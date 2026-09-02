# -*- coding: utf-8 -*-
"""结算页: 领奖(失败/胜利礼包) -> 点击继续"""
import logging

from config import WATCH_ADS

from .base import Page, color_button

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
    # ---- 动作层点色(2026-09-03 定案: 零 OCR) --------------------------------
    # 结算页整屏只有"一个"亮紫色块 = 那个按钮, 背景紫是 0x621FAD(差 >100/通道),
    # degree90(每通道 ±13)下两者完全分开; 全帧扫与限带扫结果一致(3 组帧实测)。
    # 语料实测 n 像素: 有礼包横幅版式 2968 -> 中心(275,830); 无横幅 2981 -> (275,912);
    #   真机 3 帧 2848 -> (275,910)。两种版式中心差 80px, 所以取色块外接框中心而不是写死坐标。
    # 陷阱: watch_124707 是激励视频盖在结算页上的帧, 扫描 n=0 -> 本帧不动作。
    #   旧版在这里靠 OCR 找"点击继续", 读到遮罩上的广告文案就瞎点一次。
    CONTINUE_BOX = (150, 780, 420, 970)
    CONTINUE_COLOR = 0xCC56FF
    CONTINUE_MIN_PX = 800
    act_needs_ocr = False   # 纯点色页: 主循环不为本页跑 OCR

    def detect(self, f):
        # x0.5 下"继续/维续"易读错, 多做几个容错
        if f.has('点击继续', '点击维续', '再来一局'):
            return 0.95
        if f.has('失败', '胜利') and f.has('MVP', '奖杯', '经验', '点击', '维续'):
            return 0.8
        return 0.0

    def act(self, ctx):
        # 1) 礼包领取: 真机 23:24 证实"领取"打开的是激励视频广告页(pages/ad_popup.py),
        #    WATCH_ADS=False(默认)时连 OCR 都不启动 —— 短路在最前面, 保住本页零 OCR。
        if WATCH_ADS:
            f = ctx.need_text()          # 只在真要看广告时才惰性补一次文字识别
            pts = f.find('领取') if f is not None else None
            if pts and '钻石' not in f.joined and not ctx.acted('result_claim'):
                logging.info(f'[结算] 点 领取(礼包) {pts[0]}')
                ctx.click(*pts[0])
                return True
        # 2) 继续: 亮紫按钮的外接框中心(旧版要 OCR 认"点击继续", 还常被读成"点击维续")
        pos = color_button(ctx.f.img, self.CONTINUE_BOX, self.CONTINUE_COLOR,
                           self.CONTINUE_MIN_PX)
        if pos is None or ctx.acted('result_continue'):
            return False
        ctx.battles += 1
        logging.info(f'[结算] 点色命中继续按钮 {pos} (累计 {ctx.battles} 场)')
        ctx.click(*pos)
        return True
