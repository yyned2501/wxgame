# -*- coding: utf-8 -*-
"""未知页面兜底: 截图 + 弹窗遮罩试探(上限3次/次)"""
import logging, os, time

from config import SHOTS_DIR

from .base import Page

MASK_POINTS = [(270, 860), (270, 300), (30, 300), (520, 300), (270, 200)]
MAX_IDLE = 8


class UnknownPage(Page):
    name = 'unknown'
    next_pages = ()

    def detect(self, f):
        return 0.0            # 兜底页

    def act(self, ctx):
        ctx.unknown_idle += 1
        if ctx.unknown_idle >= MAX_IDLE:
            from datetime import datetime
            ts = datetime.now().strftime('%H%M%S')
            ctx.f.img.save(os.path.join(SHOTS_DIR, f'stuck_{ts}.png'))
            logging.warning(f'未知界面 x{ctx.unknown_idle}, 截图 shots/stuck_{ts}.png')
            # 试探关弹窗(每次最多3次遮罩)
            if ctx.unknown_idle < MAX_IDLE + 3:
                pt = MASK_POINTS[(ctx.unknown_idle - MAX_IDLE) % len(MASK_POINTS)]
                logging.info(f'[未知] 试探遮罩 {pt}')
                ctx.click(*pt)
            else:
                time.sleep(45)
                ctx.unknown_idle = 0
        return False