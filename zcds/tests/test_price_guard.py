# -*- coding: utf-8 -*-
r"""价格护栏回归: chest_info 只准点"免费"那颗黄按钮, 判付费一律用点色, OCR 只剩否决权

2026-09-03 定案: 本页动作层改成**纯点色**(OCR 又慢又不准, 本页 ROI OCR 实测 369ms/帧),
所以本脚本不再用"合成文本框 + img=None"驱动 act()(那是旧版靠文字判价的时代), 改成:
  [1] 全部 chest_info 语料帧回放(帧表派生自 pick_print.LABELS, 命名即真值) ——
      免费帧必须点黄按钮, 付费帧一次都不许点按钮(只能点关闭)
  [2] 合成帧 —— 黄按钮 / 带内紫宝石 / 各种价格文字, 钉死"颜色是主判据, OCR 只有否决权"
  [3] 带内紫宝石像素的单元判据(阈值两侧) + 真机实测值必须仍落在阈值两侧
两条真机血泪(护栏为什么存在):
  1) 2026-09-03 00:04 月卡弹窗上的 "￥68" 在 (278,788), 和免费开箱按钮只差 3px ——
     弹窗一旦被误判成 chest_info, 旧代码就替玩家买了月卡。
  2) 2026-09-03 00:57 真机(shots_live/dbg_007_chest_info_005708.png): 按钮画的是
     "紫宝石图标 + 裸数字 30", OCR 只读得到 30(没有单位), 文字判据全不命中 ->
     机器人真花掉 30 紫宝石(顶栏 114->84)。现在这颗按钮带内宝石像素 362, 点色直接拒。
用法(项目根目录): python -X utf8 test_price_guard.py     # 退出码 0 = 全通过
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np
from PIL import Image, ImageDraw

import colorprint as cp
from pages.base import find_close_badge
from pages.chest_info import (CLOSE_POS, GEM_MIN, ChestInfoPage, gem_cost_pixels)
from vision import TBox

# 实测锚点: 免费和付费是同一颗黄按钮, 外接框中心完全重合(所以只能靠带内颜色分)
BTN_XY = (275, 795)
W, H = cp.REF_SIZE

# 真机帧 -> 该不该点。free: 点色必须点中黄按钮; paid: 一次都不许点按钮
# 帧表**从 tools/pick_print.py 的 LABELS['chest_info'] 派生**, 不硬编码文件名:
#   哪些帧是宝箱面板 = LABELS 说了算; 该不该点 = 文件名说了算
#   chest_info_paid_* = 要花钱(每张都人眼核对过带内紫宝石像素), 其余 = 免费。
# 上一轮就是把真值绑在 shots_live/ 的具体文件名上, 结果"每跑一次真机就假失败一次"。
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from pick_print import LABELS as _LABELS


def _real_frames():
    out = []
    for name in _LABELS['chest_info']:
        stem = os.path.splitext(os.path.basename(name))[0]
        rel = 'shots/%s.png' % stem
        if not os.path.exists(os.path.join(ROOT, rel)):
            raise AssertionError('LABELS 里登记了 %s, 但 shots/ 里没有' % stem)
        out.append((rel, 'paid' if stem.startswith('chest_info_paid_') else 'free'))
    out.sort()
    kinds = {k for _r, k in out}
    if kinds != {'free', 'paid'}:
        raise AssertionError('帧表退化成一个极端了: %s' % kinds)
    return out


REAL = _real_frames()
N_PAID = sum(1 for _r, k in REAL if k == 'paid')

FAILS = []


def check(cond, msg, detail=''):
    print('%-4s %-52s -> %s' % ('PASS' if cond else 'FAIL', msg, detail))
    if not cond:
        FAILS.append(msg + ' | ' + detail)


class F:
    """最小 ScreenFeature 替身: 只给图, 默认不给文字框(证明这条路不需要 OCR)"""

    def __init__(self, img, boxes=None):
        self.img = img
        self.boxes = boxes
        self.joined = ' '.join(b.text for b in boxes) if boxes else ''


class Ctx:
    """假 ctx: 记点击; need_text() 一被调用就是事故(本页声明了 act_needs_ocr=False)"""

    dry_run = False

    def __init__(self, img, boxes=None):
        self.f = F(img, boxes)
        self.clicks = []
        self.chest_target = None    # 大厅交接来的宝箱格 key
        self._blacklist = set()       # 判付费后拉黑的格, 见 pages/base.py chest_slot_key

    def block(self, key, sec, why=''):
        self._blacklist.add(key)

    def is_blocked(self, key):
        return key in self._blacklist

    def acted(self, key, gap=6.0):
        return False

    def need_text(self):
        raise AssertionError('chest_info 是纯点色页, 动作层不许再跑 OCR')

    def click(self, x, y):
        self.clicks.append((int(x), int(y)))


def box(text, cx, cy, w=60, h=26):
    return TBox(text, int(cx - w / 2), int(cy - h / 2), w, h)


def load(rel):
    im = Image.open(os.path.join(ROOT, rel)).convert('RGB')
    return im.resize(cp.REF_SIZE) if im.size != cp.REF_SIZE else im


def on_button(pt):
    """这个点击算不算"点了开箱按钮"(付费护栏最怕的就是这个)"""
    return ChestInfoPage.BTN_BOX[0] <= pt[0] <= ChestInfoPage.BTN_BOX[2] \
        and ChestInfoPage.BTN_BOX[1] <= pt[1] <= ChestInfoPage.BTN_BOX[3]


def is_close(pt):
    return abs(pt[0] - CLOSE_POS[0]) <= 12 and abs(pt[1] - CLOSE_POS[1]) <= 12


# ---- 合成帧: 只画"点色看得见"的东西(黄按钮 / 带内紫宝石), 文字靠文本框模拟 ----
def synth(btn=True, gem=False, dark=False):
    a = np.full((H, W, 3), 0x20 if dark else 0, dtype=np.uint8)
    im = Image.fromarray(a)
    d = ImageDraw.Draw(im)
    if btn:
        d.rectangle([193, 764, 357, 826], fill=(0xFD, 0xCA, 0x33))   # 实测按钮外接框
    if gem:
        d.rectangle([240, 800, 320, 830], fill=(222, 62, 246))       # 按钮内下半: 紫宝石图标
    return im


def run(img, boxes=None):
    ctx = Ctx(img, boxes)
    acted = ChestInfoPage().act(ctx)
    return ctx, acted


def main():
    print('[0] 声明自检: 本页必须是纯点色页(主循环才不会为它跑 OCR)')
    p = ChestInfoPage()
    check(p.act_needs_ocr is False, 'chest_info.act_needs_ocr 必须是 False',
          str(p.act_needs_ocr))
    check(len(p.fingerprints()[0]) >= 5, 'chest_info 必须有指纹(定页不靠 OCR)',
          '%d 个判色点' % len(p.fingerprints()[0]))

    print('')
    print('[1] 真机帧回放: 免费帧点黄按钮 / 付费帧只点关闭 (全程 boxes=None, 零 OCR)')
    n_free = n_paid = 0
    for rel, kind in REAL:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            check(False, '真机帧缺失 ' + rel, '帧不在, 护栏就没法回归')
            continue
        img = load(rel)
        gems = gem_cost_pixels(img, *BTN_XY)
        ctx, acted = run(img)
        if kind == 'free':
            n_free += 1
            hit = len(ctx.clicks) == 1 and not on_button(ctx.clicks[0]) is False \
                and abs(ctx.clicks[0][0] - BTN_XY[0]) <= 3 \
                and abs(ctx.clicks[0][1] - BTN_XY[1]) <= 3
            check(hit and acted, '免费 %s' % os.path.basename(rel),
                  '带内宝石 %d 点击 %s' % (gems, ctx.clicks))
        else:
            n_paid += 1
            btn_clicked = [c for c in ctx.clicks if on_button(c)]
            check(not btn_clicked and ctx.clicks and all(is_close(c) for c in ctx.clicks),
                  '付费 %s' % os.path.basename(rel),
                  '带内宝石 %d>=%d 点击 %s' % (gems, GEM_MIN, ctx.clicks))
    print('    %d 免费 / %d 付费, 免费全点中按钮、付费一次都没点按钮' % (n_free, n_paid))

    print('')
    print('[2] 合成帧: 颜色是主判据, OCR 只有否决权(能拒点, 永远不能放行)')
    SYN = [
        # (说明, 图, 文本框, 期望是否点按钮)
        ('黄按钮 + 带内空白 -> 点(免费)', synth(), None, True),
        ('黄按钮 + 带内紫宝石 -> 拒(点色判付费)', synth(gem=True), None, False),
        ('同一帧本来就带文字: 解锁 + 20分(所需时长) -> 仍点',
         synth(), [box('解锁', 278, 785), box('20分', 292, 815)], True),
        ('带内无宝石但写着 解锁-5分(真倒计时) -> 拒',
         synth(), [box('解锁 -5分', 278, 785)], False),
        ('按钮旁 3px 就是 ￥68(月卡血泪) -> 拒',
         synth(), [box('解锁', 278, 785), box('￥68', 278, 788)], False),
        ('旁边另一个框写着 29 钻石 -> 拒',
         synth(), [box('开启', 278, 785), box('29 钻石', 278, 740)], False),
        ('宝石计费画成图标 + 裸数字 30(真机 00:57) -> 拒',
         synth(gem=True), [box('开启', 275, 782), box('30', 292, 814)], False),
        ('就算 OCR 漏读成裸数字, 文字本身也判得掉 -> 拒',
         synth(), [box('开启', 275, 782), box('30', 292, 814)], False),
        ('裸数字在按钮上方(奖励那排) -> 不算价格, 仍点',
         synth(), [box('解锁', 278, 785), box('30', 292, 700)], True),
        ('价格离得远(不在按钮邻域) -> 仍点',
         synth(), [box('解锁', 278, 785), box('￥68', 120, 300)], True),
        ('没看到黄按钮(广告/已开箱/别的版式) -> 关面板走人',
         synth(btn=False), None, False),
    ]
    for desc, img, boxes, want_free in SYN:
        ctx, acted = run(img, boxes)
        got_free = any(on_button(c) for c in ctx.clicks)
        if want_free:
            check(got_free and acted and len(ctx.clicks) == 1, desc, str(ctx.clicks))
        else:
            check(not got_free and acted and all(is_close(c) or not on_button(c)
                                                 for c in ctx.clicks), desc, str(ctx.clicks))
    # 关面板必须真点到关闭 X(旧版 (478,115) 偏上 48px -> 关不掉 -> 7 张 stuck 卡死截图)
    ctx, _ = run(synth(btn=False))
    check(ctx.clicks == [CLOSE_POS], '认不出关闭徽章时才退回标定 X 坐标', str(ctx.clicks))
    ctx, _ = run(synth(gem=True))
    check(ctx.clicks == [CLOSE_POS], '付费帧也是关面板(不是点按钮后干等)', str(ctx.clicks))

    print('')
    print('[3] 带内宝石像素单元判据(阈值 %d 两侧必须干净分开)' % GEM_MIN)

    def band_only(rgb):
        a = np.zeros((H, W, 3), dtype=np.uint8)
        a[BTN_XY[1]:BTN_XY[1] + 40, BTN_XY[0] - 50:BTN_XY[0] + 50] = rgb
        return Image.fromarray(a)

    for desc, rgb, want_paid in [
            ('紫宝石(实测主色 222,62,246) -> 判付费', (222, 62, 246), True),
            ('橙色时钟图标(免费按钮那行) -> 不判付费', (232, 150, 40), False),
            ('黄色按钮底 -> 不判付费', (245, 190, 60), False),
            ('深蓝底(按钮外) -> 不判付费', (30, 30, 60), False)]:
        n = gem_cost_pixels(band_only(rgb), *BTN_XY)
        check((n >= GEM_MIN) == want_paid, desc, '带内宝石像素 %d' % n)
    for rel, kind in REAL:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            continue
        n = gem_cost_pixels(load(rel), *BTN_XY)
        ok = n >= GEM_MIN if kind == 'paid' else n == 0
        if 'dbg' in rel or 'stuck_0108' in rel or 'iron' in rel:
            check(ok, '真机带内像素 %-40s %s' % (os.path.basename(rel), kind),
                  '%d (期望 %s)' % (n, '>=60' if kind == 'paid' else '0'))

    print('')
    print('SUMMARY failures = %d' % len(FAILS))
    for m in FAILS:
        print('  - ' + m)
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())