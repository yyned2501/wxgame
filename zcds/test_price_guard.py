# -*- coding: utf-8 -*-
r"""价格护栏回归测试: chest_info 只准点免费按钮, 旁边带价格(￥/元/钻石/宝石/充值)一律拒点.

两条真机血泪, 都用合成文本框/合成图像锁死(不依赖 OCR, 秒级跑完):
  1) 2026-09-03 00:04 月卡弹窗上的 "￥68" 落在 (278,788), 和免费开箱按钮 (278,785)
     只差 3px —— 弹窗一旦被误判成 chest_info, 旧代码就替玩家买了月卡.
  2) 2026-09-03 00:57 真机(shots_live/dbg_007_chest_info_005708.png): 面板按钮写成
     "开启", 下面画的是"紫宝石图标 + 30", OCR 只读得到裸数字 30 -> PRICE_RE 全不命中,
     机器人真花掉 30 紫宝石(顶栏 114 -> 84). 免费按钮那行永远带单位(20分/5分).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vision import TBox
from pages.chest_info import ChestInfoPage, CLOSE_POS, gem_cost_pixels, GEM_MIN


class F:
    """最小 ScreenFeature 替身: 只要 boxes / img"""

    def __init__(self, boxes):
        self.boxes = boxes
        self.img = None


class Ctx:
    dry_run = False

    def __init__(self, boxes):
        self.f = F(boxes)
        self.clicks = []

    def acted(self, key, gap=6.0):
        return False

    def click(self, x, y):
        self.clicks.append((int(x), int(y)))


def box(text, cx, cy, w=60, h=26):
    return TBox(text, int(cx - w / 2), int(cy - h / 2), w, h)


CASES = [
    # (说明, 文本框, 期望点击(None=不该点免费按钮))
    ('免费面板: 解锁 + 20分(所需时长)', [box('解锁', 278, 785), box('20分', 296, 815)], (278, 785)),
    ('免费面板: 开启(宝箱转好)', [box('开启', 275, 782), box('金币', 229, 707)], (275, 782)),
    ('月卡弹窗: 按钮旁 3px 就是 ￥68', [box('解锁', 278, 785), box('￥68', 278, 788)], None),
    ('价格写在旁边另一个框: 29 钻石', [box('开启', 278, 785), box('29 钻石', 278, 740)], None),
    ('按钮自带价格字样', [box('解锁￥68', 278, 785)], None),
    ('宝石计费', [box('开启', 278, 785), box('10宝石', 340, 785)], None),
    ('价格离得远(不在按钮邻域) -> 仍算免费', [box('解锁', 278, 785), box('￥68', 120, 300)], (278, 785)),
    ('按钮带所需时长 5分 = 仍算免费', [box('解锁 5分', 278, 785)], (278, 785)),
    ('按钮带剩余倒计时 -5分 -> 不算免费', [box('解锁 -5分', 278, 785)], None),
    # v3.2 新增: 宝石计费画成"图标+裸数字", 没有 元/钻石/宝石 字样
    ('真机付费帧复刻: 开启 + 下方裸数字 30', [box('开启', 275, 782), box('30', 292, 814)], None),
    ('解锁 + 下方裸数字 30 同样拒点', [box('解锁', 278, 785), box('30', 292, 814)], None),
    ('裸数字在按钮上方(奖励那排) -> 不算价格, 仍点', [box('解锁', 278, 785), box('30', 292, 700)], (278, 785)),
    ('裸数字离得远 -> 不算价格, 仍点', [box('解锁', 278, 785), box('30', 120, 300)], (278, 785)),
    ('带单位的时长 20分 不是裸数字 -> 仍点', [box('解锁', 278, 785), box('20分', 296, 815)], (278, 785)),
]

fails = 0
for desc, boxes, want in CASES:
    ctx = Ctx(boxes)
    ChestInfoPage().act(ctx)
    got_free = (278, 785) in ctx.clicks or (275, 782) in ctx.clicks
    if want is None:
        ok = not got_free
        detail = '拒点免费按钮' if ok else '竟然点了 ' + str(ctx.clicks)
    else:
        ok = want in ctx.clicks
        detail = '点了 ' + str(ctx.clicks)
    print('%-4s %-34s -> %s' % ('PASS' if ok else 'FAIL', desc, detail))
    if not ok:
        fails += 1

# 兜底关闭坐标必须仍然是标定值(img=None 时)
ctx = Ctx([box('开启', 278, 785), box('￥68', 278, 788)])
ChestInfoPage().act(ctx)
ok = ctx.clicks == [CLOSE_POS]
print('%-4s %-34s -> %s' % ('PASS' if ok else 'FAIL', '拒点后关闭面板', ctx.clicks))
if not ok:
    fails += 1

# ---- 第三道判据: 按钮带内的紫宝石像素(不依赖 OCR, 整帧 numpy) ----
import numpy as np
from PIL import Image

W, H = 552, 1006


def band_img(rgb):
    # 造一帧: 只在按钮下方带内(x 232..322 / y 797..830)涂一种颜色
    a = np.zeros((H, W, 3), dtype=np.uint8)
    a[797:830, 232:322] = rgb
    return Image.fromarray(a)


PIX = [
    ('带内是紫宝石(实测主色 222,62,246) -> 判付费', (222, 62, 246), True),
    ('带内是橙色时钟图标(免费) -> 不判付费', (232, 150, 40), False),
    ('带内是黄色按钮底(免费) -> 不判付费', (245, 190, 60), False),
    ('带内空白 -> 不判付费', (30, 30, 60), False),
]
for desc, rgb, want_paid in PIX:
    n = gem_cost_pixels(band_img(rgb), 277, 785)
    ok = (n >= GEM_MIN) == want_paid
    print('%-4s %-42s -> 带内宝石像素 %d (阈值 %d)' % ('PASS' if ok else 'FAIL', desc, n, GEM_MIN))
    if not ok:
        fails += 1

# 真机两帧的带内实测值必须仍然落在阈值两边(免费 0 / 付费 362)
_here = os.path.dirname(os.path.abspath(__file__))
for name, cx, cy, want in (('shots_live' + os.sep + 'dbg_003_chest_info_004233.png', 276, 785, 0),
                           ('shots_live' + os.sep + 'dbg_007_chest_info_005708.png', 275, 783, 1)):
    p = os.path.join(_here, name)
    if not os.path.exists(p):
        print('SKIP %-50s (真机帧不在)' % os.path.basename(name))
        continue
    n = gem_cost_pixels(Image.open(p).convert('RGB'), cx, cy)
    ok = (n == 0) if want == 0 else (n >= GEM_MIN)
    print('%-4s %-50s -> 带内宝石像素 %d' % ('PASS' if ok else 'FAIL', os.path.basename(name), n))
    if not ok:
        fails += 1


print('SUMMARY failures = %d' % fails)
sys.exit(1 if fails else 0)
