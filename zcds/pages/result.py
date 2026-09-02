# -*- coding: utf-8 -*-
"""结算页: 领奖(失败/胜利礼包) -> 点击继续"""
import logging

from config import WATCH_ADS

from .base import Page


class ResultPage(Page):
    name = 'result'
    next_pages = ('lobby', 'claim_popup', 'ad_popup', 'vip_popup', 'matching', 'unknown')
    # 点色指纹: 由 tools/pick_print.py pick --label result 自动标定(勿手改)
    # 5 个十字单元(每单元 5 点, 共 25 判色点), 全中即判为 result; 语料 16/16 全中 / 异页误中 0 / margin 0.12 / 各形态覆盖 [16] 帧
    points = [
        [416, 188, 0xB7CBF9], [418, 188, 0x4463B2], [414, 188, 0x94ACEA],
        [416, 190, 0x839CDC], [416, 186, 0xB4C7F4], [356, 232, 0xB2C3F4],
        [358, 232, 0x5974BB], [354, 232, 0x87A2E4], [356, 234, 0xB1C3F4],
        [356, 230, 0xB1C4F4], [300, 316, 0x88DAFE], [302, 316, 0x85D7FE],
        [298, 316, 0x86CAFD], [300, 318, 0x80B5FE], [300, 314, 0x4565B9],
        [252, 324, 0x8DDFF2], [254, 324, 0x94D5F7], [250, 324, 0x8BE1F3],
        [252, 326, 0x8CBAFF], [252, 322, 0x5A74B7], [136, 192, 0xACC0F1],
        [138, 192, 0x97AFEB], [134, 192, 0x4463B7], [136, 194, 0x8198D3],
        [136, 190, 0xB3C7F7],
    ]
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
        # 1) 礼包领取: 真机 23:24 证实"领取"打开的是激励视频广告页(pages/ad_popup.py),
        #    WATCH_ADS=False 时不点, 直接走"点击继续"
        if WATCH_ADS and f.has('领取') and '钻石' not in j:
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