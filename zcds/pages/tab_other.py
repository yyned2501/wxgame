# -*- coding: utf-8 -*-
"""底部一级导航栏上的"兄弟页签"页(商店/卡牌/城堡/排名) —— 出口: 点最中间的[战斗]

为什么不给这 4 页各标一个指纹: 它们的内容全随账号进度变(商店货架/卡牌列表/排行榜),
标指纹就只能标在文字或活动美术上 —— 那是 lobby 刚踩过的坑(改版即整片失效)。
但这 4 页有一件事是恒定的: 底下那条导航栏在, 而中间那个页签(战斗)就是大厅。
所以本页只做一件事 —— 认出"我在某个兄弟页签上", 然后点回大厅。零 OCR。

真机 2026-09-03 10:12: 新手引导走完落在商店页, 是用户手动点了最中间的页签才回的大厅;
10:20 又停在排名页。这一步脚本必须自己会。
"""
import logging
import time

from .base import NAV_LOBBY_TAB, Page, nav_present, nav_tab_cx


class TabOtherPage(Page):
    name = 'tab_other'
    next_pages = ('lobby',)
    act_needs_ocr = False        # 纯点色页: 主循环不许为本页跑 OCR
    points = ()                  # 故意不标指纹 —— 本页只由"导航栏在+大厅指纹没中"推出
    prints = ()

    GAP = 2.5                    # 点一次页签没立刻回大厅 -> 隔 2.5s 再补点, 别每帧狂点
    _last = 0.0

    def detect(self, f):
        return 0.0               # 不参与文字猜页

    def act(self, ctx):
        img = getattr(ctx.f, 'img', None)
        if img is None or not nav_present(img):
            return False
        cx = nav_tab_cx(img)
        if cx == NAV_LOBBY_TAB[0]:
            # 中间页签本来就亮着 => 这就是大厅, 只是这一帧指纹被动画吃了 -> 别乱点
            return False
        now = time.time()
        if now - self._last < self.GAP:
            return False
        self._last = now
        logging.info(f'[页签] 亮着的是 x={cx}(非中间) -> 点[战斗]{NAV_LOBBY_TAB} 回大厅')
        ctx.click(*NAV_LOBBY_TAB)
        return True
