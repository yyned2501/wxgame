# -*- coding: utf-8 -*-
r"""开宝箱信息面板: 只点**免费**的[解锁], 其余(广告/钻石/宝石)一律关掉走人

真机 2026-09-02 23:34 实测(shots_live/peek_20260902_233423.png) + 语料 chestinfo/stuck_01xxxx:
  面板文字 = 铁制宝箱 / 竞技场2 / 包含: / 普通 稀有 史诗 传奇 / 金币 木材
             解锁(278,784)  20分(290,815)  X(469,168)
  1) 按钮下面那行"20分/5分"是**开箱所需时长**, 不是剩余倒计时; 解锁免费(点前点后顶栏资源不变)。
     旧版用 TIMER_RE=r'\d+\s*[分时秒]' 扫全文, 把它当冷却 -> 永远不开箱。
  2) 关闭 X 实测在 (470,167); 旧值 (478,115) 偏上 48px, 点下去什么都没发生,
     于是"判成忙 -> 关面板 -> 关不掉 -> 再判成忙"死循环 = shots/stuck_01xxxx 那 7 张卡死截图。
"""
import logging, re

from .base import Page, find_close_badge, is_countdown

# 候选按钮文字。注意: 真机 00:57 实测**同一位置写"开启"时它是付费按钮**(花 30 紫宝石立即开),
# "解锁"才是免费(启动 20 分钟倒计时), 所以这里只当候选, 最终由下面三道价格判据决定点不点。
BTN_RE = re.compile('解锁|开启|开宝箱|打开')
# 点它=看广告加速或花钻石: WATCH_ADS=False 时一律不点
PAID_RE = re.compile('钻石|AD|加速|立即|元')
# 花钱的明文信号: 按钮上或它旁边出现这些字样 -> 绝不点, 直接关面板走人
#   真机 2026-09-03 00:04 月卡弹窗上的 "￥68" 在 (278,788), 和免费开箱按钮 (278,785) 只差 3px,
#   一旦弹窗被误判成 chest_info, 旧代码就会替玩家花钱买月卡 -> 必须按"价格文字"兜底.
#   注: 紫宝石图标色 (222,62,246) **全图**到处都是(语料 77/89 帧都有), 所以不能拿整帧颜色判价;
#       但按钮正下方那条 33px 高的窄带是干净的(见下面 GEM_BAND 实测)。
PRICE_RE = re.compile(r'[¥￥] ?\d|\d+ ?元|钻石|宝石|充值')
PRICE_DX = 70                  # 只认按钮左右 70px / 上下 60px 内的价格文字
PRICE_DY = 60
# 2026-09-03 00:57 真机血泪: 面板按钮是[开启]时, 价格画成"紫宝石图标 + 裸数字 30",
#   OCR 只读得到 30 (没有单位), 上面 PRICE_RE 一条都不命中 -> 机器人真替玩家花掉 30 宝石(顶栏 114->84)。
#   免费按钮那行永远是带单位的时长(20分/5分), 所以再加两道判据:
#   a) 按钮**下方**带内出现纯数字 -> 判为价格; b) 同一条带里的紫宝石像素数 -> 判为价格。
PRICE_BARE_RE = re.compile(r'^\s*\d{1,4}\s*$')   # 裸数字(无 时/分/秒 单位)
GEM_BAND = (-45, 12, 45, 45)   # 相对按钮中心的带: x0,y0,x1,y1 (实测价格图标+数字就在这条带里)
GEM_MIN = 60                   # 带内紫宝石像素阈值; 实测免费 9 帧全 0 / 付费 1 帧 362
GEM_RGB = (170, 130, 150)      # (r>, g<, b>) 紫宝石 mask, 主色实测 (222,62,246)
PANEL_KW = ('木箱', '银箱', '金箱', '铁箱', '宝箱')
DESC_KW = ('包含', '坚固的', '坚国的', '解锁', '开宝箱', '开启')
CLOSE_POS = (470, 167)           # 标定坐标兜底(7 张语料 + 23:34 真机一致); 优先用 find_close_badge() 实测(468,165) 差 2px
BTN_FALLBACK = (278, 785)        # 中间黄色按钮兜底(真机 OCR: 解锁 x248..308 / y772..798)
PANEL_X0 = 100                   # 面板正文最小中心 x: 排除大厅左侧常驻横幅(活动倒计时 cx=24)


def gem_cost_pixels(img, cx, cy):
    """数按钮下半带里的紫宝石像素。免费按钮那带是橙色时钟图标, 实测 9 帧全 0; 付费帧 362。"""
    try:
        import numpy as np
        x0, y0, x1, y1 = cx + GEM_BAND[0], cy + GEM_BAND[1], cx + GEM_BAND[2], cy + GEM_BAND[3]
        a = np.asarray(img.convert('RGB').crop((max(x0, 0), max(y0, 0), x1, y1)), dtype=int)
        if a.ndim != 3 or a.size == 0:
            return 0
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        return int(((r > GEM_RGB[0]) & (g < GEM_RGB[1]) & (b > GEM_RGB[2])).sum())
    except Exception:
        return 0


class ChestInfoPage(Page):
    name = 'chest_info'
    next_pages = ('claim_popup', 'diamond_popup', 'vip_popup', 'lobby')

    # 点色指纹: 由 tools/pick_print.py pick --label chest_info 自动标定(勿手改)
    # 1 种形态 x 3 个十字单元(每单元 5 点, 共 15 判色点/形态), 任一形态全中即判为 chest_info; 语料 8/8 全中 / 异页误中 0 / margin 0.27(异页最高只中 4/15 点) / 各形态覆盖 [8] 帧
    #   2026-09-03 重标: 旧指纹是在"木箱"面板上标的, 真机铁制宝箱只中 9/15 -> 改用面板标题行(y166)+普稀史传行(y454), 木箱/铁箱 8 帧单组全中
    points = [
        [284, 166, 0xFFFFFF], [286, 166, 0xBFBFBF], [282, 166, 0xFFFFFF],
        [284, 168, 0xE7E7E7], [284, 164, 0xFFFFFF], [184, 454, 0xFFFFFF],
        [186, 454, 0x4E646A], [182, 454, 0xEDEDED], [184, 456, 0x999999],
        [184, 452, 0x5E6F73], [308, 454, 0xFFFFFF], [310, 454, 0xBABABA],
        [306, 454, 0xBDBDBD], [308, 456, 0xA0A0A0], [308, 452, 0xB1B1B1],
    ]

    def detect(self, f):
        if f.has(*PANEL_KW) and f.has(*DESC_KW):
            return 1.2
        return 0.0

    def act(self, ctx):
        f = ctx.f
        # 1) 免费按钮: 文字含 解锁/开启, 且自身不带倒计时、不带钻石/广告字样 -> 点它开始开箱
        btn = None
        for b in f.boxes:
            if not BTN_RE.search(b.text) or is_countdown(b.text) or PAID_RE.search(b.text):
                continue
            # 按钮自己或紧邻的文字框里带价格 = 这是付费按钮, 换下一个候选
            near = [o.text for o in f.boxes
                    if o is not b and abs(o.cx - b.cx) <= PRICE_DX
                    and abs(o.cy - b.cy) <= PRICE_DY and PRICE_RE.search(o.text)]
            # 裸数字只可能是"宝石图标+数字"的价格; 只看按钮**下方**(上方那排是普稀史传/奖励)
            bare = [o.text for o in f.boxes
                    if o is not b and PRICE_BARE_RE.match(o.text)
                    and abs(o.cx - b.cx) <= PRICE_DX and 0 <= o.cy - b.cy <= PRICE_DY]
            img = getattr(f, 'img', None)
            gems = gem_cost_pixels(img, b.cx, b.cy) if img is not None else 0
            if PRICE_RE.search(b.text) or near or bare or gems >= GEM_MIN:
                logging.info(f'[开宝箱] 按钮 {b.text} 判为付费'
                             f'(文字价格 {near} / 裸数字 {bare} / 带内宝石像素 {gems}), 拒点')
                continue
            btn = b
            break
        if btn is not None:
            if not ctx.acted('chest_open_btn'):
                logging.info(f'[开宝箱] 点免费按钮 {btn.text} {btn.center}')
                ctx.click(*btn.center)
            return True
        # 2) 没有免费按钮 = 要么真在倒计时(已经解锁过了), 要么只能花钱 -> 关掉面板回大厅
        #    只认面板正文区(x>=100)的倒计时: 大厅左上常驻"1天22时40分"也是倒计时, 但与开箱无关
        busy = [b for b in f.boxes if is_countdown(b.text) and b.cx >= PANEL_X0]
        if busy:
            logging.info(f'[开宝箱] 面板显示倒计时 {busy[0].text}, 关闭')
        else:
            logging.info('[开宝箱] 面板无免费按钮, 关闭面板')
        if not ctx.acted('chest_close', gap=12):
            img = getattr(f, 'img', None)
            pos = find_close_badge(img) if img is not None else None
            if pos is None:                    # 没认出彩标才退回标定坐标
                pos = CLOSE_POS
            logging.info(f'[开宝箱] 关闭 X -> {pos}')
            ctx.click(*pos)
        return True