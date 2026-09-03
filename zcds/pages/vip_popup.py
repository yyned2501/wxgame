# -*- coding: utf-8 -*-
"""会员/礼包/优惠弹窗: 只关闭, 绝不点任何购买/领取/续订按钮

真机 2026-09-03 00:03 修正(dry-run 复现): 关闭键是红底白叉**图形**, OCR 读不到 ->
旧版只找 'X'/'关闭' 关键字, 找不到就点遮罩, 而且每轮都点同一个 (270,860),
8 轮全在重复同一个无效点击, 月卡弹窗根本关不掉。
现在优先用 base.find_close_badge() 按颜色定位真正的 X(实测 15~20ms/帧, 94 帧 0 误报),
遮罩只作最后兜底并轮换点位。弹窗类页面一律"只关不确认", 含钻石字样时更不碰任何按钮。
"""
import logging

from .base import Page, find_close_badge

POPUP_KW = ('月卡', '特权', '立刻获取', '购买礼包', '超值', '续订', '优惠')
# 遮罩兜底点: 只挑面板外的空白, 压到宝箱行(838~882)的那个放最后
MASK_POINTS = [(270, 200), (30, 300), (520, 300), (270, 860)]


class VipPopupPage(Page):
    name = 'vip_popup'
    next_pages = ('lobby', 'levelup', 'unknown')
    _mask_i = 0
    act_needs_ocr = False     # 关闭键靠颜色定位(find_close_badge), 文字键才惰性补 OCR

    # 点色指纹: 由 tools/pick_print.py pick --label vip_popup|vip_month 自动标定(勿手改)
    # 2 种形态 x 3 个十字单元(每单元 5 点, 共 15 判色点/形态), 任一形态全中即判为 vip_popup; 语料 9/9 全中 / 异页误中 0 / margin 0.27(异页最高只中 4/15 点) / 各形态覆盖 [4, 5] 帧
    #   2026-09-03 重标第2组: 旧月卡指纹在真机 00:03 那帧只中 5/15(弹窗有动画), 改挑两帧都稳的文字行 y538
    prints = (
        (   # 来自 vip_popup
            [308, 312, 0xFFFFFF], [310, 312, 0xFFFFFF], [306, 312, 0xF5F6F5],
            [308, 314, 0xEBECEA], [308, 310, 0xFFFFFF], [196, 352, 0xFFFFFF],
            [198, 352, 0xFFFFFF], [194, 352, 0xFFFFFF], [196, 354, 0xFFFFFF],
            [196, 350, 0xFFFFFF], [324, 356, 0xFFFFFF], [326, 356, 0xFFFFFD],
            [322, 356, 0xFFFFFF], [324, 358, 0xFFFFFF], [324, 354, 0xFFFFFF],
        ),
        (   # 来自 vip_month(语料 st_2 + 真机 00:03 月卡弹窗)
            [112, 538, 0xFFFFFF], [114, 538, 0xFEFEFE], [110, 538, 0xFFFFFF],
            [112, 540, 0x9D82DC], [112, 536, 0x940B11], [216, 538, 0xFFFFFF],
            [218, 538, 0xA1A1A1], [214, 538, 0xFFFFFF], [216, 540, 0xF8F8F8],
            [216, 536, 0xECECEC], [272, 538, 0xFFFFFF], [274, 538, 0xEBEBEB],
            [270, 538, 0xBEBEBE], [272, 540, 0xF8F8F8], [272, 536, 0xFFFFFF],
        ),
    )

    # 锚点相对点色(2026-09-03): 这类奖励弹窗面板**位置随内容浮动**, 同一个月卡弹窗
    # 在 00:56 那批 badge 在 (455,461)、10:53 那批在 (459,545) —— 绝对坐标指纹必然对不上,
    # 于是每帧都要白跑一次全图 OCR(675ms)才认出弹窗。锚点 = find_close_badge 的红底白叉
    # 关闭徽章中心, 它左边那一排金币图标偏移固定(实测 11 帧完全一致), 5 点全中即认定本页。
    # 语料: 弹窗帧 11/11 全中; 248 张标注语料 + 576 张真机帧异页误中 0
    #   (ask_battle 这类弹窗徽章在 (464,307), 同偏移处是 0x592725/0xC3351C 的红底, 差得远)。
    # 5 点 < SOFT_MIN_PTS(8) -> 锚点指纹只允许全中, 不存在软命中误判。
    anchor_prints = (
        ((-30, 0, 0xFDD825), (-60, 0, 0xFED926), (-90, 0, 0xFEDA24),
         (-60, -20, 0xEFAA1F), (-90, -20, 0xEEAB22)),
    )

    def detect(self, f):
        return 1.0 if f.has(*POPUP_KW) else 0.0

    def act(self, ctx):
        f = ctx.f
        img = getattr(f, 'img', None)
        # 1) 红底白叉关闭徽章(真机实测: 特权弹窗(464,307) / 月卡弹窗(455,461))
        if img is not None:
            badge = find_close_badge(img)
            if badge:
                if not ctx.acted('vip_badge', gap=8.0):
                    logging.info(f'[弹窗] 点关闭徽章 {badge}')
                    ctx.click(*badge)
                return True
        # 2) 文字形态的关闭键(排除弹窗正中的文字) —— 颜色徽章没中才现补一次本页 OCR
        f = ctx.need_text()
        for t in ('X', 'x', '×', '✕', '关闭', '取消'):
            for bx in f.find_boxes(t):
                if bx.cx < 250 or bx.cx > 300:
                    if not ctx.acted('vip_close'):
                        logging.info(f'[弹窗] 点 {t} {bx.center}')
                        ctx.click(*bx.center)
                        return True
        # 3) 最后才点遮罩, 且轮换点位
        pt = MASK_POINTS[self._mask_i % len(MASK_POINTS)]
        self._mask_i += 1
        if not ctx.acted('vip_mask', gap=2.0):
            logging.info(f'[弹窗] 点遮罩 {pt}')
            ctx.click(*pt)
        return True
