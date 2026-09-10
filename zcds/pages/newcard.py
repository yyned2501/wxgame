# -*- coding: utf-8 -*-
r"""新卡展示页: 结算/升级后弹一张新卡(顶部黄色[新卡] + 中间卡牌美术 + 底部[白字]点击继续)

坑(真机 2026-09-03 16:03 定案, 整轮原地空转 60s): 这一页原来根本不存在 ->
  点色全表零命中 -> 2b 防抖白等一帧 -> 2c 花一次全图 OCR -> OCR 只读到"点击继续" -> 判成 **result**(0.95)
  -> ResultPage.act() 在 CONTINUE_BOX 里找亮紫按钮(#CC56FF)找不到 -> return False 一个字都不点
  -> 下一帧又是零命中……每 6.7s 一圈, 16:03:51~16:04:51 连转 10 圈直到步数用完(日志 10 条 "result ocr")。
  连带伤害: page 在 None 和 result 之间来回翻, 卡页检测器每两帧就被"page is None"清零,
  连着 60s 零动作一次 [卡页] 警报都没发 —— 同一轮把 _flag_stuck 也修了(见 auto_bot.py)。

指纹只标"和抽到哪张卡无关"的区域(标定域 --region 0,830,552,1006):
  卡牌美术 / 远程机械兵种徽章 / 卡名 / 六个属性数字 **全随卡变**, 一个都不许进指纹。
  对照实验: 不加取样域限制跑全域, 工具会挑出 (168,476)(256,524) 这种正压在[远程][机械]徽章
  和卡名"弩炮"笔画上的点 —— 换一张卡就整片失效(= 2026-09-03 lobby 改版那个坑)。
  底部带只有两样东西: 白字[点击继续] + 固定紫底。4 帧真机语料上 15 个判色点**逐位完全相同**(色差 0,
  容差 +-19), 复核: 本页 4/4 全中 / 异页误中 0 / margin 0.33(异页最高只中 5/15 点)。

动作层纯点色 —— 数白字外接框(deg90 = 每通道 +-13, 只认 >=242 的近白像素):
  新卡页 4 帧实测 n=938 中心 (276,864) 恒定; 真结算页同一带只有 187(亮紫按钮上的字被紫底吃掉一半)
  和 6(按钮在框外) -> MIN_PX=400 把两页隔开, 万一判错也点不动。
"""
import logging

from .base import Page, color_button


class NewCardPage(Page):
    name = 'newcard'
    next_pages = ('lobby', 'result', 'levelup', 'hero_level', 'chest_open', 'unknown')
    act_needs_ocr = False        # 纯点色页: 主循环不为本页跑 OCR
    # 点色指纹: python tools/pick_print.py pick --label newcard -n 8 --region 0,830,552,1006 (勿手改)
    # 1 种形态 x 3 个十字单元(每单元 5 点, 共 15 判色点/形态), 任一形态全中即判为 newcard; 语料 4/4 全中 / 异页误中 0 / margin 0.33(异页最高只中 5/15 点) / 各形态覆盖 [4] 帧
    points = [
        [236, 858, 0xFFFFFF], [238, 858, 0xFCFCFC], [234, 858, 0x6D6D6E],
        [236, 860, 0xFFFFFF], [236, 856, 0xFFFFFF], [292, 862, 0xFFFFFF],
        [294, 862, 0xFFFFFF], [290, 862, 0xFEFEFE], [292, 864, 0xFFFFFF],
        [292, 860, 0xC9C9C9], [260, 914, 0x2D255C], [262, 914, 0x2D255C],
        [258, 914, 0x2D245C], [260, 916, 0x2D255C], [260, 912, 0x2D255C],
    ]
    # ---- 动作层点色(和是哪张卡无关) ----------------------------------------
    CONTINUE_BOX = (150, 840, 420, 890)
    CONTINUE_COLOR = 0xFFFFFF
    CONTINUE_MIN_PX = 400

    def detect(self, f):
        # 刻意不给 OCR 任何分数: 这一页 OCR 能读到的只有"点击继续", 那是 result 的词。
        # 让它去抢就会重演 16:03 的空转(判成 result -> 找不到亮紫按钮 -> 什么都不点)。
        return 0.0

    def act(self, ctx):
        pos = color_button(ctx.f.img, self.CONTINUE_BOX, self.CONTINUE_COLOR,
                           min_px=self.CONTINUE_MIN_PX)
        if pos is None or ctx.acted('newcard_continue'):
            return False
        logging.info(f'[新卡] 点色命中[点击继续]白字 {pos} -> 点掉它')
        ctx.click(*pos)
        return True
