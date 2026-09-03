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
    # 1 种形态 x 5 个十字单元(每单元 5 点, 共 25 判色点/形态), 任一形态全中即判为 result; 语料 23/23 全中 / 异页误中 0 / margin 0.24(异页最高只中 6/25 点) / 各形态覆盖 [23] 帧
    # 🔴 unit0 原来在 (388,146) —— 那是 MVP 页上方的 3D 获胜角色动画精灵(红龙/骷髅…还会闪 ✨), 角色一换就掉分;
    #    2026-09-03 20:14 真机第 24 轮那帧被红龙 + 一颗大闪光正好盖住, 整条只中 23/25 -> 退化成全项目唯一一条 OCR 路由.
    #    现换到 (26,192) 王座厅纯背景(23 帧跨帧逐通道偏差 3), 留出集 54 帧(现有 result 指纹 score>=0.7 的全部帧)全中. 教训见 COLORPRINT.md §5: 动画精灵上的点不能进指纹
    points = [
        [76, 162, 0x412734], [78, 162, 0x412734], [74, 162, 0x3F2532],
        [76, 164, 0x412734], [76, 160, 0x412632], [472, 158, 0x422632],
        [474, 158, 0x422632], [470, 158, 0x301B20], [472, 160, 0x412632],
        [472, 156, 0x402530], [500, 242, 0x3C2328], [502, 242, 0x3B2126],
        [498, 242, 0x3A2025], [500, 244, 0x3C2227], [500, 240, 0x3C2328],
        [44, 242, 0x3B2227], [46, 242, 0x3B2227], [42, 242, 0x3B2227],
        [44, 244, 0x3B2227], [44, 240, 0x3C2327], [26, 192, 0x2D1613],
        [28, 192, 0x2D1613], [24, 192, 0x2D1613], [26, 194, 0x2D1613],
        [26, 190, 0x2D1613],
    ]
    # ---- 动作层点色(2026-09-03 定案: 零 OCR) --------------------------------
    # 结算页整屏只有"一个"亮紫色块 = 那个按钮, 背景紫是 0x621FAD(差 >100/通道),
    # degree90(每通道 ±13)下两者完全分开; 全帧扫与限带扫结果一致(3 组帧实测)。
    # 语料实测(全语料 51 帧重扫, 2026-09-03 晚): **有**礼包横幅 47 帧 n=2848 -> 中心(275,911)(少数 913);
    #   **无**横幅 4 帧语料 + 第 20 轮 6 张探针 n=2958~2981 -> 中心(275,830)。两种版式差 **81px**,
    #   所以取色块外接框中心而不是写死坐标。(旧注释把这两组数字标反了, 已按实测改回 -> COLORPRINT.md §22.4)
    # 陷阱: watch_124707 是激励视频盖在结算页上的帧, 扫描 n=0 -> 本帧不动作。
    #   旧版在这里靠 OCR 找"点击继续", 读到遮罩上的广告文案就瞎点一次。
    CONTINUE_BOX = (150, 780, 420, 970)
    CONTINUE_COLOR = 0xCC56FF
    CONTINUE_MIN_PX = 800
    act_needs_ocr = False   # 纯点色页: 主循环不为本页跑 OCR
    # [领取]点完到下一次点它的间隔. 领完广告退回结算页时横幅往往还在(那是"可用 8/8"的每日额度),
    # 不设节流就会在同一次结算里反复开广告。120s > 一场战斗 + 一条广告, 等于"每场最多领一次"。
    CLAIM_GAP = 120.0
    # 额度是 8 次/天: 2026-09-03 13:32:58 那一帧横幅上写着"可用 1/8", 领完这一次之后
    # 第 18~20 轮共 1000+ 步再没见过横幅(探针帧整个下带 0 个黄色像素) -> COLORPRINT.md §22.3。

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
            elif pos is None:
                # 没认到横幅 != 一定没有横幅: --ad-probe 存帧, 事后肉眼复核(见 App.ad_probe_shot)
                shot = getattr(ctx, 'ad_probe_shot', None)
                if shot is not None:
                    shot(ctx.f.img, 'result')
        # 2) 继续: 亮紫按钮的外接框中心(旧版要 OCR 认"点击继续", 还常被读成"点击维续")
        pos = color_button(ctx.f.img, self.CONTINUE_BOX, self.CONTINUE_COLOR,
                           self.CONTINUE_MIN_PX)
        if pos is None or ctx.acted('result_continue'):
            return False
        ctx.battles += 1
        logging.info(f'[结算] 点色命中继续按钮 {pos} (累计 {ctx.battles} 场)')
        ctx.click(*pos)
        return True
