# -*- coding: utf-8 -*-
r"""开宝箱信息面板: 只点**免费**的[解锁], 其余(广告/钻石/宝石)一律关掉走人

真机 2026-09-02 23:34 实测(shots_live/peek_20260902_233423.png) + 语料 chestinfo/stuck_01xxxx:
  面板文字 = 铁制宝箱 / 竞技场2 / 包含: / 普通 稀有 史诗 传奇 / 金币 木材
             解锁(278,784)  20分(290,815)  X(469,168)
  1) 按钮下面那行"20分/5分"是**开箱所需时长**, 不是剩余倒计时; 解锁免费(点前点后顶栏资源不变)。
     旧版用 TIMER_RE=r'\d+\s*[分时秒]' 扫全文, 把它当冷却 -> 永远不开箱。
  2) 关闭 X 实测在 (470,167); 旧值 (478,115) 偏上 48px, 点下去什么都没发生,
     于是"判成忙 -> 关面板 -> 关不掉 -> 再判成忙"死循环 = shots/stuck_01xxxx 那 7 张卡死截图。
  3) 2026-09-03 定案: 动作层改成**纯点色**(OCR 又慢又不准, 本页 ROI OCR 369ms/帧)。
     免费和付费按钮长得一模一样(同一张 #FDCA33 黄按钮, 外接框 y764..826 完全重合),
     唯一可靠区别是按钮内下半那条带里有没有紫宝石图标 —— 见下面 BTN_*/GEM_* 的 18 帧实测(免费 13 帧带内 0 / 付费 5 帧带内 362)。
     OCR 从此在本页只有"否决权": 帧上恰好带文字时, 读到价格字样就拒点; 文字永远不是放行的理由。
"""
import logging, re

from .base import (CHEST_BLOCK_ALL, CHEST_PAID_BLOCK, Page, color_button,
                     find_close_badge, is_countdown)

# 候选按钮文字。注意: 真机 00:57 实测**同一位置写"开启"时它是付费按钮**(花 30 紫宝石立即开),
# "解锁"才是免费(启动 20 分钟倒计时), 所以这里只当**否决词**, 不作为放行依据。
BTN_RE = re.compile('解锁|开启|开宝箱|打开')
# 点它=看广告加速或花钻石: 一律不点(付费护栏 + 广告下游面板从未采集)。
# 注意 config.WATCH_ADS 已 True, 但它只管结算页那颗黄色[领取]; 这里的[AD]入口还没接, 别照着开关名放开。
PAID_RE = re.compile('钻石|AD|加速|立即|元')
# 花钱的明文信号: 按钮上或它旁边出现这些字样 -> 绝不点, 直接关面板走人
#   真机 2026-09-03 00:04 月卡弹窗上的 "￥68" 在 (278,788), 和免费开箱按钮 (278,785) 只差 3px,
#   一旦弹窗被误判成 chest_info, 旧代码就会替玩家花钱买月卡 -> 必须按"价格文字"兜底.
#   注: 紫宝石图标色 (222,62,246) **全图**到处都是(语料 77/89 帧都有), 所以不能拿整帧颜色判价;
#       但按钮内下半那条 40px 高的窄带是干净的(见下面 GEM_BAND_BTN 实测)。
PRICE_RE = re.compile(r'[¥￥] ?\d|\d+ ?元|钻石|宝石|充值')
PRICE_DX = 70                  # 只认按钮左右 70px / 上下 60px 内的价格文字
PRICE_DY = 60
# 2026-09-03 00:57 真机血泪: 面板按钮是[开启]时, 价格画成"紫宝石图标 + 裸数字 30",
#   OCR 只读得到 30 (没有单位), 上面 PRICE_RE 一条都不命中 -> 机器人真替玩家花掉 30 宝石(顶栏 114->84)。
#   免费按钮那行永远是带单位的时长(20分/5分), 所以再加一道判据:
#   带内出现纯数字 -> 判为价格(点色那条带判据更硬, 见 GEM_MIN)。
PRICE_BARE_RE = re.compile(r'^\s*\d{1,4}\s*$')   # 裸数字(无 时/分/秒 单位)
# 旧版按 OCR 文本框中心量的带(保留给回归脚本对照); 新代码用 GEM_BAND_BTN(按点色锚点量)
GEM_BAND = (-45, 12, 45, 45)
GEM_BAND_BTN = (-50, 0, 50, 40)   # 相对**点色找到的**黄按钮中心(实测恒为 275,795):
#                                 按钮外接框 y764..826 => 这条带就是按钮内下半
GEM_MIN = 60                   # 带内紫宝石像素阈值; 18 帧实测 免费=0(13帧) / 付费=362(5帧)
GEM_RGB = (170, 130, 150)      # (r>, g<, b>) 紫宝石 mask, 主色实测 (222,62,246)
PANEL_KW = ('木箱', '银箱', '金箱', '铁箱', '宝箱')
DESC_KW = ('包含', '坚固的', '坚国的', '解锁', '开宝箱', '开启')
CLOSE_POS = (470, 167)           # 标定坐标兜底(7 张语料 + 23:34 真机一致); 优先用 find_close_badge() 实测(468,165) 差 2px
BTN_FALLBACK = (278, 785)        # 中间黄色按钮兜底(真机 OCR: 解锁 x248..308 / y772..798)
PANEL_X0 = 100                   # 面板正文最小中心 x: 排除大厅左侧常驻横幅(活动倒计时 cx=24)


def gem_cost_pixels(img, cx, cy, band=None):
    """数按钮内下半那条带里的紫宝石像素。免费 13 帧实测全 0; 付费 5 帧恒 362(阈值 60)。"""
    try:
        import numpy as np
        x0, y0, x1, y1 = (band or GEM_BAND_BTN)
        x0, y0, x1, y1 = cx + x0, cy + y0, cx + x1, cy + y1
        a = np.asarray(img.convert('RGB').crop((max(x0, 0), max(y0, 0), max(x1, 1), max(y1, 1))), dtype=int)
        if a.ndim != 3 or a.size == 0:
            return 0
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        return int(((r > GEM_RGB[0]) & (g < GEM_RGB[1]) & (b > GEM_RGB[2])).sum())
    except Exception:
        return 0


class ChestInfoPage(Page):
    name = 'chest_info'
    next_pages = ('claim_popup', 'diamond_popup', 'vip_popup', 'lobby')

    # 点色指纹: 由 scratch/scripts/ci_units4.py + ci_units5.py 自动标定(勿手改)
    # 1 种形态 x 3 个十字单元(每单元 5 点, 共 15 判色点/形态), 任一形态全中即判为 chest_info
    #   语料 22/22 全中 / 异页(245 帧)误中 0 / margin 0.2667 / 全库 844 帧里整条命中的 67 张**全是**开箱面板
    #   2026-09-04 真机第 29 轮重标(血泪): 上一版 15 个点全标在**文字像素**上 ——
    #     标题行 y166 的"青/铜/铁/木"字形 + 普稀史传行 y454 的字, 单元内跨 22 帧最大 dev 高达 255。
    #     真机换成[青铜宝箱]后标题那 5 个点里 2 个变成黑描边 -> 13/15=0.8667 -> 掉出软命中门槛
    #     -> 面板认不出 -> 出口链 find_close_badge 认出真 X (468,165) -> **机器人自己把面板关掉**
    #     -> 回大厅再点同一行 -> 16s 一圈无限活锁(一格箱都开不成, 永远进不了战斗)。
    #   本版判据: 只允许标在**与箱子种类无关的面板固定件**上, 且 22 帧单元级 dev<=12(实测 0/1/0):
    #     (132,202) 标题下的亮蓝横幅条 #0E7EFA(纯 chrome, 离标题字形 20px)
    #     (402,603) 传奇卡橙色卡面 #FEB218(4 张卡位恒定, 与卡上数字无关)
    #     ( 88,766) 面板左下紫色机身 #3A459C(纯 chrome, 离黄按钮 100px)
    #   复验: python -X utf8 scratch\scripts\ci_eval.py "[[132,202],[402,603],[88,766]]"
    points = [
        [132, 202, 0x0E7EFA], [134, 202, 0x0D7DFA], [130, 202, 0x0D7DFA],
        [132, 204, 0x0D7EFA], [132, 200, 0x0E7FFA], [402, 603, 0xFEB218],
        [404, 603, 0xFEB51A], [400, 603, 0xFEAD15], [402, 605, 0xFEAB13],
        [402, 601, 0xFEBC1C], [88, 766, 0x3A459C], [90, 766, 0x3A459C],
        [86, 766, 0x3A459C], [88, 768, 0x3A459C], [88, 764, 0x3A459C],
    ]

    # ---- 动作层点色(2026-09-03 定案: 整页零 OCR) --------------------------------
    # 免费/付费按钮是同一张黄按钮(外接框 193,764~357,826 完全重合, 中心恒 (275,795)),
    # 所以"有没有黄按钮"只证明"这里有个可点的开箱按钮", 判付费必须看带内颜色。
    BTN_BOX = (120, 730, 440, 840)   # 黄按钮搜索框(面板正文下半部, 不含顶栏资源图标)
    BTN_YELLOW = 0xFDCA33
    BTN_MIN_PX = 2000                # 18 帧实测 npx 7655~8061, 门槛留 3.8 倍余量
    act_needs_ocr = False            # 纯点色页: 主循环不为本页跑 OCR

    def detect(self, f):
        if f.has(*PANEL_KW) and f.has(*DESC_KW):
            return 1.2
        return 0.0

    # ---- OCR 只有否决权(帧上恰好带文字时才看, 绝不靠它放行) ----
    @staticmethod
    def text_veto(f, cx, cy):
        """返回否决理由(空串=不否决)。价格字样/裸数字/倒计时都算否决。"""
        boxes = getattr(f, 'boxes', None) or ()
        if not boxes:
            return ''
        for b in boxes:
            if PRICE_RE.search(b.text):
                if abs(b.cx - cx) <= PRICE_DX and abs(b.cy - cy) <= PRICE_DY:
                    return '价格文字 %r' % b.text
            if PRICE_BARE_RE.match(b.text) and 0 <= b.cy - cy <= PRICE_DY \
                    and abs(b.cx - cx) <= PRICE_DX:
                return '按钮下方裸数字 %r' % b.text
            if b is not None and abs(b.cx - cx) <= PRICE_DX and abs(b.cy - cy) <= 26:
                if is_countdown(b.text) or PAID_RE.search(b.text):
                    return '按钮字样 %r' % b.text
        return ''

    def close_panel(self, ctx, img, why, paid=False):
        logging.info(f'[开宝箱] {why} -> 关闭面板')
        if paid:
            # 关完回大厅, 那一格颜色一模一样 -> 不拉黑就是死循环(真机 03:54 连刷 16 圈)
            key = getattr(ctx, 'chest_target', None) or CHEST_BLOCK_ALL
            ctx.chest_target = None
            if not ctx.is_blocked(key):
                ctx.block(key, CHEST_PAID_BLOCK, why)
        if ctx.acted('chest_close', gap=12):
            return True
        pos = find_close_badge(img) if img is not None else None
        if pos is None:                    # 没认出彩标才退回标定坐标
            pos = CLOSE_POS
        logging.info(f'[开宝箱] 关闭 X -> {pos}')
        ctx.click(*pos)
        return True

    def act(self, ctx):
        img = getattr(ctx.f, 'img', None)
        if img is None:
            logging.warning('[开宝箱] 没有帧数据, 本轮不动作')
            return False
        # 1) 点色找中间那颗黄色开箱按钮(免费/付费都是它)
        btn = color_button(img, self.BTN_BOX, self.BTN_YELLOW, min_px=self.BTN_MIN_PX)
        if btn is None:
            return self.close_panel(ctx, img, '没看到黄色开箱按钮(广告/已开箱/别的版式)')
        cx, cy = btn
        # 2) 付费判据 A(主): 按钮内下半带里的紫宝石像素 —— 18 帧实测 0 vs 362, 隔着整个量程
        gems = gem_cost_pixels(img, cx, cy)
        if gems >= GEM_MIN:
            return self.close_panel(ctx, img, f'按钮带内宝石像素 {gems}>={GEM_MIN} = 要花钱', paid=True)
        # 3) 付费判据 B(附加否决): 这帧要是本来就带文字(别的页跑过 OCR), 读到价格也拒点
        veto = self.text_veto(ctx.f, cx, cy)
        if veto:
            return self.close_panel(ctx, img, 'OCR 否决: ' + veto, paid=True)
        # 4) 免费 -> 点它开始开箱
        if not ctx.acted('chest_open_btn'):
            logging.info(f'[开宝箱] 点色命中免费按钮 ({cx},{cy}) 带内宝石像素 {gems}')
            ctx.click(cx, cy)
        return True
