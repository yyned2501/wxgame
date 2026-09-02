# -*- coding: utf-8 -*-
"""宝箱开启动画页: 点大厅槽位开箱后整屏接管 -> [点击领取奖励] -> 奖励展示 -> [点击关闭]

真机 2026-09-02 22:56 实测: 这一页全屏盖住大厅(大厅指纹必不中), 原先没有任何页面建模它,
unknown 兜底连续 8 次(85 秒)才靠瞎点遮罩混过去 —— 现在按点色指纹直接定页。
指纹只取底部那行白色描边文字的 3 个十字单元: 领取奖励/关闭两种文案在这三处像素完全一致,
一组通吃(标定强制单簇 => 每个单元都在 3 帧真机图上稳定)。
"""
import logging

from .base import Page, color_button, color_pixels

CLAIM_KW = ('点击领取奖励', '领取奖励')
CLOSE_KW = ('点击关闭',)


class ChestOpenPage(Page):
    name = 'chest_open'
    next_pages = ('chest_open', 'claim_popup', 'lobby', 'unknown')

    # 点色指纹: 由 tools/pick_print.py pick --label chest_open --region 20,50,530,1000 --cluster 40 自动标定(勿手改)
    # 候选区排除微信标题栏(y<50)与左右黑边: 那是窗口外壳, 每页都一样, 拿来判页等于没判
    # 1 种形态 x 3 个十字单元(每单元 5 点, 共 15 判色点/形态), 任一形态全中即判为 chest_open; 语料 8/8 全中 / 异页误中 0 / margin 0.40(异页最高只中 6/15 点) / 各形态覆盖 [8] 帧
    points = [
        [228, 906, 0xFFFFFF], [230, 906, 0xFFFFFF], [226, 906, 0xB5B5B5],
        [228, 908, 0xFFFFFF], [228, 904, 0xEDEDED], [312, 906, 0xFFFFFF],
        [314, 906, 0x939393], [310, 906, 0xFBFBFB], [312, 908, 0xFFFFFF],
        [312, 904, 0xA2A2A2], [272, 930, 0xE6E6E6], [274, 930, 0x141031],
        [270, 930, 0xB6B6B6], [272, 932, 0x1A172F], [272, 928, 0xFFFFFF],
    ]

    # ---- 动作层点色(2026-09-03 定案: 零 OCR) --------------------------------
    # 底部那行按钮文字是全屏唯一的白色大块(底 0x2E265F), 数它有多少白像素就认它。
    # 语料 3 帧实测(白像素数 / 外接框中心, degree90 = 每通道 +-13):
    #   领取态 chest_open_claim : bot=1969 中心(275,917)  左上[跳过]还在 skip=833
    #   关闭态 chest_open_close : bot=1394 中心(275,917)  skip=0
    #   奖励态 chest_open_reward: bot=1394 中心(275,917)  skip=0
    # 两种文案的按钮中心完全重合 => 一次取色通吃, 不必分辨字面(旧版要靠 OCR 认"领取/关闭")。
    # 选框验证: 把框放大到 (150,780,410,990) 计数与中心都不变 => 该区域内除按钮文字无别的白色,
    #   这里取稍紧的 BOT_BOX, 阈值 600 落在 1394 与 0(动画还在放, 按钮未出)之间。
    # 跳过按钮(左上)同理: 白字块 833px, 中心(82,142); 放大到 (0,100,220,200) 计数不变(没裁到字)。
    # 顺带干掉旧版的第三个 OCR 分支(找"跳过"二字): 动画期只认左上那块白, 不再读字。
    WHITE = 0xFFFFFF
    BOT_BOX = (150, 880, 410, 960)
    BOT_MIN_PX = 600
    SKIP_BOX = (20, 120, 160, 175)
    SKIP_MIN_PX = 300
    act_needs_ocr = False   # 纯点色页: 主循环不为本页跑 OCR

    def detect(self, f):
        if f.has(*CLAIM_KW):
            return 1.4
        if f.has(*CLOSE_KW):
            return 1.3
        return 0.0

    def act(self, ctx):
        img = ctx.f.img          # act_needs_ocr=False => ctx.f 只有图, 没有文字框
        # 1) 底部主按钮: 白色文字块出现即点(先领取后关闭, 中心同一点)
        bot = color_button(img, self.BOT_BOX, self.WHITE, self.BOT_MIN_PX)
        if bot is not None:
            # 左上[跳过]还在 = 刚放完动画的"领取奖励"态; 它消失后底部就是"关闭"态
            tag = 'claim' if color_pixels(img, self.SKIP_BOX, self.WHITE) >= self.SKIP_MIN_PX else 'close'
            if ctx.acted('chest_open_' + tag, gap=6.0):
                return False
            logging.info(f'[开箱动画] 点色命中底部按钮({tag}) {bot}')
            ctx.click(*bot)
            return True
        # 2) 动画还在放(底部按钮未出): 点左上[跳过]直接进奖励展示, 省一半等待
        skip = color_button(img, self.SKIP_BOX, self.WHITE, self.SKIP_MIN_PX)
        if skip is not None and not ctx.acted('chest_open_skip', gap=8.0):
            logging.info(f'[开箱动画] 按钮未出, 点色跳过 {skip}')
            ctx.click(*skip)
            return True
        return False
