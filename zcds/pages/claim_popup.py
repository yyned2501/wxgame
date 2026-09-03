# -*- coding: utf-8 -*-
"""已获得奖励弹窗: 只关闭, 不点任何领取/确认按钮

零 OCR 改造(2026-09-03 14:30 语料对账): 全 820 帧语料里这一页**一张帧都没有**
(真机日志从 00:00 到现在也从没把它定成当前页), 它只在"领完日常奖励"那种分支里出现,
所以标不出点色指纹。但出口不需要知道它是谁 —— 这类弹窗的关闭键都是同一套
红底白叉图形 chrome(vip_popup / 指南弹窗 / 装备详情弹窗实测一致), OCR 反而读不到字。
现在: act 先按颜色找关闭徽章(约 20ms), 命中就点它, 一个字都不读;
徽章也没中才惰性补一次本页 OCR 找文字按钮。
主循环那一侧还有一条更硬的兜底: 点色全表不中 + 认出关闭徽章 -> 直接交 unknown
(见 auto_bot.py 2b2 与 pages/unknown.py BADGE_OFFSETS), 连"这页叫什么"都不用猜。
"""
import logging

from .base import Page, find_close_badge

CLOSE_KW = ('关闭', '确定', '知道了')


class ClaimPopupPage(Page):
    name = 'claim_popup'
    next_pages = ('lobby', 'result', 'unknown')
    act_needs_ocr = False     # 关闭键是颜色徽章; 徽章也没中才惰性补 OCR

    def detect(self, f):
        # "26秒后可获得奖励"是广告页文案(pages/ad_popup.py), 别误判成"已获得奖励"弹窗
        if f.has('放弃', '是否继续观看视频'):
            return 0.0
        if f.has('已获得奖励', '获得奖励', '领取成功'):
            return 1.5
        return 0.0

    def act(self, ctx):
        img = getattr(ctx.f, 'img', None)
        badge = find_close_badge(img) if img is not None else None
        if badge is not None:
            if not ctx.acted('claim_close'):
                logging.info(f'[领奖弹窗] 点关闭徽章 {badge}')
                ctx.click(*badge)
            return True
        for kw in CLOSE_KW:
            pts = ctx.need_text().find(kw)
            if pts:
                if not ctx.acted('claim_close'):
                    logging.info(f'[领奖弹窗] 点 {kw} {pts[0]}')
                    ctx.click(*pts[0])
                    return True
        return False
