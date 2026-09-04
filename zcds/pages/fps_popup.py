# -*- coding: utf-8 -*-
r"""帧率自适应提示弹窗: 只点黄色[知道了]关掉, 别的什么都不碰

坑(真机 2026-09-04 08:26~08:41 定案, 原地空转 15 分钟 / 118 步零动作):
  战斗中帧率掉到阈值以下 -> 游戏弹一张"帧率自适应 / 已开启自动帧率控制…"的蓝面板,
  正盖在结算页上(底下还能看见[点击继续]和[失败礼包])。这一页当时不存在 ->
  点色全表零命中 -> 2c 花全图 OCR -> OCR 读到的是**背景**结算页的字 -> 判成 result
  -> ResultPage.act() 的亮紫按钮被弹窗挡住找不到 -> return False
  -> "OCR 连续 3 帧认出页面却零动作" -> 交 unknown 走出口升级表 -> 遮罩试探点
     (270,860) / (270,300) / (30,300) 三个点全落在弹窗外面, 一个都关不掉它。
  日志一路 WARNING 到 08:41 我手工点掉为止 —— 弹窗自己不会消失。

修法两层:
  1) 本页进指纹表(标定域 --region 65,325,487,705 = 弹窗面板内部, 一格背景都不许进):
     面板外的东西是**被压暗的上一页**, 底色随上一页变(result/lobby/battle 各不相同),
     混进指纹就等于给弹窗加了"只在我见过的那张背景上才认得出"的毛病。
     复核: 本页 10/10 全中 / 异页误中 0 / margin 0.20(异页最高只中 3/15 点)。
  2) 动作层不写死坐标: 黄色[知道了]色块现算外接框中心(实测 n=3737 中心 (275,644)),
     弹窗真往上浮几个像素也点得中。
"""
import logging

from .base import Page, color_button

YELLOW = 0xFDCA33          # 按钮底色(实测主色, 渐变边 #FABF2C 也在容差内)
BTN_BOX = (195, 605, 360, 690)   # 只在弹窗面板内的按钮带上找
BTN_MIN_PX = 900           # 实测整块 3737px; 同带里别的黄色东西远小于这个数


class FpsPopupPage(Page):
    name = 'fps_popup'
    next_pages = ('result', 'lobby', 'unknown')
    act_needs_ocr = False      # 纯点色页: 主循环不为本页跑 OCR

    # 点色指纹: python tools/pick_print.py pick --label fps_popup -n 9 --min-sep 34 --min-lum 60 --region 65,325,487,705 (勿手改)
    # 1 种形态 x 3 个十字单元(每单元 5 点, 共 15 判色点/形态), 任一形态全中即判为 fps_popup; 语料 10/10 全中 / 异页误中 0 / margin 0.20(异页最高只中 3/15 点) / 各形态覆盖 [10] 帧
    points = [
        [217, 357, 0xFFFFFF], [219, 357, 0xFFFFFF], [215, 357, 0xFFFFFF],
        [217, 359, 0xFFFFFF], [217, 355, 0xF3F4F7], [253, 357, 0xFFFFFF],
        [255, 357, 0xFFFFFF], [251, 357, 0xFFFFFF], [253, 359, 0xFFFFFF],
        [253, 355, 0xFFFFFF], [293, 357, 0xFFFFFF], [295, 357, 0xFFFFFF],
        [291, 357, 0x5F68AD], [293, 359, 0x6068AC], [293, 355, 0xFFFFFF],
    ]

    def detect(self, f):
        # 点色没中时才轮到这里: 标题是固定文案, 给高分抢在 result 前面
        return 2.0 if f.has('帧率自适应', '自动帧率控制') else 0.0

    def act(self, ctx):
        img = getattr(ctx.f, 'img', None)
        pos = color_button(img, BTN_BOX, YELLOW, BTN_MIN_PX) if img is not None else None
        if pos is None:
            return False
        if ctx.acted('fps_ok', gap=6.0):
            return True
        logging.info(f'[帧率弹窗] 点色命中黄色[知道了] {pos} -> 点掉它')
        ctx.click(*pos)
        return True
