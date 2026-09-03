# -*- coding: utf-8 -*-
r"""军衔升级页: 点黄色"领取"领免费奖励箱(真机 2026-09-03 07:39 补的第 12 页)

坑(真机 07:39 复现): 结算页点完继续 -> 关掉月卡弹窗后露出这一页
  (蓝六边形军衔 + "升级" + 奖励木箱 + 黄色"领取"), 指纹表里没有它 ->
  点色全表零命中 -> 白烧一次全图 OCR(675ms) 还判成 unknown ->
  unknown 只会点遮罩/等 45s, 实测 3 帧 7s 一圈原地空转。

指纹只取两处**与等级/奖励内容无关**的恒定区域: 标题"升级"两个字 + 黄色领取按钮。
刻意避开六边形里的等级数字(5->6 就变)和中间那件奖励图标(木箱/铁箱/钻石会变):
pick_print 全图扫时把 (272,268) 那个"5"选进了指纹 —— 那样升一级整页指纹就废了,
所以标定分两段跑(--region 0,350,552,430 / --region 0,700,552,1006)再合并复核
(scratch/scripts/chk_lvl_print.py: 本页 4/4 全中 / 异页误中 0 / 异页最高 0.160)。

动作层纯点色, 而且必须和 chest_info 那块**同一颜色**的黄按钮划清界限:
  同一取样框 (150,720,420,840) deg90 实测 ->
    本页  中心(275,776) n=5524   (4 帧完全一致)
    chest_info 中心(275,795) n=7655~7657(免费) / 8061(付费)
    chest_open 同框只有 0~29 像素
  中心 y 带 + 像素数上下限两条带子都不重叠 => 谁也不会冒充谁去点按钮,
  尤其堵死"把付费开箱按钮当免费领取点掉"这种花钱事故;
  而且真出现"看广告双倍领取"多一个黄按钮时外接框会变宽 -> n 落在带外 -> 不点。
"""
import logging

from .base import Page, color_button, color_pixels


class LevelUpPage(Page):
    name = 'levelup'
    next_pages = ('lobby', 'chest_open', 'claim_popup', 'result', 'hero_level', 'newcard',
                    'unknown')   # 真机 16:03: 领完升级奖励直接弹新卡页
    act_needs_ocr = False        # 纯点色页: 主循环不为本页跑 OCR

    # 点色指纹: tools/pick_print.py pick --label levelup 分段标定后合并(勿手改)
    # 1 种形态 x 5 个十字单元(每单元 5 点, 共 25 判色点/形态), 任一形态全中即判为 levelup; 语料 4/4 全中 / 异页误中 0 / margin 0.16(异页最高只中 4/25 点) / 各形态覆盖 [4] 帧
    points = [
        [248, 374, 0xFFFFFF], [250, 374, 0xFFFFFF], [246, 374, 0xF1F1F1],
        [248, 376, 0x979797], [248, 372, 0xF2F2F2], [304, 382, 0xFFFFFF],
        [306, 382, 0xEDEDED], [302, 382, 0xF6F6F6], [304, 384, 0xFFFFFF],
        [304, 380, 0xFFFFFF], [252, 768, 0xFFFFFF], [254, 768, 0xF9F6F5],
        [250, 768, 0xC39471], [252, 770, 0xFFFFFF], [252, 766, 0xBD8865],
        [296, 780, 0xFFFFFF], [298, 780, 0xFFFFFF], [294, 780, 0xD9C0B5],
        [296, 782, 0xFFFFFF], [296, 778, 0xFFFEFE], [204, 752, 0xF8E281],
        [206, 752, 0xFDDD69], [202, 752, 0xD6A42A], [204, 754, 0xFDC931],
        [204, 750, 0xDCA817],
    ]

    # ---- 动作层点色(与 chest_info 黄按钮互斥, 数值见文件头实测) ----
    CLAIM_BOX = (150, 720, 420, 840)
    CLAIM_COLOR = 0xFDCA33
    CLAIM_MIN_PX = 3000      # 实测 5524; chest_open 同框 0~29 -> 下限挡掉碎黄点
    CLAIM_MAX_PX = 6800      # chest_info 黄按钮 7655~8061 -> 上限卡在两页之间
    CLAIM_Y = (760, 790)     # 中心 y 带; chest_info 恒 795

    def detect(self, f):
        # 只在 OCR 兜底分支用(指纹没标上的改版): 标题 + 按钮文字同时出现才算
        return 1.0 if f.has('升级') and f.has('领取') else 0.0

    def act(self, ctx):
        img = getattr(ctx.f, 'img', None)
        if img is None:
            return False
        pos = color_button(img, self.CLAIM_BOX, self.CLAIM_COLOR, self.CLAIM_MIN_PX)
        if pos is None:
            return False
        n = color_pixels(img, self.CLAIM_BOX, self.CLAIM_COLOR)
        cx, cy = pos
        if n > self.CLAIM_MAX_PX or not (self.CLAIM_Y[0] <= cy <= self.CLAIM_Y[1]):
            # 长得像 chest_info 的开箱按钮(或多了个广告按钮) -> 一律不动
            logging.info(f'[升级] 黄块 {pos} n={n} 不在领取按钮带内 -> 不动')
            return False
        if ctx.acted('levelup_claim', gap=8.0):
            return True
        logging.info(f'[升级] 点色命中领取按钮 {pos} n={n}')
        ctx.click(cx, cy)
        return True
