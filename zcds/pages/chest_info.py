# -*- coding: utf-8 -*-
"""开宝箱页面: 中间黄色按钮[开宝箱/解锁] -> 点它开箱; 钻石提示则跳过"""
import logging, re

from .base import Page

TIMER_RE = re.compile(r'\d+\s*[分时秒]')
PANEL_KW = ('木箱', '银箱', '金箱', '铁箱', '宝箱')
DESC_KW = ('包含', '坚固的', '解锁', '开宝箱', '开启')
CLOSE_POS = (478, 115)          # 面板右上角关闭X
BTN_FALLBACK = (249, 771)       # 中间黄色按钮兜底位置


class ChestInfoPage(Page):
    name = 'chest_info'
    next_pages = ('claim_popup', 'diamond_popup', 'vip_popup', 'lobby')

    # 点色指纹: 由 tools/pick_print.py pick --label chest_info 自动标定(勿手改)
    # 1 种形态 x 3 个十字单元(每单元 5 点, 共 15 判色点/形态), 任一形态全中即判为 chest_info; 语料 7/7 全中 / 异页误中 0 / margin 0.27(异页最高只中 4/15 点) / 各形态覆盖 [7] 帧
    points = [
        [284, 156, 0xFFFFFF], [286, 156, 0xFFFFFF], [282, 156, 0xFFFFFF],
        [284, 158, 0xFFFFFF], [284, 154, 0x555555], [192, 452, 0xFFFFFF],
        [194, 452, 0x414141], [190, 452, 0xA9A9A9], [192, 454, 0xFFFFFF],
        [192, 450, 0xFFFFFF], [292, 452, 0xFFFFFF], [294, 452, 0xF5F5F5],
        [290, 452, 0xF7F7F7], [292, 454, 0xFAFAFA], [292, 450, 0xFFFFFF],
    ]

    def detect(self, f):
        if f.has(*PANEL_KW) and f.has(*DESC_KW):
            return 1.2
        return 0.0

    def act(self, ctx):
        f = ctx.f
        # 还没就绪(带倒计时): 不点解锁(避免误花钻石), 关掉面板
        if TIMER_RE.search(f.joined):
            if not ctx.acted('chest_busy_close', gap=20):
                logging.info('[开宝箱] 面板有倒计时(未就绪), 关闭')
                ctx.click(*CLOSE_POS)
            return True
        # 检测到钻石: 不开(跳过)
        if f.has('钻石'):
            logging.info('[开宝箱] 检测到钻石提示, 跳过')
            ctx.click(*CLOSE_POS)
            return True
        # 点黄色开启按钮(解锁/开宝箱/开启/打开)
        for kw in ('开宝箱', '解锁', '开启', '打开'):
            pts = f.find(kw)
            if pts:
                if not ctx.acted('chest_open_btn'):
                    logging.info(f'[开宝箱] 点按钮 [{kw}] {pts[0]}')
                    ctx.click(*pts[0])
                    return True
        # 兜底: 中间黄色按钮
        if not ctx.acted('chest_open_btn'):
            logging.info(f'[开宝箱] 兜底点中间按钮 {BTN_FALLBACK}')
            ctx.click(*BTN_FALLBACK)
            return True
        return False