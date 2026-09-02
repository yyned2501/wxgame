# -*- coding: utf-8 -*-
"""主页(lobby): 自动开宝箱 -> 开始玩家对战"""
import logging, re

from .base import Page

CHEST_SLOTS = [(95, 741), (202, 741), (317, 741), (428, 741)]
CHEST_BAND = (695, 790)
TIMER_RE = re.compile(r'\d+\s*[分时秒]')


class LobbyPage(Page):
    name = 'lobby'
    next_pages = ('matching', 'chest_info', 'claim_popup', 'vip_popup', 'diamond_popup')

    # 点色指纹: 由 tools/pick_print.py pick --label lobby 自动标定(勿手改)
    # 3 种形态 x 3 个十字单元(每单元 5 点, 共 15 判色点/形态), 任一形态全中即判为 lobby; 语料 21/21 全中 / 异页误中 0 / margin 0.13(异页最高只中 2/15 点) / 各形态覆盖 [17, 20, 1] 帧
    prints = (
        (   # 形态: after_battle_btn/after_click/after_click2...
            [324, 96, 0xFFFFFF], [326, 96, 0xE6E6E8], [322, 96, 0x76748B],
            [324, 98, 0x55526D], [324, 94, 0xACABB3], [504, 96, 0xFFFFFF],
            [506, 96, 0xFFFFFF], [502, 96, 0xA4A3AA], [504, 98, 0x262143],
            [504, 94, 0x9A9AA2], [88, 108, 0xFFFFFF], [90, 108, 0x8B8A9C],
            [86, 108, 0x53506E], [88, 110, 0xFFFFFF], [88, 106, 0x8D8B9D],
        ),
        (   # 形态: live_lobby/live_now2/lobby_clean
            [324, 96, 0xFFFFFF], [326, 96, 0xE6E6E8], [322, 96, 0x76748B],
            [324, 98, 0x55526D], [324, 94, 0xACABB3], [416, 96, 0xFFFFFF],
            [418, 96, 0x52506A], [414, 96, 0xF2F2F3], [416, 98, 0x1F1A45],
            [416, 94, 0xFDFDFD], [504, 96, 0xFFFFFF], [506, 96, 0xFFFFFF],
            [502, 96, 0xA4A3AA], [504, 98, 0x262143], [504, 94, 0x9A9AA2],
        ),
        (   # 形态: guide_live2
            [332, 96, 0xFFFFFF], [334, 96, 0xFFFFFF], [330, 96, 0x94939E],
            [332, 98, 0x28244B], [332, 94, 0xACACB3], [504, 96, 0xFFFFFF],
            [506, 96, 0xFFFFFF], [502, 96, 0xA4A3AA], [504, 98, 0x262143],
            [504, 94, 0x9A9AA2], [92, 112, 0xFFFFFF], [94, 112, 0x555367],
            [90, 112, 0x95949F], [92, 114, 0x6E6C7C], [92, 110, 0xA1A1AA],
        ),
    )

    def detect(self, f):
        return 1.0 if f.has('玩家对战') else 0.0

    def _ready_chests(self, f):
        """槽位无倒计时文字 => 视为可开"""
        timers = [b for b in f.boxes
                  if CHEST_BAND[0] <= b.cy <= CHEST_BAND[1] and TIMER_RE.search(b.text)]
        ready = []
        for sx, sy in CHEST_SLOTS:
            if any(abs(b.cx - sx) < 45 for b in timers):
                continue
            ready.append((sx, sy))
        return ready

    def act(self, ctx):
        f = ctx.f
        # 1) 开宝箱(槽位无倒计时)
        ready = self._ready_chests(f)
        if ready:
            sx, sy = ready[0]
            if not ctx.acted('chest_open'):
                logging.info(f'[主页] 宝箱就绪, 点槽位 ({sx},{sy})')
                ctx.click(sx, sy)
                return True
        # 2) 玩家对战
        pts = f.find('玩家对战')
        if pts:
            if not ctx.acted('pvp_click'):
                logging.info(f'[主页] 点 玩家对战 {pts[0]}')
                ctx.click(*pts[0])
                return True
        return False