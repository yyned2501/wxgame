# -*- coding: utf-8 -*-
"""激励视频广告页: 结算页的"领取(礼包)"打开的就是它

真机 2026-09-02 23:24: result 点"领取" -> 广告页(左上"广告"69,89 / 右上"关闭"498,88 /
顶部"26秒后可获得奖励"194,89), 倒计时没走完就点"关闭" -> 弹挽留框
"暂未获得奖励是否继续观看视频"(277,484) + [放弃](179,609) [继续](374,609)。
本页策略: 只点"放弃"退出 —— 看满 30s 广告换一个小礼包不值得, 而且广告页会把主循环卡住。
没有点色指纹(广告创意每帧都变), 只靠 OCR 关键词定页。
"""
import logging

from .base import Page


class AdPopupPage(Page):
    name = 'ad_popup'
    next_pages = ('result', 'lobby', 'claim_popup', 'unknown')

    GIVEUP_KW = ('放弃',)
    MARK_KW = ('是否继续观看视频', '秒后可获得奖励', '继续观看')

    def detect(self, f):
        if f.has(*self.GIVEUP_KW):
            return 1.6
        if f.has(*self.MARK_KW):
            return 1.4
        return 0.0

    def act(self, ctx):
        f = ctx.f
        for kw in self.GIVEUP_KW:
            pts = f.find(kw)
            if pts:
                if not ctx.acted('ad_giveup', 5.0):
                    logging.info(f'[广告页] 点 {kw} {pts[0]} -> 放弃, 不点广告礼包')
                    ctx.click(*pts[0])
                    return True
        # 只有倒计时没走完(还没有挽留框): 什么都不点, 等广告自己结束或被手动放弃
        return False
