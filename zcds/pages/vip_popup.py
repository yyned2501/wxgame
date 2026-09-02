# -*- coding: utf-8 -*-
"""会员/礼包/优惠弹窗: 点X或遮罩关闭"""
import logging

from .base import Page

POPUP_KW = ('月卡', '特权', '立刻获取', '购买礼包', '超值', '续订', '优惠')
MASK_POINTS = [(270, 860), (270, 300), (30, 300), (520, 300), (270, 200)]


class VipPopupPage(Page):
    name = 'vip_popup'
    next_pages = ('lobby', 'unknown')

    # 点色指纹: 由 tools/pick_print.py pick --label vip_popup|vip_month 自动标定(勿手改)
    # 2 种形态 x 3 个十字单元(每单元 5 点, 共 15 判色点/形态), 任一形态全中即判为 vip_popup; 语料 5/5 全中 / 异页误中 0 / margin 0.13(异页最高只中 2/15 点) / 各形态覆盖 [4, 1] 帧
    prints = (
        (   # 来自 vip_popup
            [308, 312, 0xFFFFFF], [310, 312, 0xFFFFFF], [306, 312, 0xF5F6F5],
            [308, 314, 0xEBECEA], [308, 310, 0xFFFFFF], [196, 352, 0xFFFFFF],
            [198, 352, 0xFFFFFF], [194, 352, 0xFFFFFF], [196, 354, 0xFFFFFF],
            [196, 350, 0xFFFFFF], [324, 356, 0xFFFFFF], [326, 356, 0xFFFFFD],
            [322, 356, 0xFFFFFF], [324, 358, 0xFFFFFF], [324, 354, 0xFFFFFF],
        ),
        (   # 来自 vip_month
            [328, 244, 0xFFFFFF], [330, 244, 0xFFFFFF], [326, 244, 0xFAF8D9],
            [328, 246, 0xFFFFFF], [328, 242, 0xFBF6D6], [352, 408, 0xFFFFFF],
            [354, 408, 0xFFFFFF], [350, 408, 0xF8F5E9], [352, 410, 0xF1EDDD],
            [352, 406, 0xFEFEFB], [240, 536, 0xFFFFFF], [242, 536, 0xEAEAEA],
            [238, 536, 0xFDFDFD], [240, 538, 0xFFFFFF], [240, 534, 0xF9F9F9],
        ),
    )

    def detect(self, f):
        return 1.0 if f.has(*POPUP_KW) else 0.0

    def act(self, ctx):
        f = ctx.f
        # 钻石相关绝不确认
        if f.has('钻石'):
            logging.info('[弹窗] 含钻石, 只关闭')
        # X/关闭按钮
        for t in ('X', 'x', '×', '✕', '关闭', '取消'):
            for bx in f.find_boxes(t):
                if bx.cx < 250 or bx.cx > 300:      # 排除弹窗正中的文字
                    if not ctx.acted('vip_close'):
                        logging.info(f'[弹窗] 点 {t} {bx.center}')
                        ctx.click(*bx.center)
                        return True
        # 遮罩
        for pt in MASK_POINTS:
            if not ctx.acted('vip_mask'):
                logging.info(f'[弹窗] 点遮罩 {pt}')
                ctx.click(*pt)
                return True
        return False