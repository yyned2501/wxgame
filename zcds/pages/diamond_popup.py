# -*- coding: utf-8 -*-
"""钻石确认弹窗: 只关闭, 绝不点确认(避免花钻石)

零 OCR 改造(2026-09-03 14:30): 旧版在"徽章没中 + OCR 也没读到字"时会盲点 (270,300)
兜底遮罩 —— 而这一页恰恰是**花钱确认框**, 正中那块区域可能就是[确认]按钮,
点错一次就是真金白银的钻石。现在改成: 认不出来就什么都不点(返回 False),
让主循环的[卡页]计数器存帧取证, 宁可空转也不赌。
"""
import logging

from .base import Page, find_close_badge

CANCEL_KW = ('取消', '关闭', 'X', 'x')


class DiamondPopupPage(Page):
    name = 'diamond_popup'
    next_pages = ('lobby', 'chest_info', 'claim_popup', 'unknown')
    act_needs_ocr = False     # 只关不确认, 关闭键是颜色徽章; 文字键才惰性补 OCR

    def detect(self, f):
        if f.has('钻石') and f.has('确认', '取消', '花费', '加速', '是否'):
            return 1.3
        return 0.0

    def act(self, ctx):
        logging.info('[钻石弹窗] 只关闭不确认')
        img = getattr(ctx.f, 'img', None)
        badge = find_close_badge(img) if img is not None else None
        if badge:                            # 红底白叉 X 是图形, OCR 读不到
            if not ctx.acted('diamond_badge', gap=8.0):
                logging.info(f'[钻石弹窗] 点关闭徽章 {badge}')
                ctx.click(*badge)
            return True
        # 颜色徽章没中, 才需要读字 -> 惰性升级(点色命中时默认不跑 OCR)
        for kw in CANCEL_KW:
            pts = ctx.need_text().find(kw)
            if pts:
                if not ctx.acted('diamond_cancel', gap=8.0):
                    logging.info(f'[钻石弹窗] 点 {kw} {pts[0]}')
                    ctx.click(*pts[0])
                return True
        logging.warning('[钻石弹窗] 关闭徽章和取消文字都没认出来 -> 什么都不点 '
                        '(花钱确认框盲点遮罩可能点到[确认])')
        return False
