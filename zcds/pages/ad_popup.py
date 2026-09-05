# -*- coding: utf-8 -*-
"""激励视频广告页: 结算页的"领取(礼包)"打开的就是它

真机 2026-09-02 23:24: result 点"领取" -> 广告页(左上"广告"69,89 / 右上"关闭"498,88 /
顶部"26秒后可获得奖励"194,89), 倒计时没走完就点"关闭" -> 弹挽留框
"暂未获得奖励是否继续观看视频"(277,484) + [放弃](179,609) [继续](374,609)。
本页策略(2026-09-03 12:47 反转, 用户定案"可以看广告的地方就自动看完"):
  1) 广告正在放 -> **什么都不点**, 等它自己放完。旧版在这里点"放弃", 奖励直接作废;
  2) 弹了"暂未获得奖励是否继续观看视频"挽留框 -> 点**[继续观看]**(旧版点[放弃]);
     挽留框只会在倒计时没走完就去点[关闭]时出现, 正常路径走不到这里, 留着是保险。
看广告窗口的计时/关闭判据在 auto_bot.App._ad_tick(点色 ad_close_pos + ad_pill_right), 不在本页。
没有点色指纹(广告创意每帧都变), 定页仍靠 OCR 关键词 —— 这是全项目唯一还靠 OCR 定页的页。
"""
import logging

from .base import Page


class AdPopupPage(Page):
    name = 'ad_popup'
    next_pages = ('result', 'lobby', 'claim_popup', 'unknown')

    GIVEUP_KW = ('放弃',)
    KEEP_KW = ('继续观看', '继续')          # 挽留框右边的[继续观看](374,609)
    MARK_KW = ('是否继续观看视频', '秒后可获得奖励', '继续观看')
    # 同一个挽留框上点"继续"的最大次数, 超过就改点"放弃":
    # R52 真机 0:52~0:58 踩到的就是 SDK 反复重弹同一挽留框, 一帧都不推进.
    # 用户口径「可看广告得奖励就优先看广告」是给广告能正常放的情况, 这种广告根本没在放
    # (没填充 + 上一会话残留挽留框) 再点继续只会浪费额度; 真广告早就放完了, 不会再卡在这屏.
    KEEP_MAX = 3

    def __init__(self):
        super().__init__()
        self._keep_count = 0            # 本轮挽留框上点了多少次「继续」

    def detect(self, f):
        if f.has(*self.GIVEUP_KW):
            return 1.6
        if f.has(*self.MARK_KW):
            return 1.4
        return 0.0

    def act(self, ctx):
        f = ctx.f
        # 1) 挽留框: 点[继续观看]把广告看完 —— 这一步之后奖励才会发
        if f.has('是否继续观看视频') or f.has('暂未获得奖励'):
            if self._keep_count >= self.KEEP_MAX:
                # 已经点了 KEEP_MAX 次还没推进: SDK 反复重弹同一挽留框, 改点放弃收场
                pts = f.find(self.GIVEUP_KW[0])
                if pts and not ctx.acted('ad_giveup', 5.0):
                    logging.info(f'[广告页] 挽留框连续{self._keep_count}次继续仍卡在原页 -> 改点放弃 {pts[0]}')
                    ctx.click(*pts[0])
                    self._keep_count = 0
                    return True
                return False
            for kw in self.KEEP_KW:
                pts = f.find(kw)
                if pts:
                    if not ctx.acted('ad_keep', 5.0):
                        logging.info(f'[广告页] 挽留框点 {kw} {pts[0]} -> 继续看完(旧版在这里点[放弃])')
                        ctx.click(*pts[0])
                        self._keep_count += 1
                        return True
                    return False
        else:
            # 不在挽留框上(广告页或别的), 把累计计数清零 —— 进了下一轮再从 0 开始
            self._keep_count = 0
        # 2) 广告正在放: 一帧都不点。旧版这里点[放弃] -> 用户要的"自动看完"永远拿不到奖励。
        #    超时兜底在 App._ad_tick(看广告窗口超 AD_WATCH_TOTAL 才退回正常路由), 不在本页判。
        return False
