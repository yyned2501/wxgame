# -*- coding: utf-8 -*-
"""结算页: 看广告领奖(失败/胜利礼包, 纯点色) -> 点击继续"""
import logging

from config import WATCH_ADS

from .base import Page, ad_claim_pos, color_button

class ResultPage(Page):
    name = 'result'
    next_pages = ('lobby', 'claim_popup', 'ad_popup', 'vip_popup', 'matching',
                  'levelup', 'hero_level', 'unknown')
    # 点色指纹: 由 tools/pick_print.py pick --label result 自动标定(勿手改)
    # 1 种形态 x 5 个十字单元(每单元 5 点, 共 25 判色点/形态), 任一形态全中即判为 result; 语料 22/22 全中 / 异页误中 0 / margin 0.12(异页最高只中 3/25 点) / 各形态覆盖 [22] 帧
    points = [
        [388, 146, 0x573324], [390, 146, 0x512E26], [386, 146, 0x573324],
        [388, 148, 0x573324], [388, 144, 0x573324], [76, 162, 0x412734],
        [78, 162, 0x412734], [74, 162, 0x3F2532], [76, 164, 0x412734],
        [76, 160, 0x412632], [472, 158, 0x422632], [474, 158, 0x422632],
        [470, 158, 0x301B20], [472, 160, 0x412632], [472, 156, 0x402530],
        [500, 242, 0x3C2328], [502, 242, 0x3B2126], [498, 242, 0x3A2025],
        [500, 244, 0x3C2227], [500, 240, 0x3C2328], [44, 242, 0x3B2227],
        [46, 242, 0x3B2227], [42, 242, 0x3B2227], [44, 244, 0x3B2227],
        [44, 240, 0x3C2327],
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
    # [领取]点完到下一次点它的间隔. 领完广告退回结算页时横幅往往还在(那是"可用 8/8"的每日额度),
    # 不设节流就会在同一次结算里反复开广告。120s > 一场战斗 + 一条广告, 等于"每场最多领一次"。
    CLAIM_GAP = 120.0

    def detect(self, f):
        # x0.5 下"继续/维续"易读错, 多做几个容错
        if f.has('点击继续', '点击维续', '再来一局'):
            return 0.95
        if f.has('失败', '胜利') and f.has('MVP', '奖杯', '经验', '点击', '维续'):
            return 0.8
        return 0.0

    def act(self, ctx):
        # 1) 礼包领取: 点色认黄色[领取]药丸(ad_claim_pos, 全语料 815 帧 38 中 / 0 误中),
        #    然后交给主循环的"看广告窗口"把这条广告看完 —— 用户 2026-09-03 12:47 定案。
        #    旧版这里是 ctx.need_text() + f.find('领取'): 一次全图 OCR, 而且"领取"两个字
        #    在别的弹窗上也有(钻石礼包), 靠 '钻石' not in joined 打补丁。现在整条零 OCR。
        if WATCH_ADS:
            pos = ad_claim_pos(ctx.f.img)
            if pos is not None and not ctx.acted('result_claim', self.CLAIM_GAP):
                logging.info(f'[结算] 点色命中[领取](看广告) {pos} -> 去看广告, 看完自动关')
                ctx.click(*pos)
                ctx.start_ad_watch('结算礼包')
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
