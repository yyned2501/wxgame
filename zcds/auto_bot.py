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
from datetime import datetime

import game_utils as g
from colorprint import REF_SIZE
from config import PAGE_CFG
from vision import Vision, ScreenFeature
from pages import ALL_PAGES
from pages.base import (AD_PILL_LEFT_TOL, AD_PILL_LOW_HOLD, AD_PILL_SHRINK, AD_PILL_SHRINK_PCT,
                        NAV_LOBBY_TAB, ad_close_pos, ad_pill_state, back_arrow_pos, detect_ocr,
                        find_close_badge, guide_targets, is_soft, is_transition, nav_present,
                        nav_tab_cx, route_prints)

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


def setup_logging():
    os.makedirs(os.path.join(ROOT, 'shots'), exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE, encoding='utf-8')])


class App:
    """主循环 + 页面执行上下文(ctx)"""

    def __init__(self, max_battles=0, dry_run=False, low_cpu=True, affinity_cores=0,
                 resize=True, max_steps=0, shots=0):
        self.max_battles = max_battles
        self.dry_run = dry_run
        self.low_cpu = low_cpu
        self.affinity_cores = affinity_cores
        self.resize = resize             # 每轮把窗口钉回指纹基准尺寸
        self.max_steps = max_steps   # >0: 跑满 N 轮退出(dry-run 冒烟用)
        self.shots = shots      # >0: 每轮存帧 -> shots_live/dbg_*.png (取证用)
        self.steps = 0
        self._win_warn = 0
        self.hwnd = None
        self.vision = None
        self.pages = ALL_PAGES
        # 页面执行上下文
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
        self._stuck = 0                  # 卡页统计: 该页连续零动作轮数
        # 看广告窗口(2026-09-03 12:47 定案): _ad_until 非 0 = 窗口开着, 主循环交 _ad_tick 管
        self._ad_t0 = 0.0                # 本轮广告开始时刻
        self._ad_until = 0.0             # 窗口硬上限时刻(= 开始 + AD_WATCH_TOTAL)
        self._ad_pill_max = 0            # 本场广告左上状态药丸见过的最大右边界(判"放完了")
        self._ad_white_max = 0           # 第二把尺子: 本场药丸带内白像素峰值(=字数最多的那帧)
        self._ad_pill_left = None        # 峰值帧的药丸左边界, 用来识破"广告画面盖住顶栏"的假读数
        self._ad_low_t0 = 0.0            # 白像素开始持续偏低的时刻(0 = 当前不偏低)
        self._ad_pill = ()               # 最近一次药丸读数 (右边界, 白像素, 左边界), 只为播报用
        self._ad_logged = 0.0            # 上次"播放中"播报的时刻
        self._ad_seen = False            # 是否真见过广告 chrome(见过才允许等满全程)
        self._ad_closing = False         # 已点过[关闭], 正在确认它真的关掉了
        self._ad_close_t = 0.0
        self._ad_retry_at = 0.0

    # ---- 上下文工具(供页面调用) ----
    def click(self, x, y):
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
    AD_WATCH_MAX = 40.0       # 实拍倒计时 30s + 尾帧; 等满这么多秒就认定"放完了"
    AD_WATCH_TOTAL = 100.0    # 一条广告最多占用主循环这么久, 超了撒手(防死等)
    AD_CLOSE_RETRY = 3.0      # 点过[关闭]后每这么多秒复检: 还赖在广告页就再点一次
    AD_CLOSE_CONFIRM = 12.0   # 关闭动作最多盯这么久(正常下一帧就已经离开广告页)
    AD_NOT_AD_AT = 4.0        # 等了这么久还是"游戏自己的页" -> 认定根本没进广告, 撒手

    def start_ad_watch(self, why=''):
        """arm 看广告窗口: result 点完黄色[领取]后调用, 或主循环撞见广告页时调用"""
        now = time.time()
        self._ad_t0, self._ad_until = now, now + self.AD_WATCH_TOTAL
        self._ad_pill_max, self._ad_logged = 0, now
        self._ad_white_max, self._ad_pill_left, self._ad_low_t0, self._ad_pill = 0, None, 0.0, ()
        self._ad_seen, self._ad_closing = False, False
        self._ad_close_t = self._ad_retry_at = 0.0
        logging.info(f'[广告] 开始看广告({why}): 期间不定页/不跑 OCR/不点击; '
                     f'放完判据 = 状态药丸缩窄 或 等满 {self.AD_WATCH_MAX:.0f}s; '
                     f'最长 {self.AD_WATCH_TOTAL:.0f}s')

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
        # 2) 压根没进广告(点[领取]没命中 / 弹的是别的窗): 别把主循环锁死在这
        if (not self._ad_seen and waited >= self.AD_NOT_AD_AT
                and self._ad_page_hard(img)):
            logging.warning(f'[广告] 等了 {waited:.0f}s 认出的是游戏自己的页且始终没有广告顶栏 '
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
                    self._ad_pill_max = max(self._ad_pill_max, pr)
                    shrink = self._ad_pill_max - pr >= AD_PILL_SHRINK
                    if shrink:
                        how = f'药丸缩窄 {self._ad_pill_max}->{pr}'
                    elif wc <= self._ad_white_max * (1 - AD_PILL_SHRINK_PCT):
                        if not self._ad_low_t0:
                            self._ad_low_t0 = now
                        elif now - self._ad_low_t0 >= AD_PILL_LOW_HOLD:
                            shrink = True
                            how = (f'药丸字变少 {self._ad_white_max}->{wc}px 持续 '
                                   f'{now - self._ad_low_t0:.0f}s')
                    else:
                        self._ad_low_t0 = 0.0
            if waited >= self.AD_WATCH_MIN and (shrink or waited >= self.AD_WATCH_MAX):
                how = (how + ' = 已获得奖励') if shrink else f'等满 {self.AD_WATCH_MAX:.0f}s'
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

    def _ad_page_hard(self, img):
        """广告窗口里的"根本没在看广告"探针: 点色能**硬命中**某个已知页(2ms, 零 OCR) => 还留在游戏里"""
        page, _score, src = route_prints(self.pages, img, prefer=self.expected or ())
        return page is not None and not is_soft(src)

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
        if self.hwnd is None or not g.u32.IsWindow(self.hwnd):
            self.hwnd = g.find_game_window()
            if self.hwnd is None:
                raise RuntimeError('找不到游戏窗口, 请先打开 占城大师')
            self.vision = Vision(self.hwnd)   # 新引擎首轮必然 OCR, 不必再置标记
            self._win_warn = 0

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
        """卡页检测: 只报警 + 存帧取证, 绝不代替页面做任何点击"""
        if page is None or acted or page.name in STUCK_EXEMPT:
            self._stuck_page, self._stuck = None, 0
            return
        if page.name != self._stuck_page:
            self._stuck_page, self._stuck = page.name, 0
        self._stuck += 1
        if self._stuck != STUCK_AFTER:
            return
        img = getattr(self.f, 'img', None)
        if img is None:
            return
        d = os.path.join(ROOT, 'shots_live')
        os.makedirs(d, exist_ok=True)
        fn = 'stuck_%s_%s.png' % (page.name, time.strftime('%H%M%S'))
        try:
            img.save(os.path.join(d, fn))
            logging.warning('[卡页] %s 连续 %d 轮零动作 -> 存帧 shots_live/%s '
                            '(多半是撞上新页面没标指纹, 或按钮位置/颜色变了)',
                            page.name, self._stuck, fn)
        except Exception as e:
            logging.warning('[卡页] 存帧失败: %s', e)

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
                # 2c) 连着两帧都没有任何指纹(新页面/被别的窗口遮挡) -> 才允许花一次全图 OCR
                self._nohit_streak = 0
                self.f, ocr_ran = self.vision.ocr(img, force=True)
                self._text_done = True
                page, score = detect_ocr(self.pages, self.f)
                src = 'ocr' if page.name != self.pages[-1].name else 'unknown'
                if src == 'ocr':
                    self._save_ocr_shot(page.name, img)   # 白捡一条待标语料
                self.print_confirmed = False
                self._soft_page, self._soft_streak = None, 0
        else:
            self._trans_streak = 0
            self._nohit_streak = 0
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
        # 点色定完页、该读的字已经备好 -> 同一轮就能出手。
        # 旧版进页第一轮只补特征不动作(_skip_act), 每换一页白扔一轮, 已删除。
        acted = page.act(self)
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
                if self.max_steps and self.steps >= self.max_steps:
                    logging.info(f'达到目标轮数 {self.max_steps}, 结束')
                    break
                if self.max_battles and self.battles >= self.max_battles:
                    logging.info(f'达到目标场次 {self.max_battles}, 结束')
                    break
                fg = PAGE_CFG.get(self.cur_page, PAGE_CFG['unknown'])
                time.sleep(fg['poll'])
            except KeyboardInterrupt:
                logging.info('手动中断')
                break
            except Exception as e:
                logging.exception('循环异常: %s', e)
                time.sleep(8)
        logging.info('挂机结束')


def main():
    ap = argparse.ArgumentParser(description='占城大师自动挂机 (CPU 优化版)')
    ap.add_argument('--max-battles', type=int, default=0, help='打满 N 场后退出, 0=无限')
    ap.add_argument('--max-steps', type=int, default=0, help='最多跑 N 轮后退出, 0=不限 (dry-run 冒烟用)')
    ap.add_argument('--dry-run', action='store_true', help='只打印行为不真点')
    ap.add_argument('--shots', type=int, default=0, help='每轮存帧到 shots_live/dbg_*.png, 存 N 帧(取证用)')
    ap.add_argument('--no-low-cpu', action='store_true', help='不降低微信进程优先级')
    ap.add_argument('--affinity', type=int, default=0, help='微信进程限 N 个CPU核(0=不限)')
    ap.add_argument('--no-resize', action='store_true',
                    help=f'不自动把窗口调成指纹基准尺寸 {REF_SIZE[0]}x{REF_SIZE[1]}')
    a = ap.parse_args()
    setup_logging()
    g.enter_default_desktop()
    try:
        App(a.max_battles, a.dry_run, low_cpu=not a.no_low_cpu,
            affinity_cores=a.affinity, resize=not a.no_resize,
            max_steps=a.max_steps, shots=a.shots).run()
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
