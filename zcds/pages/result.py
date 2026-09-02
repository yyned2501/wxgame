# -*- coding: utf-8 -*-
"""结算页: 领奖(失败/胜利礼包) -> 点击继续"""
import logging

from .base import Page


class ResultPage(Page):
    name = 'result'
    next_pages = ('lobby', 'claim_popup', 'vip_popup', 'matching', 'unknown')

    # 点色指纹: 由 tools/pick_print.py pick --label result 自动标定(勿手改)
    # 4 种形态 x 3 个十字单元(每单元 5 点, 共 15 判色点/形态), 任一形态全中即判为 result; 语料 13/13 全中 / 异页误中 0 / margin 0.27(异页最高只中 4/15 点) / 各形态覆盖 [3, 3, 7, 1] 帧
    prints = (
        (   # 形态: flow3_end1/flow3_r1/flow4_s0_result
            [184, 416, 0xFFFFFF], [186, 416, 0xC8C6C4], [182, 416, 0xFDFDFD],
            [184, 418, 0xA8A5A2], [184, 414, 0xFFFFFF], [340, 416, 0xFFFFFF],
            [342, 416, 0xAF8D40], [338, 416, 0xBD9129], [340, 418, 0xFFFFFF],
            [340, 414, 0xFDFDFD], [236, 824, 0xFFFFFF], [238, 824, 0xFFFFFF],
            [234, 824, 0x9C9C9C], [236, 826, 0xFFFFFF], [236, 822, 0xFFFFFF],
        ),
        (   # 形态: now/st_1/help_live
            [424, 780, 0xFFFFFF], [426, 780, 0xFAFAFA], [422, 780, 0xF0F0F0],
            [424, 782, 0xFFFFFF], [424, 778, 0xADA79F], [100, 812, 0xFFFFFF],
            [102, 812, 0x3C6F3B], [98, 812, 0xF4F4F4], [100, 814, 0xFFFFFF],
            [100, 810, 0x3F8C3E], [448, 836, 0xFFFFFF], [450, 836, 0xFEFEFE],
            [446, 836, 0x51347A], [448, 838, 0xE7E7E7], [448, 834, 0xF5F5F5],
        ),
        (   # 形态: watch_124652/watch_124654/watch_124656...
            [256, 416, 0xFFFFFF], [258, 416, 0xC7C6C4], [254, 416, 0xFCFCFC],
            [256, 418, 0xAAA7A3], [256, 414, 0xFFFFFF], [376, 732, 0xFFFFFF],
            [378, 732, 0xFDFDFD], [374, 732, 0xFFFFFF], [376, 734, 0xF2F2F2],
            [376, 730, 0xFFFFFF], [440, 732, 0xFFFFFF], [442, 732, 0xFAFAFA],
            [438, 732, 0xFBFBFB], [440, 734, 0xEFEFEF], [440, 730, 0xFFFFFF],
        ),
        (   # 形态: watch_124707
            [172, 192, 0xFFFFFF], [174, 192, 0xFFFFFF], [170, 192, 0xC4D3F8],
            [172, 194, 0xFFFFFF], [172, 190, 0xFEFFFF], [36, 412, 0xFFFFFF],
            [38, 412, 0xFFFFFF], [34, 412, 0xE4E4E4], [36, 414, 0x000000],
            [36, 410, 0x000000], [176, 412, 0xFFFFFF], [178, 412, 0xFFFFFF],
            [174, 412, 0x000000], [176, 414, 0xFFFFFF], [176, 410, 0xFFFFFF],
        ),
    )

    def detect(self, f):
        # x0.5 下"继续/维续"易读错, 多做几个容错
        if f.has('点击继续', '点击维续', '再来一局'):
            return 0.95
        if f.has('失败', '胜利') and f.has('MVP', '奖杯', '经验', '点击', '维续'):
            return 0.8
        return 0.0

    def act(self, ctx):
        f = ctx.f
        j = f.joined
        # 1) 礼包领取(检测到钻石就跳过)
        if f.has('领取') and '钻石' not in j:
            pts = f.find('领取')
            if pts and not ctx.acted('result_claim'):
                logging.info(f'[结算] 点 领取(礼包) {pts[0]}')
                ctx.click(*pts[0])
                return True
        # 2) 继续
        for kw in ('点击继续', '点击维续', '继续', '维续', '再来一局'):
            pts = f.find(kw)
            if pts:
                if not ctx.acted('result_continue'):
                    ctx.battles += 1
                    logging.info(f'[结算] 点 {kw} {pts[0]} (累计 {ctx.battles} 场)')
                    ctx.click(*pts[0])
                    return True
        return False