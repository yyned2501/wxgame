# -*- coding: utf-8 -*-
"""匹配页: 正在寻找对手, 等待"""
from .base import Page


class MatchingPage(Page):
    name = 'matching'
    next_pages = ('battle', 'unknown')

    # 点色指纹: 由 tools/pick_print.py pick --label matching 自动标定(勿手改)
    # 1 种形态 x 3 个十字单元(每单元 5 点, 共 15 判色点/形态), 任一形态全中即判为 matching; 语料 1/1 全中 / 异页误中 0 / margin 0.20(异页最高只中 3/15 点) / 各形态覆盖 [1] 帧
    points = [
        [172, 168, 0xFFFFFF], [174, 168, 0xFFFFFF], [170, 168, 0xC4C4C4],
        [172, 170, 0xFFFFFF], [172, 166, 0x737373], [236, 168, 0xFFFFFF],
        [238, 168, 0xFFFFFF], [234, 168, 0xFFFFFF], [236, 170, 0xBEBEBE],
        [236, 166, 0xEBEBEB], [284, 168, 0xFFFFFF], [286, 168, 0x4D4D4F],
        [282, 168, 0xFFFFFF], [284, 170, 0xFFFFFF], [284, 166, 0x3F3F3F],
    ]

    def detect(self, f):
        return 0.8 if f.has('正在寻找', '匹配中') else 0.0

    def act(self, ctx):
        return False        # 只等待, 不动作