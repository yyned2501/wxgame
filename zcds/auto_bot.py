# -*- coding: utf-8 -*-
"""占城大师 后台自动挂机 v3.1 (CPU 优化版)

架构:
  battle_scan.py    战斗页颜色扫描(无 OCR, ~10ms): 白=可点/红=钱不够, 石矿识别
  vision.py         特征提取层: grab() 零 OCR 抓帧 + ocr() 按需(线程数/轮询均受限)
  pages/*.py        页面层: 每页一个模块(点色指纹/动作/预期跳转/act_needs_ocr)
  auto_bot.py       主循环: 点色定页(全中/软命中, 零OCR) -> 要读字的页才 OCR 本页ROI -> 动作 -> 转移校验

设计铁律: 点色优先(用户 2026-09-03 定案) —— OCR 又慢又不准, 定页面、点哪里,
  能用颜色就绝不碰 OCR。真机实测一轮: 点色全表 2.2ms / 全图 OCR 675ms / 本页 ROI OCR 369ms。
  每页用 act_needs_ocr 声明动作层是否真需要读字(价格护栏/按钮文案), 不需要的整轮零 OCR;
  声明不需要但临时要读字的(弹窗文字关闭键), 用 ctx.need_text() 惰性补一次。

CPU 优化:
  - 战斗页零 OCR: 全部用颜色扫描
  - 指纹全中的纯点色页零 OCR; 其他页面只裁本页 roi + 限线程(ocr_config.yaml)
  - 微信进程优先级降为 BelowNormal(可 --no-low-cpu 关闭)

窗口尺寸:
  点色指纹是在 552x1006 基准尺寸上标定的, 窗口一旦被缩放, 色块就错位 -> 指纹层整片失效.
  因此机器人启动后每轮都会把窗口钉回基准尺寸(可 --no-resize 关闭).
"""
import argparse, logging, os, subprocess, sys, time
from collections import Counter, deque
from datetime import datetime

import game_utils as g
from colorprint import REF_SIZE
from config import AD_FOCUS, PAGE_CFG
from libs.vision import Vision, ScreenFeature  # 2026-09-09 Task 5: 走 libs 入口
from pages import ALL_PAGES
from pages.base import (AD_PILL_LEFT_TOL, AD_PILL_LOW_HOLD, AD_PILL_SHRINK, AD_PILL_SHRINK_PCT,
                        AD_BLACK_MAX_FRAC, CHEST_BLOCK_ALL, NAV_LOBBY_TAB,
                        AD_DIVERGE_FRAC, ad_black_frac, ad_claim_pos, ad_close_pos,
                        ad_pill_state, screen_div_frac,
                        back_arrow_pos, detect_ocr, find_close_badge, guide_targets, is_soft,
                        is_transition, nav_present, nav_tab_cx, route_prints)
from pages.lobby import CHEST_SLOTS
from pages.unknown import STUCK_DIR_OFFLINE, frame_sig

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(ROOT, 'bot.log')
# 软命中(点色差<=1个指纹点)要连续这么多帧同一页才允许动手:
# 转场/动画中间帧不会连着两帧长得一样, 稳住了才点, 免得误点。
SOFT_ACT_AFTER = 2
# 点色全表零命中、又不像转场帧时, 要连续这么多帧才允许花一次全图 OCR:
# 战斗爆炸/掉落动画会临时盖住指纹点(实测 1 帧 score 0.07), 下一帧就恢复全中,
# 旧版每出现一帧这种图就白烧 675ms 还把它判成 unknown 去点遮罩。
NO_HIT_OCR_AFTER = 2
# 黑屏连续这么多帧就不再当转场: 放完的激励视频广告页整页是黑的(真机实测 31 帧/4 分钟干等),
# 只有这种赖着不走的黑屏才去点色找右上角[关闭]; 真转场 1~2 帧就恢复, 走不到这一步。
BLANK_AD_AFTER = 2
# 卡页取证(2026-09-03 07:39 教训): 真机冒出一张没标指纹的新页面时, 点色全表零命中 ->
#   判成 unknown -> 只会点遮罩/睡 45s, 实测 7s 一圈原地空转, 而日志里一行异常都没有。
#   现在: 同一个"该动手"的页连着 STUCK_AFTER 轮一次都没动 -> 存一帧 shots_live/stuck_*.png
#   并 WARNING。battle/matching/versus/unknown/ad_popup 是合法的"等着不动手"页, 不计。
STUCK_AFTER = 20                 # 约 60s(每轮 poll ~3s)
STUCK_EXEMPT = ('battle', 'matching', 'versus', 'unknown', 'ad_popup')
# B 路卡页计数(2026-09-04 真机第 28 轮补): 点色全表连续这么多帧零命中 -> 报警。
#   这条不看画面签名(带动画的新弹窗每帧都在变, A 路永远数不到), 也不看页名
#   (那张[秘境大冒险]被 OCR 误判成 versus, 而 versus 正好在 STUCK_EXEMPT 里 -> A 路直接豁免),
#   只认"这一屏我们压根认不出来"这一件事。实测每轮 1~7s -> 十几帧就是 30~80s。
STUCK_ZEROHIT_AFTER = 12
STUCK_ZEROHIT_EVERY = 30         # 首次报警之后每多 30 帧复报一次(不必每帧都丢一张取证帧)
# 点色零命中后走全图 OCR 兜底, 连着这么多帧"OCR 认出了页却一次手都动不了" ->
# 这条路已经证明是死的: 不再花 675ms OCR, 直接交 unknown 走它的出口升级表。
OCR_ESCALATE_AFTER = 3

# 弹窗"纯回执"按钮(2026-09-04 08:41 定案, 见 pages/unknown.py 出口升级表):
# 只认点了不会花钱、不会消耗资源的回执文案, 且整条文字必须很短(按钮字样) ——
# 正文段落里出现"知道了"不算。MODAL_OK_BAD 是价格/领取/广告字样, 一律不碰。
MODAL_OK_KW = ('知道了', '我已知晓', '我知道了', '好的', '明白')
MODAL_OK_BAD = ('购买', '充值', '宝石', '钻石', '领取', '广告', '续订', '解锁',
                '元', '¥', '￥', '$')
MODAL_OK_MAX_LEN = 6         # 按钮文字长度上限(超过就是正文)
MODAL_OK_TRIES = 3           # 同一个落点最多试探几次(点不掉就交回原升级表)
# C 路活锁检测(2026-09-04 真机第 29 轮补): "点了但没进展" 的来回翻。
#   那一轮 chest_info 指纹掉到 0.8667 -> 面板认不出 -> 出口链认出真 X 把面板关掉 ->
#   回大厅再点同一行 -> 16s 一圈, 一格箱都开不成, 永远进不了战斗。
#   A 路数不到它(每轮都 acted=True, 而且画面一直在变), B 路也数不到它(大厅帧点色全中,
#   _zerohit_run 每一圈都被清零) -> 三条判据里只有"同一落点被反复点"看得见这件事。
#   判据: 最近 FLIP_WINDOW 次点击里, 同一个坐标出现 >= FLIP_REPEAT 次, 且这些点击
#         横跨 >= FLIP_PAGE_MIN 个页名(= 两个页来回翻, 而不是单页原地重试)。
FLIP_WINDOW = 8
FLIP_REPEAT = 4
FLIP_PAGE_MIN = 2
FLIP_ALARM_EVERY = 6        # 同一个活锁每判 6 次复报一次, 别每轮刷日志
FLIP_BLOCK = 300            # 活锁里如果反复点的是大厅宝箱格 -> 整行拉黑 300s(= 3~4 场战斗)


def setup_logging():
    os.makedirs(os.path.join(ROOT, 'shots'), exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE, encoding='utf-8')])


class App:
    """主循环 + 页面执行上下文(ctx)"""

    def __init__(self, max_battles=0, dry_run=False, low_cpu=True, affinity_cores=0,
                 resize=True, max_steps=0, shots=0, ad_probe=0, ad_focus=None):
        self.max_battles = max_battles
        self.dry_run = dry_run
        self.low_cpu = low_cpu
        self.affinity_cores = affinity_cores
        self.resize = resize             # 每轮把窗口钉回指纹基准尺寸
        self.max_steps = max_steps   # >0: 跑满 N 轮退出(dry-run 冒烟用)
        self.shots = shots      # >0: 每轮存帧 -> shots_live/dbg_*.png (取证用)
        self.ad_probe = ad_probe   # >0: 结算页没认到黄色[领取]时存帧 -> scratch/adprobe/ (排查广告额度用)
        self._adprobe_n = 0
        # 点[领取]前抢前台(微信激励视频在后台可能不给量) —— 开关在 config.AD_FOCUS
        self.ad_focus = AD_FOCUS if ad_focus is None else ad_focus
        self.ad_screen = True              # 广告密拍期同时抓屏幕像素(离线回归自动跳过)
        self._fg_state = None            # 上次已知"我们是不是前台", 只在变化时打日志
        self.steps = 0
        self._win_warn = 0
        self.hwnd = None
        self.vision = None
        self.pages = ALL_PAGES
        # ---- 依赖注入 (2026-09-09 重构 Task 5) ----
        # 新代码可通过 self.window.click() / self.color.pixels() 调用, 旧代码继续走 App.click/click_window.
        from libs import Window, Color, Vision
        self.window = Window()        # 窗口/截图/click/drag (封装 game_utils)
        self.color = Color()          # 点色指纹 (封装 colorprint)
        self.vision = None            # 在 ensure_window 之后实例化 (需要 hwnd)
        self.f = None                    # 当前 ScreenFeature
        self.battles = 0
        self.clicked_cells = {}        # key -> 点击时刻(battle 页按 CELL_RETRY 过期解禁)
        self.last_cell = 0
        self.last_action = {}
        self.blocked = {}                # key -> 解禁时刻(跨页拉黑, 见 pages/base.py chest_slot_key)
        self.chest_target = None         # 大厅刚点下去的宝箱格 key, 面板判付费时回写拉黑
        self.unknown_idle = 0
        self.expected = None             # 动作后期望的页面集合
        self.cur_page = None
        self._act_gap = 3.0
        self.print_confirmed = False     # 本轮页面是否由点色指纹确认(动作层据此免检)
        self._text_done = False          # 本轮这帧是否已经跑过 OCR(need_text 不重复花销)
        self._soft_page = None           # 上一帧软命中的页(软命中要连续若干帧才算稳)
        self._soft_streak = 0
        self._nohit_streak = 0           # 点色连续零命中的帧数(到第 2 帧才肯花全图 OCR)
        self._stuck_page = None          # 卡页统计: 上一轮的页名
        self._stuck_sig = None           # 卡页统计: 上一轮的画面签名(28x51 灰度缩略)
        self._stuck = 0                  # 卡页统计: 该页连续零动作轮数
        self._zerohit_run = 0            # 卡页统计 B 路: 点色全表连续零命中帧数(不看签名)
        self.modal_ok = None           # 最近一次全图 OCR 认出的弹窗回执键 (x, y, 文字)
        self._modal_ok_budget = 0      # 该落点还剩几次试探额度
        self._ocr_zero = 0               # 连续"OCR 认出页但动不了手"的帧数(到 3 帧就改走 unknown)
        self._clicks = deque(maxlen=FLIP_WINDOW)   # 最近 N 次点击 (页名, 坐标) -> C 路活锁
        self._flip_key = None            # 当前活锁的身份证 (页名组合 + 落点)
        self._flip_hits = 0              # 同一个活锁连续判定次数
        # 看广告窗口(2026-09-03 12:47 定案): _ad_until 非 0 = 窗口开着, 主循环交 _ad_tick 管
        self._ad_t0 = 0.0                # 本轮广告开始时刻
        self._ad_until = 0.0             # 窗口硬上限时刻(= 开始 + AD_WATCH_TOTAL)
        self._ad_pill_min = 0            # 本场广告左上状态药丸见过的**最窄**右边界(判"放完了")
                                          # 🔴 2026-09-05 真机 R49 事故后改 min 跟踪: 倒计时宽度
                                          # 单调递减, max 会被首帧渲染动画(329)污染成基准,
                                          # 下一帧真实宽度(211)就触发"329->211"假缩窄,
                                          # 12s 误点关闭。min 跟踪: 首帧 329 -> 二帧 211 -> pill_min=211,
                                          # 211-211=0 不缩窄; 真实"已获得奖励"164 -> 211-164=47 触发。
        self._ad_pill_first = None       # 🔴 2026-09-05 R49 事故: 首帧渲染动画(329)污染基准,
                                          #   第 2 帧才建立 pill_min = min(首, 次), 差过大就丢首帧
        self._ad_pill_samples = 0         # 药丸样本计数(第 1 帧存 first, 第 2 帧起比较)
        self._ad_white_max = 0           # 第二把尺子: 本场药丸带内白像素峰值(=字数最多的那帧)
        self._ad_pill_left = None        # 峰值帧的药丸左边界, 用来识破"广告画面盖住顶栏"的假读数
        self._ad_low_t0 = 0.0            # 白像素开始持续偏低的时刻(0 = 当前不偏低)
        self._ad_pill = ()               # 最近一次药丸读数 (右边界, 白像素, 左边界), 只为播报用
        self._ad_logged = 0.0            # 上次"播放中"播报的时刻
        self._ad_seen = False            # 是否真见过广告 chrome(见过才允许等满全程)
        self._ad_closing = False         # 已点过[关闭], 正在确认它真的关掉了
        self._ad_close_t = 0.0
        self._ad_retry_at = 0.0
        self._ad_black_t = 0.0           # 最近一次看到黑屏广告帧的时刻(0 = 没见过)

    # ---- 上下文工具(供页面调用) ----
    def ensure_foreground(self, why=''):
        """点[领取]之前把游戏窗口带到前台 —— 微信激励视频在后台可能根本不给量。

        真机依据见 config.AD_FOCUS 的注释(前台那一次 12s 后盖上黑屏广告 / 后台 6 次全无量)。
        只在"前后台状态变了"时打一行日志, 免得每场都刷。dry_run 下什么都不做:
        离线回归没有真窗口, 真去抢前台会把测试进程顶到台面上。
        """
        if not self.ad_focus or self.dry_run or not self.hwnd:
            return True
        ok = bool(g.focus_window(self.hwnd))
        if ok != self._fg_state:
            self._fg_state = ok
            logging.info(f'[广告] {why}: 点前激活游戏窗口 -> '
                         + ('已在前台' if ok else '抢不到前台(系统前台锁), 广告可能不给量'))
        return ok

    def click(self, x, y):
        # C 路活锁的原料: 谁在什么坐标点了一下(dry_run 也记, 回归脚本才测得到)
        self._clicks.append((self.cur_page or '?', (int(x), int(y))))
        if self.dry_run:
            logging.info(f'[dry] 点击 ({x},{y})')
            return
        import ctypes, ctypes.wintypes as wt
        u32 = ctypes.windll.user32
        h = self._widget()
        if not h:
            logging.error('找不到渲染窗口')
            return
        wr = wt.RECT(); u32.GetWindowRect(h, ctypes.byref(wr))
        gr = wt.RECT(); u32.GetWindowRect(self.hwnd, ctypes.byref(gr))
        px = int(x) - (gr.left - wr.left)
        py = int(y) - (gr.top - wr.top)
        lp = (py << 16) | (px & 0xFFFF)
        u32.SendMessageW(h, 0x0200, 0, lp)
        u32.SendMessageW(h, 0x0201, 0x0001, lp)
        time.sleep(0.06)
        u32.SendMessageW(h, 0x0202, 0, lp)

    def drag(self, x1, y1, x2, y2, steps=10, hold_each=0.02):
        """拖动 (x1,y1) -> (x2,y2). SendMessageW 路径, 不抢前台.
        2026-09-07 加: 给战页面自动释放技能用, 物理拖动, steps 步匀速移动.
        2026-09-08: 末尾多发 2 次 UP 兜底(0,0 坐标强制释放), 防 SendMessageW UP 没生效导致鼠标卡住.
        """
        self._clicks.append((self.cur_page or '?', ('drag', int(x1), int(y1), int(x2), int(y2))))
        if self.dry_run:
            logging.info(f'[dry] 拖动 ({x1},{y1}) -> ({x2},{y2})')
            return
        import ctypes, ctypes.wintypes as wt
        u32 = ctypes.windll.user32
        h = self._widget()
        if not h:
            logging.error('找不到渲染窗口')
            return
        wr = wt.RECT(); u32.GetWindowRect(h, ctypes.byref(wr))
        gr = wt.RECT(); u32.GetWindowRect(self.hwnd, ctypes.byref(gr))
        def to_widget(x, y):
            px = int(x) - (gr.left - wr.left)
            py = int(y) - (gr.top - wr.top)
            return (py << 16) | (px & 0xFFFF)
        lp1 = to_widget(x1, y1)
        lp2 = to_widget(x2, y2)
        u32.SendMessageW(h, 0x0200, 0, lp1)
        u32.SendMessageW(h, 0x0201, 0x0001, lp1)
        time.sleep(0.05)
        for i in range(1, steps + 1):
            t = i / steps
            mx = x1 + (x2 - x1) * t
            my = y1 + (y2 - y1) * t
            u32.SendMessageW(h, 0x0200, 0x0001, to_widget(mx, my))   # MOVE with MK_LBUTTON
            time.sleep(hold_each)
        u32.SendMessageW(h, 0x0202, 0, lp2)
        # 2026-09-08 兜底: 再发 2 次 UP(原坐标 + 0,0 强制), 防止 SendMessageW UP 没生效
        u32.SendMessageW(h, 0x0202, 0, lp2)
        u32.SendMessageW(h, 0x0200, 0, 0)         # MOVE to (0,0)
        u32.SendMessageW(h, 0x0202, 0, 0)         # UP at (0,0)

    def _widget(self):
        import ctypes, ctypes.wintypes as wt
        u32 = ctypes.windll.user32
        h = None
        def cb(w, lp):
            nonlocal h
            buf = ctypes.create_unicode_buffer(256)
            u32.GetClassNameW(w, buf, 256)
            if 'RenderWidgetHost' in buf.value:
                rc = wt.RECT(); u32.GetWindowRect(w, ctypes.byref(rc))
                if rc.right - rc.left > 50 and rc.bottom - rc.top > 50:
                    h = w
                    return False
            return True
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
        u32.EnumChildWindows(self.hwnd, WNDENUMPROC(cb), 0)
        return h or u32.ChildWindowFromPoint(self.hwnd, ctypes.wintypes.POINT(100, 100))

    # ==================== 看广告窗口 ====================
    # (用户 2026-09-03 12:47 指定: "点击黄色的看广告领取, 可以看广告的地方就自动看完")
    # 窗口一旦 arm(结算页点到黄色[领取] / 主循环撞见黑屏广告页), 主循环就**停止定页、
    # 停止 OCR、停止一切点击**, 只由 _ad_tick 管这一件事, 直到广告放完并关掉。
    # 为什么要专门的窗口: 广告创意每帧都变(点色定不了页), 而中途点[关闭]会让奖励作废
    #   并弹"是否继续观看视频"挽留框 —— 所以"什么时候才准点关闭"必须由时间+放奖判据来管。
    # 判"放完了"(零 OCR): 左上那颗状态药丸的右边界。实拍 2026-09-02 12:47 连拍:
    #   "广告 | 27 秒后可获得奖励" -> 211 / "...8 秒..." -> 204 / "广告 | 已获得奖励" -> 164
    #   同一句文案在不同广告 SDK 下宽度不同(另一路实测 209) -> 只能跟本场最宽比, 见 pages.base
    AD_WATCH_MIN = 12.0       # 这之前绝不动手: 提前关闭 = 奖励作废 + 弹挽留框
    # 🔴 用户 2026-09-05 定案「广告得看满时间, 不能中途退出」-> 旧 AD_WATCH_MAX=40s
    #   "等满就认定放完了"删除: **时间不是放完的证据**, 只有药丸缩窄(§19.3 两把尺子)才算。
    #   拿不到缩窄证据 -> 等到 AD_WATCH_TOTAL 撒手; 撒手 = 一个键都不点交回主循环,
    #   广告若还在放, 黑屏帧会被 §18 重新 arm 继续等 —— 宁可慢, 不可打断。
    AD_WATCH_TOTAL = 100.0    # 一条广告最多占用主循环这么久, 超了撒手(防死等; 撒手不点击)
    AD_CLOSE_RETRY = 3.0      # 点过[关闭]后每这么多秒复检: 还赖在广告页就再点一次
    AD_CLOSE_CONFIRM = 12.0   # 关闭动作最多盯这么久(正常下一帧就已经离开广告页)
    AD_NOT_AD_AT = 4.0        # 等了这么久、且已经硬命中**别的**游戏页 -> 认定没进广告, 撒手
    AD_NOT_AD_SAME_AT = 25.0  # 一直停在点[领取]时那一页(视频在加载)时, 最多等这么久才撒手
    AD_BLACK_GRACE = 6.0        # 见过黑屏帧之后, 这么多秒内不按"没进广告"撒手
    AD_DIVERGE_FRAC = AD_DIVERGE_FRAC      # 屏幕/PrintWindow 分歧度阈值, 见 pages.base
    AD_CLAIM_RETRY = 1          # 点[领取]后一直停在原页、等满 AD_NOT_AD_SAME_AT 仍没有广告顶栏
                                # -> 再点一次[领取](真机 R35: 04:43 那次在结算页干等 28s 广告始终没来,
                                #    而 04:22 那次一次就中 —— 无填充时再点一次是免费的, 不烧"可用 x/8")
    AD_SHOT_MAX = 14          # 一次广告窗口最多存几帧取证(见 _ad_sample)
    AD_SHOT_EVERY = 4.0       # 密拍结束后每这么多秒一帧
    AD_SHOT_DENSE = 0.5       # 前 AD_SHOT_DENSE_N 帧每这么多秒一张: 广告盖上/退回游戏页
                              # 都发生在点[领取]后的头几秒, 4s 一张会整段漏掉(真机 R34 就是这样)
    AD_SHOT_DENSE_N = 9       # 密拍到第几张为止(arm+1s 起, 覆盖到 ~5s)
    AD_TICK_POLL = 0.5        # 看广告窗口里主循环一跳多久(原来跟着 PAGE_CFG 的 3s, 密拍形同虚设)
                              # 实测一帧 grab+关闭位+药丸+黑屏 = 37ms, 0.5s 一跳只吃掉单核 ~7%;
                              # 所有广告判据(AD_NOT_AD_AT / BLACK_GRACE / LOW_HOLD / WATCH_MIN)
                              # 都是按**秒**算的, 加密只会更快更准, 不会提前点[关闭]。

    def start_ad_watch(self, why=''):
        """arm 看广告窗口: result 点完黄色[领取]后调用, 或主循环撞见广告页时调用"""
        now = time.time()
        self._ad_t0, self._ad_until = now, now + self.AD_WATCH_TOTAL
        # 记下 arm 时站在哪一页: _ad_tick 靠它区分"广告在加载(还是这页)"和"已经跑到别的页(广告没来)"
        self._ad_from = self.cur_page
        self._ad_pill_min, self._ad_pill_first, self._ad_pill_samples, self._ad_logged = 0, None, 0, now
        self._ad_white_max, self._ad_pill_left, self._ad_low_t0, self._ad_pill = 0, None, 0.0, ()
        self._ad_seen, self._ad_closing = False, False
        self._ad_shot_next, self._ad_shot_n = now + 1.0, 0
        # 每场重置黑屏时间戳: 不然第二次看广告时 _ad_black_t 还是上一场的旧值，
        # 那行"黑屏帧 = 正在放广告"的日志永远不会再打印(只影响可观察性，不影响判据)。
        self._ad_black_t = 0.0
        self._ad_close_t = self._ad_retry_at = 0.0
        self._ad_claim_retry = 0
        logging.info(f'[广告] 开始看广告({why}): 期间不定页/不跑 OCR/不点击; '
                     f'放完判据 = 状态药丸缩窄(唯一证据, 时间不算); '
                     f'最长 {self.AD_WATCH_TOTAL:.0f}s, 超了撒手(不点任何键)')

    def _ad_overlay_frac(self, img):
        """只在"准备撒手/重试"的那一刻问一次屏幕通道: 现在盖在窗口上的东西 PrintWindow 看得见吗?

        取一次 BitBlt 只要 ~25ms, 不进常规密拍(密拍段另存 ads_*.png 是另一回事);
        屏幕通道自检不通过 / dry_run / 抓失败 -> 返回 None, 调用方按旧口径处理(不把新判据当硬闸门)。
        """
        if not self.ad_screen or not self.hwnd or self.dry_run:
            return None
        try:
            sc = g.capture_screen(self.hwnd)
        except Exception as e:
            logging.warning(f'[广告] 屏幕通道抓取失败: {e}')
            return None
        return screen_div_frac(img, sc)

    def _end_ad_watch(self):
        self._ad_until = 0.0
        self._ad_closing = False

    def _ad_tick(self, img):
        """看广告窗口的一轮。
        -> 'wait'   本轮什么都不做(也不花 OCR)
        -> 'acted'  本轮点了[关闭]
        -> 'done'   广告确实关掉了 / 确认已离开广告页 -> 交回正常路由(同一帧就能认出)
        -> 'giveup' 超时无奈或压根没进广告 -> 交回正常路由
        """
        now = time.time()
        waited = now - self._ad_t0
        if now > self._ad_until:
            logging.warning(f'[广告] 看了 {waited:.0f}s 仍没放完 -> 撒手交回正常路由(防死等)')
            self._end_ad_watch()
            return 'giveup'
        pos = ad_close_pos(img)
        if pos is not None:
            self._ad_seen = True
            # 稳定命中兜底: ad_close_pos 连续 3 帧同坐标 + 广告期 >= AD_WATCH_MIN 直接点
            if (waited >= self.AD_WATCH_MIN
                    and getattr(self, '_ad_close_streak_pos', None) == pos
                    and getattr(self, '_ad_close_streak_n', 0) >= 3
                    and not getattr(self, '_ad_closing', False)):
                logging.info(f'[广告] 看了 {waited:.0f}s, 关闭按钮稳定命中 {pos} 3 帧 -> 直接点')
                self.click(*pos)
                self._ad_closing = True
                self._ad_close_t = now
                self._ad_retry_at = now + self.AD_CLOSE_RETRY
                self._ad_close_streak_pos = None
                self._ad_close_streak_n = 0
                return 'acted'
            if getattr(self, '_ad_close_streak_pos', None) == pos:
                self._ad_close_streak_n = getattr(self, '_ad_close_streak_n', 0) + 1
            else:
                self._ad_close_streak_pos = pos
                self._ad_close_streak_n = 1
        else:
            self._ad_close_streak_pos = None
            self._ad_close_streak_n = 0
        # OCR 主导判据(2026-09-12 用户定案): 药丸 ROI OCR 识别到 "已获得奖励" 直接点关闭.
        # 不依赖 ad_close_pos —— 即使这一帧是转场帧 pos=None, OCR 仍能读出文字;
        # 触发后再重算一次 ad_close_pos (广告放完时关闭按钮一定在), 找不到就用 OCR
        # 区域附近的默认坐标 (488, 77 是微信激励视频 SDK 的常见位置). 优先级最高,
        # 早于"12s 稳定命中"兜底.
        if (waited >= self.AD_WATCH_MIN
                and not getattr(self, '_ad_closing', False)
                and now - getattr(self, '_ad_ocr_last', 0.0) >= 3.0):
            self._ad_ocr_last = now
            try:
                self.vision._ensure_ocr()
                w, h = img.size
                crop = img.crop((0, 55, min(330, w), min(118, h)))
                res, _ = self.vision._ocr(crop)
                joined = ' '.join(item[1] for item in (res or []))
                if '已获得奖励' in joined:
                    close_pos = pos or ad_close_pos(img) or (488, 77)
                    logging.info(f'[广告] OCR 识别到 "已获得奖励" ({waited:.0f}s) -> 点[关闭] {close_pos}')
                    self.click(*close_pos)
                    self._ad_closing = True
                    self._ad_close_t = now
                    self._ad_retry_at = now + self.AD_CLOSE_RETRY
                    self._ad_close_streak_pos = None
                    self._ad_close_streak_n = 0
                    return 'acted'
            except Exception as e:
                logging.warning(f'[广告] OCR 判据失败: {e}')
        self._ad_sample(img, pos, now)
        # 1) 已经点过一次[关闭]: 还赖在广告页就重补一次, 认不出广告页了就交回主循环
        if self._ad_closing:
            if pos is None:
                logging.info(f'[广告] 点[关闭]后 {now - self._ad_close_t:.0f}s 已离开广告页 -> 交回正常路由')
                self._end_ad_watch()
                return 'done'
            if now - self._ad_close_t >= self.AD_CLOSE_CONFIRM:
                logging.warning(f'[广告] 点[关闭]后 {self.AD_CLOSE_CONFIRM:.0f}s 还赖在广告页 -> 交回正常路由')
                self._end_ad_watch()
                return 'done'
            if now >= self._ad_retry_at:
                self._ad_retry_at = now + self.AD_CLOSE_RETRY
                self._ad_close_t = now
                logging.warning(f'[广告] 还赖在广告页 -> 再点一次[关闭] {pos}')
                self.click(*pos)
                return 'acted'
            return 'wait'
        # 2) 压根没进广告(点[领取]没跳转 / 弹的是别的窗): 别把主循环锁死在这。
        #    分两档 —— "还停在点[领取]那一页"和"已经跑到别的页"完全不是一回事:
        #      · 硬命中**别的**游戏页: 那一页已经盖在结算页上面了, 广告不可能还在后面加载
        #        -> 等满 AD_NOT_AD_AT 就撒手(真机 R29~R32 的 18 次里有 13 次是这一档);
        #      · 还停在**点[领取]时那一页**: 微信激励视频冷启动要 5~15s, 这期间画面就是原页,
        #        4s 撒手会把真广告判成没进广告、白丢一次奖励 -> 放宽到 AD_NOT_AD_SAME_AT。
        # 2a) 黑屏帧 = 广告正在放: PrintWindow 抓不到视频层, 整屏只剩顶部一条 chrome,
        #     实测真广告帧非黑像素仅 5~6%(判据与阈值来路见 pages.base.AD_BLACK_MAX_FRAC)。
        #     顶栏没认出来也只是"这家 SDK 的 chrome 长得不一样", 绝不能当"没进广告"撒手 ——
        #     撒手后主循环会立刻去点别的地方 = 自己把广告打断 = 奖励作废。
        #     但不给永久免检: 游戏自己的黑屏转场长得一样 -> 只在"最近 AD_BLACK_GRACE 秒内
        #     确实见过黑屏"时豁免; 画面一旦回到正常游戏页且顶栏还是认不出, 2b 照常撒手。
        if not self._ad_seen:
            frac = ad_black_frac(img)
            if frac < AD_BLACK_MAX_FRAC:
                if not self._ad_black_t:
                    logging.info(f'[广告] 看了 {waited:.0f}s: 黑屏帧(非黑像素仅 {frac * 100:.1f}%) '
                                 f'= 正在放广告, 顶栏没认出来也继续等')
                self._ad_black_t = now
        if (not self._ad_seen and waited >= self.AD_NOT_AD_AT
                and now - self._ad_black_t >= self.AD_BLACK_GRACE):
            hard = self._ad_page_hard(img)
            same = hard is not None and hard == self._ad_from
            # 2b-① 动手前先问一次屏幕通道: 分歧度大 = 屏幕上确实盖着一层 PrintWindow 拍不到的
            #     东西 = 广告正在放。这时候无论是撒手还是"免费再点一次[领取]",都等于自己把广告打断
            #     -> 继续等(借用 _ad_black_t 这个"最近确实在放广告"的免死钻, 同 2a)。
            div = None
            if hard is not None and (not same or waited >= self.AD_NOT_AD_SAME_AT):
                div = self._ad_overlay_frac(img)
                if div is not None:
                    logging.info(f'[广告] 通道分歧度 {div * 100:.1f}%(阈值 {self.AD_DIVERGE_FRAC * 100:.0f}%) '
                                 f'-> ' + ('屏幕上有 PrintWindow 看不见的层 = 广告正在放, 继续等'
                                          if div >= self.AD_DIVERGE_FRAC else '两条通道一致 = 确实没广告'))
            if div is not None and div >= self.AD_DIVERGE_FRAC:
                self._ad_black_t = now
                return 'wait'
            # 2b-② 还站在点[领取]那一页、且黄色[领取]还在 -> 先免费再点一次, 别急着撒手
            if (same and waited >= self.AD_NOT_AD_SAME_AT
                    and self._ad_claim_retry < self.AD_CLAIM_RETRY):
                cp = ad_claim_pos(img)
                if cp is not None:
                    self._ad_claim_retry += 1
                    self._ad_t0, self._ad_until = now, now + self.AD_WATCH_TOTAL
                    logging.info(f'[广告] 等了 {waited:.0f}s 还停在 {self._ad_from} 且没有广告顶栏 '
                                 f'-> 免费再点一次[领取] {cp} (第 {self._ad_claim_retry} 次, 重新计时)')
                    self.click(*cp)
                    return 'acted'
            if hard is not None and (not same or waited >= self.AD_NOT_AD_SAME_AT):
                logging.warning(f'[广告] 等了 {waited:.0f}s 硬命中游戏页 {hard} '
                                f'(点[领取]时在 {self._ad_from}) 且始终没有广告顶栏 '
                                f'-> 判定没在看广告, 交回正常路由')
                self._end_ad_watch()
                return 'giveup'
        # 3) 正在放: 一帧都不点, 只盯状态药丸有没有变短(= 文案换成"已获得奖励")。
        #    两把尺子任一命中即算放完: ①右边界相对本场最宽缩掉 >=AD_PILL_SHRINK px
        #                  ②带内白像素相对本场峰值少 >=AD_PILL_SHRINK_PCT 且持续 AD_PILL_LOW_HOLD 秒
        shrink, gate = False, ''
        if pos is not None:
            st = ad_pill_state(img)
            if st is not None:
                pr, wc, pl = st
                self._ad_pill = st
                if self._ad_pill_left is not None and abs(pl - self._ad_pill_left) > AD_PILL_LEFT_TOL:
                    # 广告画面糊上顶栏: 这一帧的读数不可信, 两把尺子都不作数(也不清基准)
                    gate = (f'药丸左边界 {self._ad_pill_left}->{pl} 漂移超 '
                            f'{AD_PILL_LEFT_TOL}px = 顶栏被广告盖住 -> 本轮尺子作废')
                    self._ad_low_t0 = 0.0
                else:
                    if wc > self._ad_white_max:
                        # "字最多"的那一帧才是基准(倒计时一定比放奖后长), 左边界跟着它走
                        self._ad_white_max, self._ad_pill_left = wc, pl
                    if self._ad_pill_samples == 0:
                        # 首帧: 先存着, 不下结论
                        self._ad_pill_first = pr
                        self._ad_pill_samples = 1
                    elif self._ad_pill_samples == 1:
                        # 第 2 帧: pill_min = min(首, 次); 差过大就丢首帧(动画外层)
                        self._ad_pill_min = min(self._ad_pill_first, pr)
                        self._ad_pill_samples = 2
                    else:
                        # 先用更新前的 pill_min 算 shrink1, 再决定要不要把 pill_min 往下踩
                        shrink1 = self._ad_pill_min > 0 and self._ad_pill_min - pr >= AD_PILL_SHRINK
                        if pr < self._ad_pill_min:
                            self._ad_pill_min = pr
                    # 第二把尺子: 白像素变少 (跟右边界并列, 独立触发)
                    shrink2_held = False
                    if wc <= self._ad_white_max * (1 - AD_PILL_SHRINK_PCT):
                        if not self._ad_low_t0:
                            self._ad_low_t0 = now
                        elif now - self._ad_low_t0 >= AD_PILL_LOW_HOLD:
                            shrink2_held = True
                    else:
                        self._ad_low_t0 = 0.0
                    shrink = locals().get('shrink1', False) or shrink2_held
                    if shrink:
                        how1 = f'药丸缩窄 {self._ad_pill_min}->{pr}' if locals().get('shrink1', False) else ''
                        how2 = (f'药丸字变少 {self._ad_white_max}->{wc}px 持续 '
                                f'{now - self._ad_low_t0:.0f}s') if shrink2_held else ''
                        how = (how1 + ' ' + how2).strip() or f'放完判据命中'
            if waited >= self.AD_WATCH_MIN and shrink:
                how += ' = 已获得奖励'
                logging.info(f'[广告] 看了 {waited:.0f}s, {how} -> 点[关闭] {pos}')
                self.click(*pos)
                self._ad_closing = True
                self._ad_close_t = now
                self._ad_retry_at = now + self.AD_CLOSE_RETRY
                return 'acted'
        if gate:
            logging.info(f'[广告] {gate}')
        if now - self._ad_logged >= 10.0:
            self._ad_logged = now
            logging.info(f'[广告] 播放中 {waited:.0f}s: 本轮不动作, 也不花 OCR '
                         f'(药丸 右={self._ad_pill[0] if self._ad_pill else "-"} '
                         f'白={self._ad_pill[1] if self._ad_pill else "-"}/峰 {self._ad_white_max} '
                         f'左={self._ad_pill[2] if self._ad_pill else "-"})')
        return 'wait'

    def _ad_sample(self, img, pos, now):
        """广告窗口存证: 把这一帧写到 shots_live/ad_*.png

        为什么非做不可: 广告创意每帧都变(点色定不了页), 但顶栏那颗状态药丸和[关闭]叉
        是广告 SDK 的固定件 —— 想零 OCR 认出【广告放完了】就必须拿真广告帧标定它们。
        真机 R31(2026-09-04 02:39~02:41)整段 100s 里 ad_close_pos 一次都没命中,
        日志只有 药丸 右=- 白=-/峰 0 左=-, 而窗口期间**一帧都不落盘** => 下一轮还是没得标,
        死等 bug 永远修不掉。arm 后 1s 存第一帧, 之后每 20s 一帧; 文件名带 p/n 表示
        这一帧有没有认出广告顶栏, 标定和分组都靠它。
        """
        if now < self._ad_shot_next or self._ad_shot_n >= self.AD_SHOT_MAX:
            return
        self._ad_shot_n += 1
        self._ad_shot_next = now + (self.AD_SHOT_DENSE if self._ad_shot_n < self.AD_SHOT_DENSE_N
                                    else self.AD_SHOT_EVERY)
        # 目录口径抄 _flag_stuck: 离线回归每跑一次就丢几张假广告帧, 不能污染
        # shots_live/ 这个真机取证目录(真机靠 ad_*_p/n 判"广告到底有没有起来")。
        d = STUCK_DIR_OFFLINE if getattr(self, 'dry_run', True) else os.path.join(ROOT, 'shots_live')
        fn = 'ad_%s_%s.png' % (time.strftime('%H%M%S'), 'p' if pos is not None else 'n')
        try:
            os.makedirs(d, exist_ok=True)
            img.save(os.path.join(d, fn))
            extra = ''
            # 第二通道: 密拍阶段同一时刻再抓一张**屏幕像素**(见 game_utils.capture_screen)。
            # 两条通道都是游戏页 => 广告确实没起来; 屏幕那张黑掉/变成广告 => 是 PrintWindow
            # 抓不到视频层, 判据得改走屏幕通道。真机 R34(04:16)游戏窗口已在前台、Z 序第一、
            # 点[领取]后 3s 窗口自绘仍是游戏页 -> 只有这条通道能分清 A/B 两种解释。
            if self.ad_screen and not self.dry_run and self._ad_shot_n <= self.AD_SHOT_DENSE_N:
                sfn = fn.replace('ad_', 'ads_')
                g.capture_screen(self.hwnd).save(os.path.join(d, sfn))
                extra = ' +屏幕帧 ' + sfn
            logging.info('[广告取证] 存帧 %s (关闭位=%s 药丸=%s)%s', fn, pos,
                         self._ad_pill or '-', extra)
        except Exception as ex:
            logging.warning('[广告取证] 存帧失败: %s', ex)

    def _ad_page_hard(self, img):
        """广告窗口里的"根本没在看广告"探针: 点色能**硬命中**某个已知页(2ms, 零 OCR) => 还留在游戏里

        返回命中的页名(没命中 -> None)。调用方还要看它是不是点[领取]时那一页, 所以不能只回 bool。
        """
        page, _score, src = route_prints(self.pages, img, prefer=self.expected or ())
        return page.name if (page is not None and not is_soft(src)) else None

    def acted(self, key, gap=None):
        """动作冷却: True=还在冷却期(跳过); False=可以执行并刷新"""
        gap = gap or self._act_gap
        now = time.time()
        if now - self.last_action.get(key, 0) < gap:
            return True
        self.last_action[key] = now
        return False

    def block(self, key, sec, why=''):
        """拉黑某个目标 sec 秒(= 这段时间内别再点它). 与 acted() 的区别:
        acted 是"同一动作别重复做"的节流, block 是"这个目标本身现在不能碰"."""
        self.blocked[key] = time.time() + sec
        logging.info(f'[拉黑] {key} {sec}s ({why})')

    def is_blocked(self, key):
        """目标还在拉黑期吗"""
        return time.time() < self.blocked.get(key, 0.0)

    def ensure_window(self):
        # 2026-09-08 真机长测: hwnd churn (游戏窗口重开句柄变) 会导致找不到窗口死循环抛 RuntimeError.
        # 加 5次 × 2s = 10s 重试给窗口恢复时间, 减少不必要的 bot 中断.
        for attempt in range(5):
            if self.hwnd and g.u32.IsWindow(self.hwnd):
                return
            self.hwnd = g.find_game_window()
            if self.hwnd is not None:
                self.vision = Vision(self.hwnd)
                self._win_warn = 0
                self._screen_selftest()
                return
            if attempt < 4:
                logging.info(f'[窗口] 找不到, {2}s 后重试 (第 {attempt+1}/5 次)')
                time.sleep(2)
        raise RuntimeError('找不到游戏窗口, 请先打开 占城大师')

    def _screen_selftest(self):
        """屏幕通道自检(capture_screen 和 PrintWindow 是两条独立的路, 一条废了另一条不一定废)

        真机 R35 实证: enter_default_desktop 用低权限掩码切过桌面之后, 本线程的屏幕 DC 被废,
        capture_screen 整帧纯黑, 而 PrintWindow 完全正常 —— 广告取证帧 ads_*.png 全黑就是这么
        来的(独立进程抓同一块屏幕 mean≈146)。根因修好之后仍留这道自检: 以后换任何运行上下文,
        日志第一句就说清屏幕通道能不能用, 不用对着全黑帧猜。
        """
        try:
            lr, tt, rr, bb = g.get_rect(self.hwnd)
            best = 0.0
            for fx, fy in ((0.5, 0.5), (0.25, 0.25), (0.75, 0.75)):
                x, y = int(lr + (rr - lr) * fx), int(tt + (bb - tt) * fy)
                im = g.capture_screen_rect(x - 40, y - 40, 80, 80)
                best = max(best, float(im.convert('L').resize((1, 1)).getpixel((0, 0))))
        except Exception as ex:
            logging.warning('[自检] 屏幕通道异常: %s', ex)
            best = -1.0
        self.ad_screen = best > 0.0
        logging.info('[自检] 屏幕通道 %s (窗口内 3 点 80x80 最大灰度均值=%.1f)',
                     '可用' if best > 0 else '全黑 -> 关闭广告密拍的屏幕帧', best)

    def ensure_window_size(self):
        """把窗口钉回指纹标定的基准尺寸 REF_SIZE(点色色块对尺寸极敏感)"""
        if not self.resize:
            return
        w0, h0 = g.window_size(self.hwnd)
        if w0 < 2 or h0 < 2:
            return                     # 假句柄/离线测试: 没有真实窗口, 不折腾也不刷日志
        ok, w, h = g.set_window_size(self.hwnd, REF_SIZE[0], REF_SIZE[1])
        if (w0, h0) != (w, h):
            logging.info('[窗口] 尺寸 %dx%d -> %dx%d (指纹基准 %dx%d)',
                         w0, h0, w, h, REF_SIZE[0], REF_SIZE[1])
            if self.vision is not None:
                self.vision.reset()      # 画面缩放后旧特征与 OCR 缓存全部作废
        if not ok:
            self._win_warn += 1
            if self._win_warn % 10 == 1:
                logging.warning('[窗口] 无法设为 %dx%d, 实际 %dx%d -> 指纹层可能失效 '
                                '(不想自动改窗口就加 --no-resize)',
                                REF_SIZE[0], REF_SIZE[1], w, h)
        else:
            self._win_warn = 0

    def apply_low_cpu(self):
        """把微信进程优先级降到 BelowNormal(+可选限核), 降低对系统的抢占"""
        if not self.low_cpu:
            return
        script = os.path.join(ROOT, 'tools', 'set_low_cpu.ps1')
        if not os.path.exists(script):
            logging.warning('缺少 tools/set_low_cpu.ps1, 跳过降优先级')
            return
        cmd = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
               '-File', script, '-Priority', 'BelowNormal']
        if self.affinity_cores:
            cmd += ['-AffinityCores', str(self.affinity_cores)]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=30)
            if r.returncode:
                logging.warning('降低微信优先级异常: %s',
                                r.stderr.decode('utf-8', 'replace')[:200])
            else:
                logging.info('已降低微信进程优先级' +
                             (f' 并限 {self.affinity_cores} 核' if self.affinity_cores else ''))
        except Exception as e:
            logging.warning('降低微信优先级失败(可忽略): %s', e)

    # ---- 惰性文字特征(点色优先) ----
    def page_by_name(self, name):
        """按名字取页面对象 —— 给'不标指纹、只能靠上下文推出身份'的页用(tab_other)。
        这些页永远进不了 route_prints 的候选表, 所以只能显式点名。"""
        for pg in self.pages:
            if pg.name == name:
                return pg
        return self.pages[-1]

    def need_text(self):
        """点色命中时默认不跑 OCR; 动作层真需要读字, 才现补一次本页 ROI OCR(每轮至多一次)"""
        if self._text_done or self.f is None:
            return self.f
        self._text_done = True
        fg = PAGE_CFG.get(self.cur_page, PAGE_CFG['unknown'])
        self.f, _ = self.vision.ocr(self.f.img, region=fg['roi'], scale=fg['scale'],
                                    min_gap=fg['ocr_gap'])
        return self.f

    def _soft_stable(self, name):
        """软命中是否已连续 SOFT_ACT_AFTER 帧同一页(= 这帧画面稳了, 可以按它动手)"""
        if self._soft_page == name:
            self._soft_streak += 1
        else:
            self._soft_page, self._soft_streak = name, 1
        return self._soft_streak >= SOFT_ACT_AFTER

    def _save_shot(self, img, label):
        """--shots N 取证模式: 把当前帧存成 shots_live/dbg_NNN_<label>_<hhmmss>.png"""
        d = os.path.join(ROOT, 'shots_live')
        os.makedirs(d, exist_ok=True)
        fn = 'dbg_{0:03d}_{1}_{2}.png'.format(self.steps, label, time.strftime('%H%M%S'))
        try:
            img.save(os.path.join(d, fn))
            logging.info(f'{"[DRY]" if self.dry_run else ""}[存帧] {fn}')
        except Exception as e:
            logging.warning('[存帧] 失败: %s', e)

    def ad_probe_shot(self, img, why=''):
        """--ad-probe N: 结算页**没**认到黄色[领取]时存一帧, 用来回答"广告额度用完没"。

        为什么不直接塞 shots_live/: 用户明确要过"临时帧别污染 shots_live/", 而这个探针
        只在排查广告问题时开(平时一轮一帧都不写)。第 19/20 轮 400 步各 6 场战斗,
        [领取] 一次都没命中 —— 到底是"每日 8 次额度在 13:33 就用完了"(日志最后一次命中
        13:32:58), 还是"横幅在但点色判据漏了", 光看日志分不出来, 得肉眼看过那一帧。
        """
        if not self.ad_probe or self._adprobe_n >= self.ad_probe:
            return
        d = os.path.join(ROOT, 'scratch', 'adprobe')
        os.makedirs(d, exist_ok=True)
        self._adprobe_n += 1
        fn = os.path.join(d, 'noclaim_{0:03d}_{1}_{2}.png'.format(
            self._adprobe_n, why or '?', time.strftime('%H%M%S')))
        try:
            img.save(fn)
            logging.info('[广告探针] 本帧没有黄色[领取] -> 存帧 %s', fn)
        except Exception as e:
            logging.warning('[广告探针] 存帧失败: %s', e)

    # ---- OCR 兜底 = 白捡一条"待标语料"(2026-09-03 加) --------------------------
    # 真机长测里剩下的 OCR 路由只有 result / vip_popup 两页(它们有种没进语料的版式),
    # 但 --shots 0 时这些帧一帧都不落盘 -> 下次还是没语料标, 永远补不上。
    # 所以: 只要定页走了全图 OCR(src=='ocr'), 就把这一帧存进 shots_live/, 标完就少一条 OCR。
    OCR_SHOT_MAX = 20           # 一轮最多存 20 张, 别把 shots_live 灌满
    OCR_SHOT_GAP = 20.0         # 同一页两次存帧至少隔 20s(连着几帧都是同一屏, 存一张够)

    def _save_ocr_shot(self, page, img):
        """走了 OCR 兜底 -> 说明这屏点色认不出, 存成待标语料(零行为改动, 只多写一张 png)"""
        at = getattr(self, '_ocr_shot_at', None)
        if at is None:
            at = self._ocr_shot_at = {}
            self._ocr_shots = 0
        if self._ocr_shots >= self.OCR_SHOT_MAX:
            return
        now = time.time()
        if now - at.get(page, 0.0) < self.OCR_SHOT_GAP:
            return
        d = os.path.join(ROOT, 'shots_live')
        os.makedirs(d, exist_ok=True)
        fn = 'ocr_%s_%s.png' % (page, time.strftime('%H%M%S'))
        try:
            img.save(os.path.join(d, fn))
            at[page] = now
            self._ocr_shots += 1
            logging.info(f'[待标语料] {page} 是靠 OCR 认出来的 -> 存帧 shots_live/{fn} '
                         f'(登记进 pick_print.LABELS 后这条 OCR 路由就能换成点色)')
        except Exception as e:
            logging.warning('[待标语料] 存帧失败: %s', e)

    def _flag_stuck(self, page, acted):
        """卡页检测: 只报警 + 存帧取证, 绝不代替页面做任何点击

        坑(真机 2026-09-03 16:03 新卡页): 点色零命中的那一帧 step() 按 2b 的防抖返回 page=None,
        下一帧才花全图 OCR 认出 result —— page 就在 None/result 之间来回翻, 而旧版第一句就是
        "page is None 就清零", 等于让那个防抖自己把卡页计数永远打断: 连着 60s 一次动作都没做成,
        [卡页] 警报一行都没发(事后全靠数日志才发现)。
        现在: None 帧沿用上一帧的页名继续算, 但**画面签名 frame_sig 一变就重新计数** ——
        转场白烟/激励视频每帧都在变 -> 不会误报; 真卡死时画面一动不动 -> 一定数得到 20 帧。
        看广告窗口(_ad_until)整段豁免: 那本来就是我们故意不动手。
        B 路(2026-09-04 R28 补): 开屏那张[秘境大冒险]活动弹窗有动画 -> 每帧 frame_sig 都在变,
          A 路被动画一路打断; 而且它被全图 OCR 误判成 versus, versus 又在 STUCK_EXEMPT 里 ->
          A 路连页名这一关都过不去。结果 4 分钟零动作、零警报(事后全靠数日志才发现)。
          现在再数一条"点色全表连续 N 帧零命中": 认不出来这么多帧, 这件事本身就是要报警的事实,
          不需要先知道这是哪一页。仍然只报警 + 存帧, 一个点都不替页面点。
        """
        name = page.name if page is not None else self.cur_page
        img = getattr(self.f, 'img', None)
        sig = frame_sig(img) if img is not None else None
        same = bool(name) and name == self._stuck_page and sig == self._stuck_sig
        self._stuck_page, self._stuck_sig = name, sig
        self._stuck = self._stuck + 1 if same else 1
        z = self._zerohit_run
        hit_static = name not in STUCK_EXEMPT and self._stuck == STUCK_AFTER
        hit_zerohit = (z >= STUCK_ZEROHIT_AFTER
                       and (z == STUCK_ZEROHIT_AFTER or z % STUCK_ZEROHIT_EVERY == 0))
        if acted or self._ad_until or not name or not (hit_static or hit_zerohit):
            return
        if img is None:
            return
        # 取证帧目录和 unknown._give_up 同一口径(pages.unknown.stuck_dir 的道理):
        # 离线回归每跑一次就丢几张帧, 不能污染 shots_live/ 这个真机取证目录。
        d = STUCK_DIR_OFFLINE if getattr(self, 'dry_run', True) else os.path.join(ROOT, 'shots_live')
        os.makedirs(d, exist_ok=True)
        fn = 'stuck_%s_%s.png' % (name, time.strftime('%H%M%S'))
        why = ('点色连续 %d 帧零命中' % z) if hit_zerohit else ('同页连续 %d 轮零动作' % self._stuck)
        try:
            img.save(os.path.join(d, fn))
            logging.warning('[卡页] %s %s -> 存帧 %s '
                            '(多半是撞上新页面没标指纹, 或按钮位置/颜色变了)',
                            name, why, os.path.relpath(os.path.join(d, fn), ROOT))
        except Exception as e:
            logging.warning('[卡页] 存帧失败: %s', e)

    def _find_modal_ok(self):
        """最近一帧全图 OCR 里找弹窗"纯回执"按钮 -> (x, y, 文字); 没有 -> None

        只认回执, 不认领取/购买: MODAL_OK_BAD 里的字样一个都不许碰(花钱护栏),
        文字长度 > MODAL_OK_MAX_LEN 一律当正文跳过。取最后一个命中框 = 弹窗最下面
        那颗按钮(回执键永远在正文之后)。
        """
        boxes = getattr(getattr(self, 'f', None), 'boxes', None) or []
        hit = None
        for b in boxes:
            txt = (b.text or '').replace(' ', '')
            if not txt or len(txt) > MODAL_OK_MAX_LEN:
                continue
            if not any(k in txt for k in MODAL_OK_KW):
                continue
            if any(k in txt for k in MODAL_OK_BAD):
                continue
            hit = (b.cx, b.cy, b.text)
        return hit

    def _scan_modal_ok(self):
        """刷新回执键 + 额度: 落点变了才重新给 MODAL_OK_TRIES 次机会"""
        pos = self._find_modal_ok()
        if pos is None:
            self.modal_ok, self._modal_ok_budget = None, 0
            return
        if self.modal_ok is None or self.modal_ok[:2] != pos[:2]:
            self._modal_ok_budget = MODAL_OK_TRIES
        self.modal_ok = pos

    def _flag_flip(self, page, acted):
        """C 路活锁检测: 两个页来回翻 + 同一落点反复点 = 点了没进展.

        坑(真机 2026-09-04 第 29 轮, 连转 40 分钟一格箱都没开成): chest_info(开箱面板)的旧指纹
        15 个点里有一串标在[标题行/卡名行]的**文字像素**上; 游戏当天那一格是[青铜宝箱]
        (语料里只有木箱/铁箱) -> 字形位置变了 -> 13/15 = 0.8667 掉出软命中门槛
        -> 面板认不出 -> 出口链 find_close_badge 认出面板真 X (468,165)
        -> **机器人自己把面板关掉** -> 回大厅再点同一行 -> 16s 一圈, 永远进不了战斗。
        A 路(_flag_stuck 静态签名)数不到它: 每轮 acted=True, 而且画面一直在变;
        B 路(点色连续零命中)也数不到它: 大厅帧点色全中, _zerohit_run 每一圈都被清零。
        => 三条判据里只有[同一坐标在短时间内被反复点]看得见这件事。

        判据(常量见文件头 FLIP_*): 最近 FLIP_WINDOW 次点击里同一个坐标出现 >= FLIP_REPEAT 次,
        且这些点击横跨 >= FLIP_PAGE_MIN 个页名(= 两页来回翻, 不是单页原地重试)。
        动作: 只报警 + 存帧取证; 唯一允许的补救是这串点击里出现过大厅宝箱格时把整行拉黑
        FLIP_BLOCK 秒 —— 那是活锁的燃料, 断掉它机器人自然会去开战斗, 比继续空转强。
        (同日已把 chest_info 指纹整条重标到面板固定件上, 这条只是防同类腐烂再犯。)
        """
        if not acted or len(self._clicks) < FLIP_REPEAT:
            return
        win = list(self._clicks)
        names = {n for n, _pt in win}
        if len(names) < FLIP_PAGE_MIN:
            return
        (px, py), times = Counter(_pt for _n, _pt in win).most_common(1)[0]
        if times < FLIP_REPEAT:
            return
        pair = '<->'.join(sorted(names))
        key = '%s@%d,%d' % (pair, px, py)
        if key != self._flip_key:
            self._flip_key, self._flip_hits = key, 0
        self._flip_hits += 1
        if self._flip_hits > 1 and self._flip_hits % FLIP_ALARM_EVERY:
            return                 # 同一个活锁别每轮刷屏: 只在第 1 / 6 / 12 ... 次报
        name = page.name if page is not None else self.cur_page
        img = getattr(self.f, 'img', None)
        # 取证帧目录口径抄 _flag_stuck: 离线回归每跑一次就丢几张帧, 不能污染 shots_live/
        d = STUCK_DIR_OFFLINE if getattr(self, 'dry_run', True) else os.path.join(ROOT, 'shots_live')
        fp = '-'
        if img is not None:
            try:
                os.makedirs(d, exist_ok=True)
                fp = os.path.join(d, 'flip_%s_%s.png' % (name, time.strftime('%H%M%S')))
                img.save(fp)
                fp = os.path.relpath(fp, ROOT)
            except Exception as e:
                logging.warning('[活锁] 存帧失败: %s', e)
        logging.warning('[活锁] %s 最近 %d 次点击里 (%d,%d) 重复 %d 次, 页名 %s '
                        '(第 %d 次判定) -> 点了没进展, 存帧 %s',
                        name, FLIP_WINDOW, px, py, times, pair, self._flip_hits, fp)
        slots = {(int(x), int(y)) for x, y in CHEST_SLOTS}
        if any(pt in slots for _n, pt in win) and not self.is_blocked(CHEST_BLOCK_ALL):
            self.chest_target = None
            self.block(CHEST_BLOCK_ALL, FLIP_BLOCK, '活锁: 宝箱格点了没进展')

    def step(self):
        """跑一轮: 点色定页(零 OCR) -> 只有声明要读字的页才 OCR 本页 ROI -> 动作.
        返回 (page, acted, ocr_ran)"""
        self.ensure_window_size()
        img = self.vision.grab()
        self._text_done = False
        # 0) 看广告窗口开着 -> 这一轮只归它管: 不定页、不跑 OCR、不乱点(见 _ad_tick)
        if self._ad_until:
            r = self._ad_tick(img)
            if r in ('wait', 'acted'):
                self.f = ScreenFeature(img=img, boxes=[], joined='')
                self._soft_page, self._soft_streak = None, 0
                self._trans_streak = 0
                self._nohit_streak = 0
                self._zerohit_run = 0        # 广告窗口整段是我们的故意等待, 同样不计
                return None, r == 'acted', False
            # 'done'/'giveup' -> 窗口已关, 同一帧继续往下走正常路由(少白等一轮)
        # 1) 定页只看点色指纹: 实测 2ms 判完全表, 同样的轮次跑全图 OCR 要 675ms
        page, score, src = route_prints(self.pages, img, prefer=self.expected or ())
        soft = is_soft(src)
        defer = False
        self._trans_streak = getattr(self, '_trans_streak', 0)
        if page is None:
            # 2a) 转场闸门: 白烟/黑屏帧点色必然全表不中 -> 先用颜色认出来, 本轮直接跳过,
            #     一次 OCR 都不花(旧版在这里每帧白烧 675ms, 然后判成 unknown 去点遮罩)。
            trans, why = is_transition(img)
            if trans:
                self._trans_streak += 1
                self._zerohit_run = 0        # 转场帧认不出是应该的, 不计进 B 路
                self.f = ScreenFeature(img=img, boxes=[], joined='')
                self._soft_page, self._soft_streak = None, 0
                if self.shots:
                    self.shots -= 1
                    self._save_shot(img, 'other')
                # 黑屏赖着不走 = 不是转场, 是激励视频广告页 -> 开"看广告窗口"(看完才关)
                # 旧版(12:31)在这里直接点[关闭]: 撞上正在放广告的黑屏帧就会提前关闭 -> 奖励作废。
                # 现在交给 _ad_tick: 它自己会等状态药丸缩窄(=已获得奖励)或等满才动手。
                if why == '黑屏' and self._trans_streak >= BLANK_AD_AFTER and ad_close_pos(img) is not None:
                    if not self._ad_until:
                        logging.warning(f'[转场] 黑屏连续 {self._trans_streak} 帧 -> 不是转场, '
                                        f'是激励视频广告页 -> 开始看广告(放完自动关)')
                        self.start_ad_watch('撞见广告页')
                    r = self._ad_tick(img)
                    if r == 'acted':
                        self._trans_streak = 0
                        return None, True, False
                    if r == 'wait':
                        return None, False, False
                if self._trans_streak % 10 == 1:
                    logging.warning(f'[转场] {why}帧(连续 {self._trans_streak} 帧) '
                                    f'-> 本轮不动作, 也不花 OCR')
                return None, False, False
            self._trans_streak = 0
            # 2b) 点色连"差一个点"的软命中都没有 -> 要么真是没标指纹的页, 要么只是动画盖住了指纹点。
            #     先白等一帧(零成本): 动画帧下一帧必然恢复全中, 真页面才会连着两帧都不中, 那时才花全图 OCR。
            self._nohit_streak += 1
            self._zerohit_run += 1           # B 路: 不是转场却仍然点色零命中
            if self._nohit_streak < NO_HIT_OCR_AFTER:
                self.f = ScreenFeature(img=img, boxes=[], joined='')
                self._soft_page, self._soft_streak = None, 0
                logging.warning(f'[兜底] 点色零命中 第{self._nohit_streak}/{NO_HIT_OCR_AFTER}帧'
                                f'(上一帧={self.cur_page}) -> 本轮不动作, 也不花 OCR')
                return None, False, False
            # 2b2) 侧页出口(2026-09-03 08:36 竞技场晋级页教训): 这类页面内容随等级变,
            #      标指纹只能标在文字/地图美术上(= 下次改版又整片失效, lobby 刚踩过), 所以刻意不标。
            #      但[左下角青色返回箭头]本身就是点色可认的身份 + 出口 -> 直接交 unknown,
            #      不必再花 675ms 全图 OCR 去猜页面名字(猜出来也没有对应的动作层)。
            #      同样的道理适用于[新手引导模态]: 大白气泡 + 手套指向哪里就该点哪里,
            #      这件事用 1.8ms 的行游程就能判出来, 完全不需要 OCR。
            #      顺序: 引导模态 -> 弹窗关闭徽章 -> 兄弟页签 -> 侧页箭头。
            #      页签必须排在箭头前面: 真机实测卡牌页左下那颗青色卡牌图标会被
            #      back_arrow_pos 误认成返回箭头(84,960) —— 那正好是页签自己, 点它原地打转。
            #      关闭徽章排在页签前面: 弹窗是模态的, 压住的那层导航栏点了也没用
            #      (2026-09-03 语料对账: 全 820 帧里徽章帧只有 6 张(= 4 个不同弹窗), 且没有一张同时带
            #      页签/箭头/引导 —— 插在这里对既有三条路零影响)。
            guide = guide_targets(img)
            badge = None if guide else find_close_badge(img)
            on_tab = (not guide and badge is None and nav_present(img)
                      and nav_tab_cx(img) != NAV_LOBBY_TAB[0])
            arrow = None if (guide or on_tab or badge is not None) else back_arrow_pos(img)
            if on_tab or guide or arrow is not None or badge is not None:
                # 认出出口 -> 停在"已升级"水位: 下一帧还零命中就继续出手, 不必再白等一帧
                # (旧版这里把计数清 0, 结果引导页/页签页每隔一帧才动一次手)
                self._nohit_streak = NO_HIT_OCR_AFTER - 1
                ocr_ran = False          # 出口判据本身就是颜色, 一个字都不读
                self.f = ScreenFeature(img=img, boxes=[], joined='')
                self._soft_page, self._soft_streak = None, 0
                if on_tab:
                    logging.warning(f'[页签] 点色零命中但导航栏在(亮着的是 x={nav_tab_cx(img)})'
                                    f' -> 交 tab_other 点中间[战斗]回大厅, 不花 OCR')
                    page, score, src = self.page_by_name('tab_other'), 1.0, 'escape-tab'
                else:
                    if guide:
                        what, tag = '新手引导落点 %s' % (guide[:2],), 'guide'
                    elif badge is not None:
                        what, tag = '弹窗关闭徽章 %s' % (badge,), 'badge'
                    else:
                        what, tag = '返回箭头 %s' % (arrow,), 'arrow'
                    logging.warning(f'[侧页] 点色零命中但认出{what} -> 交 unknown, 不花 OCR')
                    page, score, src = self.pages[-1], 1.0, 'escape-' + tag
            else:
                # 2c) 连着两帧都没有任何指纹(新页面/被别的窗口遮挡) -> 才允许花一次全图 OCR。
                #     但真机第 28 轮证明这条兜底自己也会死循环: 开屏那张[秘境大冒险]弹窗点色
                #     整表不中, 又被 OCR 误判成 versus(act 永远 return False) -> 每 2 帧白烧一次
                #     675ms OCR、4 分钟零动作。连着 OCR_ESCALATE_AFTER 帧这样就说明这条路是死的:
                #     不再花 OCR, 直接交 unknown 走它的出口升级表(引导/徽章/箭头/页签 ->
                #     遮罩试探 -> 睡 45s), 至少日志看得见它在干什么, CPU 也不再烧在读字上。
                if self._ocr_zero >= OCR_ESCALATE_AFTER:
                    self._nohit_streak = NO_HIT_OCR_AFTER - 1   # 停在已升级水位, 每帧都能出手
                    self.f = ScreenFeature(img=img, boxes=[], joined='')
                    ocr_ran = False
                    self._soft_page, self._soft_streak = None, 0
                    logging.warning(f'[兜底] OCR 连续 {self._ocr_zero} 帧认出页面却零动作'
                                    f' -> 本轮不花全图 OCR, 交 unknown 走出口升级表')
                    page, score, src = self.pages[-1], 1.0, 'escape-ocrzero'
                else:
                    self._nohit_streak = 0
                    self.f, ocr_ran = self.vision.ocr(img, force=True)
                    self._text_done = True
                    page, score = detect_ocr(self.pages, self.f)
                    self._scan_modal_ok()   # 顺手记下弹窗回执键, 供 unknown 的升级表用
                    src = 'ocr' if page.name != self.pages[-1].name else 'unknown'
                    if src == 'ocr':
                        self._save_ocr_shot(page.name, img)   # 白捡一条待标语料
                    self.print_confirmed = False
                    self._soft_page, self._soft_streak = None, 0
        else:
            self._trans_streak = 0
            self._nohit_streak = 0
            self._zerohit_run = 0            # 点色认出来了 -> B 路归零
            self.print_confirmed = True
            src = 'print-' + src
            if not soft:
                self._soft_page, self._soft_streak = None, 0
            else:
                defer = not self._soft_stable(page.name)
            if defer:
                # 3a) 软命中头一帧: 页面身份认下了, 但这帧差点(动画/转场) -> 不动手也不跑 OCR
                self.f = ScreenFeature(img=img, boxes=[], joined='')
                ocr_ran = False
            elif page.act_needs_ocr:
                # 3) 动作层非读文字不可 -> 只裁本页 ROI, 且受该页 ocr_gap 节流
                fg = PAGE_CFG.get(page.name, PAGE_CFG['unknown'])
                self.f, ocr_ran = self.vision.ocr(
                    img, region=fg['roi'], scale=fg['scale'], min_gap=fg['ocr_gap'])
                self._text_done = True
            else:
                # 纯点色页: 整轮零 OCR, 只把帧交给动作层
                self.f = ScreenFeature(img=img, boxes=[], joined='')
                ocr_ran = False
        logging.info(f'[指纹] {page.name} {src} {score:.2f}')
        if defer:
            logging.warning(f'[指纹-软] {page.name} {score:.2f} 差<=1点·第{self._soft_streak}/'
                            f'{SOFT_ACT_AFTER}帧未稳 -> 本轮不动作, 也不花 OCR')
            return page, False, ocr_ran
        if soft:
            logging.warning(f'[指纹-软] {page.name} {score:.2f} 连续{self._soft_streak}帧 -> '
                            f'按稳定帧放行(依然不跑全图 OCR)')
        # --shots N: 取证模式, 每轮把当前帧存到 shots_live/dbg_*.png
        if self.shots:
            self.shots -= 1
            self._save_shot(self.f.img, page.name)
        # 转移校验
        if self.expected and page.name not in self.expected and page.name != 'unknown':
            logging.info(f'[转移] 预期{self.expected} 实际->{page.name}')
        if page.name != self.cur_page:
            logging.info(f'[状态] {self.cur_page} -> {page.name}')
            self.cur_page = page.name
            self.unknown_idle = 0
            self.expected = None
            # 每场战斗的棋盘都是新的: 进入战斗页必须清空"已点过的格子",
            # 否则 clicked_cells 只增不减, 打几场之后所有格子都被永久拉黑 -> 战斗页不再动手
            if page.name == 'battle':
                self.clicked_cells.clear()
                self.last_cell = 0
                # 「连续零价签」报警的记账只许在同一场内累加(真机 R42 跨场累积误报, 见 battle.py)
                from pages.battle import reset_blind_streak
                reset_blind_streak()
                # 技能按点格子累计次数释放(8/20/50), 进新战斗必须清零(2026-09-08)
                from pages.battle import reset_battle_clicks
                reset_battle_clicks()
        # 点色定完页、该读的字已经备好 -> 同一轮就能出手。
        # 旧版进页第一轮只补特征不动作(_skip_act), 每换一页白扔一轮, 已删除。
        acted = page.act(self)
        # "OCR 认出了页却动不了手" 的连续帧数: 只要这帧真动了手、或者是点色认出来的正常页
        # 就清零(那说明游戏状态在往前走); 只有 src=ocr 且零动作才累加。
        if acted or src.startswith('print'):
            self._ocr_zero = 0
        elif src == 'ocr':
            self._ocr_zero += 1
        if acted and page.next_pages and page.name != 'battle':
            self.expected = set(page.next_pages)
        elif not acted and page.name not in ('battle', 'matching', 'unknown'):
            self.expected = None
        return page, acted, ocr_ran

    # ---- 主循环 ----
    def run(self):
        self.ensure_window()
        self.apply_low_cpu()
        logging.info('=' * 60)
        logging.info(f'占城大师后台挂机 v3.1 max_battles={self.max_battles or "无限"} '
                     f'dry_run={self.dry_run} low_cpu={self.low_cpu} '
                     f'affinity={self.affinity_cores or "不限"}')
        logging.info(f'窗口={self.hwnd}  开始={datetime.now():%H:%M:%S}')
        while True:
            try:
                self.ensure_window()
                page, acted, _ = self.step()
                self.steps += 1
                self._flag_stuck(page, acted)
                self._flag_flip(page, acted)
                if self.max_steps and self.steps >= self.max_steps:
                    logging.info(f'达到目标轮数 {self.max_steps}, 结束')
                    break
                if self.max_battles and self.battles >= self.max_battles:
                    logging.info(f'达到目标场次 {self.max_battles}, 结束')
                    break
                fg = PAGE_CFG.get(self.cur_page, PAGE_CFG['unknown'])
                time.sleep(self.AD_TICK_POLL if self._ad_until else fg['poll'])
            except KeyboardInterrupt:
                logging.info('手动中断')
                break
            except Exception as e:
                logging.exception('循环异常: %s', e)
                time.sleep(8)
        logging.info('挂机结束')


_MUTEX = [None]        # 句柄必须活到进程结束, 否则互斥量会被回收

def acquire_single_instance(name='Local\\ZCDS_AutoBot'):
    """同一机器只允许一个 bot 在跑。

    不是怕占 CPU，是怕污染取证语料: 两个进程各自点各的格子，同一秒往
    shots_live/ 写两张状态码不同的大厅帧(实测 074833), 面板帧就再也归不清是谁点的。
    拿不到互斥量的场景(非 Windows / 权限受限)一律放行, 不把正常启动拦死。
    """
    try:
        import ctypes
        # use_last_error=True: windll.kernel32.GetLastError() 会被 ctypes 自己的调用抢掉
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        h = k.CreateMutexW(None, False, name)
        err = ctypes.get_last_error()
        if not h:
            return True
        _MUTEX[0] = h
        return err != 183        # ERROR_ALREADY_EXISTS(实测 GetLastError=183)
    except Exception:
        return True


def main():
    ap = argparse.ArgumentParser(description='占城大师自动挂机 (CPU 优化版)')
    ap.add_argument('--max-battles', type=int, default=0, help='打满 N 场后退出, 0=无限')
    ap.add_argument('--max-steps', type=int, default=0, help='最多跑 N 轮后退出, 0=不限 (dry-run 冒烟用)')
    ap.add_argument('--dry-run', action='store_true', help='只打印行为不真点')
    ap.add_argument('--shots', type=int, default=0, help='每轮存帧到 shots_live/dbg_*.png, 存 N 帧(取证用)')
    ap.add_argument('--ad-probe', type=int, default=0,
                    help='结算页没认到黄色[领取]时存帧到 scratch/adprobe/, 存 N 帧(0=关)')
    ap.add_argument('--no-ad-focus', action='store_true',
                    help='点[领取]前不把游戏窗口带到前台(默认会带: 后台可能被判定不可见而不出广告)')
    ap.add_argument('--no-low-cpu', action='store_true', help='不降低微信进程优先级')
    ap.add_argument('--affinity', type=int, default=0, help='微信进程限 N 个CPU核(0=不限)')
    ap.add_argument('--no-resize', action='store_true',
                    help=f'不自动把窗口调成指纹基准尺寸 {REF_SIZE[0]}x{REF_SIZE[1]}')
    ap.add_argument('--allow-multi', action='store_true',
                    help='允许和另一个 bot 并发(会把 shots_live/ 取证语料写乱, 只测试用)')
    a = ap.parse_args()
    if not (a.dry_run or a.allow_multi) and not acquire_single_instance():
        sys.stderr.write('已有另一个 auto_bot 在跑(互斥量 Local\\ZCDS_AutoBot), 本次不启动'
                       ' -- 并发会把取证帧写乱; 确要并发加 --allow-multi\n')
        return
    setup_logging()
    switched, note = g.enter_default_desktop()
    logging.info('[启动] 桌面上下文: %s', note)
    try:
        App(a.max_battles, a.dry_run, low_cpu=not a.no_low_cpu,
            affinity_cores=a.affinity, resize=not a.no_resize,
            max_steps=a.max_steps, shots=a.shots,
            ad_probe=a.ad_probe, ad_focus=not a.no_ad_focus).run()
    except Exception as e:
        logging.exception('启动失败: %s', e)
    # 双击 exe/pyw 运行时要停住让人看日志; 但管道/自动化下 stdin 可能仍是控制台,
    # 读不到行就安静退出, 别让 EOFError 把成功的跑批报成崩溃。
    if sys.stdin and sys.stdin.isatty():
        try:
            input('按回车退出...')
        except EOFError:
            pass


if __name__ == '__main__':
    main()
