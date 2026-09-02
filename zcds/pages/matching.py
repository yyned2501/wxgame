# -*- coding: utf-8 -*-
"""匹配页: 正在寻找对手, 等待"""
from .base import Page


class MatchingPage(Page):
    name = 'matching'
    next_pages = ('versus', 'battle', 'unknown')
    act_needs_ocr = False     # 匹配页只等待, 从不动作 -> 不必为它跑 OCR
    # 点色指纹: 由 tools/pick_print.py pick --label matching 自动标定(勿手改)
    # 1 种形态 x 4 个十字单元(每单元 5 点, 共 20 判色点/形态), 任一形态全中即判为 matching; 语料 4/4 全中 / 异页误中 0 / margin 0.35(异页最高只中 7/20 点) / 各形态覆盖 [4] 帧
    points = [
        [172, 168, 0xFFFFFF], [174, 168, 0xFFFFFF], [170, 168, 0xC4C4C4],
        [172, 170, 0xFFFFFF], [172, 166, 0x737373], [276, 168, 0xFFFFFF],
        [278, 168, 0xFFFFFF], [274, 168, 0x989898], [276, 170, 0xFFFFFF],
        [276, 166, 0xFFFFFF], [328, 168, 0xFFFFFF], [330, 168, 0xFFFFFF],
        [326, 168, 0xFFFFFF], [328, 170, 0xFFFFFF], [328, 166, 0x7E7E7E],
        [216, 180, 0xFFFFFF], [218, 180, 0xFFFFFF], [214, 180, 0xFFFFFF],
        [216, 182, 0xFEFEFE], [216, 178, 0xFFFFFF],
    ]
    def detect(self, f):
        return 0.8 if f.has('正在寻找', '匹配中') else 0.0

    def act(self, ctx):
        return False        # 只等待, 不动作