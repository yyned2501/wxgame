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
    next_pages = ('chest_open', 'claim_popup', 'chest_info', 'levelup', 'hero_level', 'lobby', 'unknown')

    # 点色指纹: 由 tools/pick_print.py pick --label chest_open --region 20,50,530,1000 --cluster 40 自动标定(勿手改)
    # 候选区排除微信标题栏(y<50)与左右黑边: 那是窗口外壳, 每页都一样, 拿来判页等于没判
    # 1 种形态 x 3 个十字单元(每单元 5 点, 共 15 判色点/形态), 任一形态全中即判为 chest_open; 语料 8/8 全中 / 异页误中 0 / margin 0.40(异页最高只中 6/15 点) / 各形态覆盖 [8] 帧
    # 2026-09-04 02:5x 重标(tools/pick_print.py stable --label chest_open --min-chroma 40):
    # 旧指纹 15 点里有 2 个点标在底部那行按钮文字上(312,904 #A2A2A2 / 270,930 #B6B6B6),
    # 文字带描边呼吸动画 -> 跨帧极差 0x41/0x49, degree85 只容 +-19, 于是真机 3 张新帧
    # (chest_open_live011320/014932/022853) 只中 8~13/15 点 -> 整页退回 OCR 定页。
    # stable 模式和 pick 相反: 只认【本页 11 帧全中 + 其他 274 帧一张都不误中】的单元,
    # 形态数固定 1; 再加 min-chroma 40 把白字/图标这类无色像素挡在门外。
    # 结果 = 开箱面板蓝机身 6 个十字单元 30 点, 跨帧极差 0, 本页最低 30/30, 异页最高 0.37。
    # 再 --with-dbg 把 20 张真机留出帧(shots_live/dbg_*_chest_open_*)也拉进【必须全中】:
    # 第一版第 6 单元 (268,388) 在 3 张留出帧上整组不中(25/30), 换成 (264,332) 后 31 帧全中。
    # 教训: stable 只吃标定语料会过拟合, 留出集才是判页是否真的稳。
    prints = (
        (   # 形态: chest_open 全部 31 帧通吃(11 标定 + 20 真机留出)(tools/pick_print.py stable --with-dbg)
            [264, 496, 0x5366AB], [266, 496, 0x5366AB], [262, 496, 0x5366AB],
            [264, 498, 0x5366AB], [264, 494, 0x5366AB], [356, 472, 0x4D5AA2],
            [358, 472, 0x4C5AA1], [354, 472, 0x4C5AA2], [356, 474, 0x4D5AA2],
            [356, 470, 0x4C5AA2], [184, 448, 0x49569D], [186, 448, 0x49579C],
            [182, 448, 0x49559C], [184, 450, 0x49569D], [184, 446, 0x4A549C],
            [324, 628, 0x4A549C], [326, 628, 0x4A549B], [322, 628, 0x4A559C],
            [324, 630, 0x49549B], [324, 626, 0x4A559C], [228, 644, 0x485299],
            [230, 644, 0x485299], [226, 644, 0x485299], [228, 646, 0x475197],
            [228, 642, 0x485299], [264, 332, 0x3E4385], [266, 332, 0x3E4385],
            [262, 332, 0x3E4385], [264, 334, 0x3F4486], [264, 330, 0x3E4385],
        ),
    )

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
    BOT_BOX = (150, 750, 410, 960)
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
