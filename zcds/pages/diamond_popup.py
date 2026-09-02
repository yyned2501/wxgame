# -*- coding: utf-8 -*-
"""钻石确认弹窗: 只关闭, 绝不点确认(避免花钻石)"""
import logging

from .base import Page, find_close_badge


class DiamondPopupPage(Page):
    name = 'diamond_popup'
    next_pages = ('lobby', 'chest_info', 'claim_popup', 'unknown')
    act_needs_ocr = False     # 只关不确认, 关闭键是颜色徽章; 文字键才惰性补 OCR

    def detect(self, f):
        if f.has('钻石') and f.has('确认', '取消', '花费', '加速', '是否'):
            return 1.3
        return 0.0

    def act(self, ctx):
        f = ctx.f
        logging.info('[钻石弹窗] 只关闭不确认')
        img = getattr(f, 'img', None)
        badge = find_close_badge(img) if img is not None else None
        if badge:                            # 红底白叉 X 是图形, OCR 读不到
            if not ctx.acted('diamond_badge', gap=8.0):
                logging.info(f'[钻石弹窗] 点关闭徽章 {badge}')
                ctx.click(*badge)
            return True
        # 颜色徽章没中, 才需要读字 -> 惰性升级(点色命中时默认不跑 OCR)
        f = ctx.need_text()
        for kw in ('取消', '关闭', 'X', 'x'):
            pts = f.find(kw)
            if pts:
                ctx.click(*pts[0])
                return True
        # 兜底遮罩
        ctx.click(270, 300)
        return True