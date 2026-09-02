# -*- coding: utf-8 -*-
"""未知页面兜底: 先认侧页返回箭头, 再截图 + 弹窗遮罩试探(上限3次/次)"""
import logging, os, time

from config import SHOTS_DIR

from .base import BACK_ARROW_POS, Page, is_back_arrow

MASK_POINTS = [(270, 860), (270, 300), (30, 300), (520, 300), (270, 200)]
MAX_IDLE = 8


class UnknownPage(Page):
    name = 'unknown'
    next_pages = ()
    # 本页没有点色指纹(只在 OCR 兜底分支出现, 那时 f 里本来就带文字),
    # 动作层用的返回箭头判据也是纯颜色 -> 不需要额外的 OCR。
    act_needs_ocr = False

    def detect(self, f):
        return 0.0            # 兜底页

    def act(self, ctx):
        # 0) 侧页(任务/商店/英雄)左下角有青色返回箭头 -> 点它回大厅, 比瞎点遮罩有效
        img = getattr(ctx.f, 'img', None)
        if img is not None and is_back_arrow(img):
            if not ctx.acted('back_arrow', gap=6.0):
                logging.info(f'[未知] 看到返回箭头, 退出侧页 {BACK_ARROW_POS}')
                ctx.click(*BACK_ARROW_POS)
            return True
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