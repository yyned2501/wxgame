# -*- coding: utf-8 -*-
"""已获得奖励弹窗: 点关闭/确定"""
import logging

from .base import Page


class ClaimPopupPage(Page):
    name = 'claim_popup'
    next_pages = ('lobby', 'result', 'unknown')

    def detect(self, f):
        if f.has('已获得奖励', '获得奖励', '领取成功'):
            return 1.5
        return 0.0

    def act(self, ctx):
        for kw in ('关闭', '确定', '知道了'):
            pts = ctx.f.find(kw)
            if pts:
                if not ctx.acted('claim_close'):
                    logging.info(f'[领奖弹窗] 点 {kw} {pts[0]}')
                    ctx.click(*pts[0])
                    return True
        return False