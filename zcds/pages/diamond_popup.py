# -*- coding: utf-8 -*-
"""钻石确认弹窗: 只关闭, 绝不点确认(避免花钻石)"""
import logging

from .base import Page


class DiamondPopupPage(Page):
    name = 'diamond_popup'
    next_pages = ('lobby', 'chest_info', 'claim_popup', 'unknown')

    def detect(self, f):
        if f.has('钻石') and f.has('确认', '取消', '花费', '加速', '是否'):
            return 1.3
        return 0.0

    def act(self, ctx):
        f = ctx.f
        logging.info('[钻石弹窗] 只关闭不确认')
        for kw in ('取消', '关闭', 'X', 'x'):
            pts = f.find(kw)
            if pts:
                ctx.click(*pts[0])
                return True
        # 兜底遮罩
        ctx.click(270, 300)
        return True