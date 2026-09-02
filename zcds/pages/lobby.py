# -*- coding: utf-8 -*-
"""主页(lobby): 自动开宝箱 -> 开始玩家对战"""
import logging

from .base import (CHEST_BLOCK_ALL, Page, chest_slot_key, color_button,
                     color_pixels)

CHEST_SLOTS = [(109, 855), (220, 855), (331, 855), (441, 855)]
# ^ 2026-09-02 重标定: 旧值 (95,741)... 落在卡片顶边外(卡片实占 y738..879), 且 x 取自金币角标图标(偏左 14px),
#   真机 19 次点击全部落空. 现值 = 4 张卡片实测中心 x(109/220/331/441) + 操作按钮行 y=855(真机[开启]金色块 840..870)
CHEST_BAND = (695, 790)
# ^ 卡片[标题带](宝箱名/时长角标那一行). 判据本身不用它, 它只被 test_print_route.py [8] 拿去断言
#   [点色指纹不许罩住角标行] —— 角标颜色随宝箱档位变, 罩进去就成假指纹。

# ---- 动作层点色(2026-09-03 定案: 零 OCR) --------------------------------
# 四张宝箱卡片的操作按钮长得几乎一样, 但颜色构成完全不同, 数颜色比读字稳得多:
#   [开启]    = 整块纯金, 左边没东西挡   -> 按钮框黄 1235~1241, 左半黄 380~400
#   [[AD]加速] = 金按钮左边贴了张蓝票券图标 -> 按钮框黄  789~818, 左半黄只剩 123~133
#   [点击解锁] = 深色底白字(点它[免费]开箱) -> 按钮框黄 0, 白 143~176
#   空槽位     = 那一行没有按钮            -> 全 0
# 上面是 33 帧 lobby 语料 x 4 槽 = 132 个观测的实测区间, 逐帧与 OCR 真值核对过
# (复核脚本 scratch/scripts/slot_truth2.py, 输出 scratch/o_truth2.txt; 改阈值后重跑它即回归)。
# 阈值取法: 黄 >=500 才算有金按钮(实测 789 vs 0); 左半黄 >=250 判[开启](实测 380 vs 123);
#   白 >=120 判[点击解锁](实测 143~176, 而[开启]/[[AD]]按钮自带的白描边只有 70~100, 120 留安全边际)。
# 票券图标色 AAE4FF/6FC2F2/223F6B 与金色不搭, 所以只数金色就能把[开启]和[[AD]]分开。
# 注意 [[AD]] 那一格点下去 = 看激励视频加速, WATCH_ADS=False 时一律不点。
CHEST_BTN_COLOR = 0xFDCA33
CHEST_WHITE = 0xFFFFFF
CHEST_BTN_BAND = (838, 882)     # 按钮行 y 范围(标题行在 y810..826, 不许混进来)
CHEST_BTN_HALF = 45             # 卡片宽 ~111, 半宽 45 足够且不串邻列
CHEST_YELLOW_MIN = 500
CHEST_OPEN_LEFT_MIN = 250
CHEST_UNLOCK_WHITE_MIN = 120
# [玩家对战]按钮: 也是同一套金色, 语料 33 帧实测 n=6405~6539, 外接框中心恒为 (180,675)
PVP_BOX = (60, 640, 290, 720)
PVP_COLOR = 0xFDCA33
PVP_MIN_PX = 3000


class LobbyPage(Page):
    name = 'lobby'
    next_pages = ('chest_open', 'matching', 'chest_info', 'versus', 'claim_popup', 'ad_popup', 'vip_popup', 'diamond_popup')

    # 点色指纹: 由 tools/pick_print.py pick --label lobby --region 0,130,552,1006 自动标定(勿手改)
    # 候选区必须排除顶栏资源数字(y<130): 那些点的颜色随金币/钻石数值变化, 早先标定的 15 点全在顶栏, 换号即失效
    # 3 种形态 x 3 个十字单元(每单元 5 点, 共 15 判色点/形态), 任一形态全中即判为 lobby; 语料 35/35 全中 / 异页误中 0 / margin 0.20(异页最高只中 3/15 点) / 各形态覆盖 [35, 21, 14] 帧
    # 语料 25/25 全中 / 异页误中 0 / margin 0.20 / 各形态覆盖 [17, 4, 4] 帧
    prints = (
        (   # 形态: after_battle_btn/after_click/after_click2...
            [132, 194, 0xFFFFFF], [134, 194, 0x1059AC], [130, 194, 0xF5F5F5],
            [132, 196, 0xFFFFFF], [132, 192, 0xFBFBFB], [180, 194, 0xFFFFFF],
            [182, 194, 0xBFBFBF], [178, 194, 0x8C919B], [180, 196, 0xFFFFFF],
            [180, 192, 0xD6D6D6], [380, 638, 0xFFFFFF], [382, 638, 0xF6F1EF],
            [378, 638, 0xFAF7F6], [380, 640, 0xCFAFA1], [380, 636, 0xCDAB9B],
        ),
        (   # 形态: live_lobby/live_now2/lobby_clean/guide_live2
            [132, 194, 0xFFFFFF], [134, 194, 0x1059AC], [130, 194, 0xF5F5F5],
            [132, 196, 0xFFFFFF], [132, 192, 0xFBFBFB], [180, 194, 0xFFFFFF],
            [182, 194, 0xBFBFBF], [178, 194, 0x8C919B], [180, 196, 0xFFFFFF],
            [180, 192, 0xD6D6D6], [212, 266, 0xFFFFFF], [214, 266, 0x878795],
            [210, 266, 0x424362], [212, 268, 0xFFFFFF], [212, 264, 0x9B9BA7],
        ),
        (   # 形态: live_20260902_a/b/c/d (真机 2026-09-02 帧)
            [172, 194, 0xFFFFFF], [174, 194, 0xA9ACB5], [170, 194, 0xFFFFFF],
            [172, 196, 0xFFFFFF], [172, 192, 0x808C9B], [224, 194, 0xFFFFFF],
            [226, 194, 0xDEDEDE], [222, 194, 0xFFFFFF], [224, 196, 0x5E6F8F],
            [224, 192, 0x85909D], [492, 286, 0xFFFFFF], [494, 286, 0xD6D5D8],
            [490, 286, 0xD8D8DA], [492, 288, 0xD2D2D4], [492, 284, 0xF3F3F3],
        ),
    )

    act_needs_ocr = False   # 纯点色页: 主循环不为本页跑 OCR(定页仍优先看点色指纹, 与此无关)

    def detect(self, f):
        # 只有点色指纹全不中、回落到 OCR 判页时才会走到这里。
        # 注: 语料 33 帧里 OCR 一次都没读出[玩家对战]四个字(字体描边太细),
        #     旧版动作层正是靠 f.find('玩家对战') 点按钮, 所以它从来没点着过 —— 见 act()。
        return 1.0 if f.has('玩家对战') else 0.0

    @staticmethod
    def _slot_boxes(cx):
        """(整按钮框, 按钮左半框) —— 左半用来看有没有被蓝色票券图标挡住"""
        y0, y1 = CHEST_BTN_BAND
        return ((cx - CHEST_BTN_HALF, y0, cx + CHEST_BTN_HALF, y1), (cx - 34, 846, cx - 14, 874))

    def chest_states(self, img):
        """逐槽点色判状态 -> 4 字符码: o=[开启] u=[点击解锁] a=[[AD]加速] .=空槽"""
        out = []
        for cx, _cy in CHEST_SLOTS:
            btn, left = self._slot_boxes(cx)
            if color_pixels(img, btn, CHEST_BTN_COLOR) >= CHEST_YELLOW_MIN:
                out.append('o' if color_pixels(img, left, CHEST_BTN_COLOR) >= CHEST_OPEN_LEFT_MIN else 'a')
            elif color_pixels(img, btn, CHEST_WHITE) >= CHEST_UNLOCK_WHITE_MIN:
                out.append('u')
            else:
                out.append('.')
        return ''.join(out)

    def _ready_chests(self, img):
        """可点的宝箱槽位(左->右): o/u 是免费动作才点, a/. 一律不点。判据见 chest_states()"""
        st = self.chest_states(img)
        return [slot for slot, code in zip(CHEST_SLOTS, st) if code in 'ou']

    # 轮换游标(真机教训: 旧版死点 ready[0], 那一格若点了没跳转就永远卡在同一坐标)
    _chest_i = 0

    def act(self, ctx):
        img = ctx.f.img      # act_needs_ocr=False => ctx.f 只有图没有文字框, 别用 ctx.f.find()
        # 1) 开宝箱: 按钮是纯金[开启] 或 白字[点击解锁] = 免费动作才点
        #    再叠一层拉黑: 面板判出"这格要花钱"后 CHEST_PAID_BLOCK 秒内不再点它
        #    (真机 03:54: 那一格颜色不变 -> 大厅反复点 -> 反复关面板, 6 秒一圈刷了 16 次)
        st = self.chest_states(img)
        ready = self._ready_chests(img)
        # CHEST_BLOCK_ALL = 面板判过付费但说不清是哪一格(用户手动开的面板) -> 整行先别碰
        openable = ([] if ctx.is_blocked(CHEST_BLOCK_ALL)
                    else [s for s in ready if not ctx.is_blocked(chest_slot_key(s))])
        if ready and not openable:
            if not ctx.acted('chest_blocked_log', gap=60):
                logging.info(f'[主页] 宝箱状态 {st} {len(ready)} 格全在拉黑期(开箱要花钱) -> 跳过开箱去打对战')
        elif openable:
            i = self._chest_i % len(openable)
            sx, sy = openable[i]
            if not ctx.acted('chest_open'):
                self._chest_i = i + 1
                ctx.chest_target = chest_slot_key((sx, sy))
                logging.info(f'[主页] 宝箱状态 {st} 可开 {len(openable)} 格, 点第 {i + 1} 格 ({sx},{sy})')
                ctx.click(sx, sy)
                return True
        # 2) 玩家对战: 认那块金色按钮的外接框中心(旧版要 OCR 读[玩家对战], 读不到就永远不点)
        pos = color_button(img, PVP_BOX, PVP_COLOR, PVP_MIN_PX)
        if pos is not None and not ctx.acted('pvp_click'):
            logging.info(f'[主页] 点色命中玩家对战 {pos}')
            ctx.click(*pos)
            return True
        return False
