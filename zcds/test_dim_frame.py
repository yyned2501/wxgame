# -*- coding: utf-8 -*-
r"""压暗闸门: 全屏过场动画把整帧压暗时, 判页结论**不许变成另一页**

现场(真机 2026-09-04 09:07:10, `shots_live/ocr_battle_090710.png`):
  战斗里蹦出「传说卡牌来袭! 5% 超幸运!」全屏过场动画 —— 大法师 + 红色斜光带 + 黄色横幅
  **盖住整屏并把每一像素压暗**(全帧 mean 168.9 -> 137.2)。
  battle 指纹的两个推条单元 + 右下聊天气泡单元**同时 0/15** -> 连续 2 帧点色零命中
  -> 花一次全图 OCR -> OCR 认出 battle(0.90) -> 照常点格子。
  代价 = 一次 675ms OCR + 约 6s 不出手, **不是卡死**, 动画放完(下一帧 mean 167.5)自动恢复。

为什么**不**给 battle 补一个"压暗形态"指纹:
  压暗不是等比缩放 —— 实测 蓝条 (29,139,210)->(30,114,167) 三通道系数 1.03/0.82/0.80,
  气泡 (249,254,254)->(213,217,217) 系数 0.855/0.854/0.854, 而且动画本身在动,
  任何一组固定坐标都只能蒙中某一相位 => 硬凑的形态会在别的帧里制造**假全中**, 比零命中危险得多。

所以这道锁的真正判据是 [4]: **把 295 张语料整体压暗两档, 任何一帧都不许被"另一页"认领。**
零命中只是慢一点, 误判成别的页会点错按钮(§31 那张弹窗就是这么把 result 的动作层带沟里的)。
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import pick_print as pk                      # noqa: E402
from pages import ALL_PAGES                  # noqa: E402
from pages.base import match_print           # noqa: E402
from pages.battle import BattlePage          # noqa: E402

LIVE = os.path.join(ROOT, 'shots_live')


DARK = os.path.join(LIVE, 'ocr_battle_090710.png')      # 压暗帧(过场动画盖屏)
BRIGHT = os.path.join(LIVE, 'dbg_105_battle_090701.png')  # 同一场战斗 9 秒前的正常帧
DIMS = (0.82, 0.70)
fail = []


def check(cond, msg):
    if not cond:
        fail.append(msg)
    print('  %s   %s' % ('ok  ' if cond else 'FAIL', msg))


def load(p):
    from PIL import Image
    im = Image.open(p).convert('RGB')
    if im.size != (552, 1006):
        im = im.resize((552, 1006))
    return np.asarray(im, dtype=np.uint8)


def unit_hits(img):
    """battle 两形态逐单元的命中数, 用于把"整帧压暗 => 指纹全灭"钉死在测试里"""
    out = []
    for form in BattlePage.prints:
        u = []
        for i in range(0, len(form), 5):
            pts = form[i:i + 5]
            u.append(sum(1 for x, y, c in pts
                         if int(np.abs(img[y, x].astype(int) - np.array(pk.cp.c2rgb(c))).max()) <= pk.cp.tolerance(85)))
        out.append(u)
    return out


# ---------------------------------------------------------------- [1] 已知盲区
print('[1] 压暗帧上 battle 指纹的命中数(钉死已知盲区, 别以为它一直能中)')
if not os.path.exists(DARK):
    print('  SKIP  现场帧不在仓库里(shots_live 不进 git), 采到真机帧后再跑')
else:
    dark = load(DARK)
    hits = unit_hits(dark)
    print('  dark  mean=%.1f  units=%s' % (dark.mean(), hits))
    if sum(map(sum, hits)) != 0:
        fail.append('[1] 压暗帧上 battle 指纹竟然还有命中: %s' % hits)
    br = load(BRIGHT)
    hb = unit_hits(br)
    print('  bright mean=%.1f  units=%s' % (br.mean(), hb))
    if not all(v == 5 for u in hb for v in u):
        fail.append('[1] 对照帧(正常战斗)battle 指纹没全中: %s' % hb)
    if br.mean() - dark.mean() < 20:
        fail.append('[1] 对照帧与压暗帧亮度差 <20, 现场帧取错了')

# ------------------------------------------------- [2] 压暗帧不许被任何页认领
print('[2] 压暗帧 match_print 不许给出任何页(只许零命中 -> 交 OCR)')
if os.path.exists(DARK):
    pg, score, src = match_print(ALL_PAGES, dark)
    print('  match_print -> %s score=%.2f src=%s' % (pg.name if pg else None, score, src))
    if pg is not None:
        fail.append('[2] 压暗帧被 %s 以 %.2f 认领(会点错按钮)' % (pg.name, score))
    if score >= 0.20:
        fail.append('[2] 压暗帧最高分 %.2f 已够到软命中门限' % score)
    pg2, sc2, src2 = match_print(ALL_PAGES, br)
    print('  对照帧 -> %s %.2f %s' % (pg2.name if pg2 else None, sc2, src2))
    if pg2 is None or pg2.name != 'battle':
        fail.append('[2] 对照帧没被 battle 全中, 现场帧配对取错')

# ---------------------------------------- [3] 逐档压暗全量语料: 不许改判成别的页
print('[3] 295 张语料 x 压暗 %s: 结论只许"同一页"或"无人认领"' % (DIMS,))
corp = pk.corpus()
n_hit = 0
n_none = 0
bad = []
for label, path, img in corp:
    want = pk.group_of(label)
    for k in DIMS:
        dim = np.clip(img.astype(np.float32) * k, 0, 255).astype(np.uint8)
        pg, score, src = match_print(ALL_PAGES, dim)
        if pg is None:
            n_none += 1
        elif pg.name == want:
            n_hit += 1
        else:
            bad.append('%s x%.2f -> %s %.2f %s (应为 %s)' % (path, k, pg.name, score, src, want))
print('  仍判对页 %d / 无人认领 %d / **误判成别的页 %d**  (共 %d 次判定)'
      % (n_hit, n_none, len(bad), len(corp) * len(DIMS)))
for b in bad[:10]:
    print('  !! ' + b)
if bad:
    fail.append('[3] %d 帧压暗后被误判成别的页' % len(bad))

# ------------------------------------- [4] 压暗率统计: 别把闸门做成"永远零命中"
print('[4] 压暗后仍全中的比例(过低说明指纹只靠亮度, 过高说明它压根没在认结构)')
rate = n_hit / float(len(corp) * len(DIMS))
print('  仍判对页的比例 = %.1f%%' % (rate * 100))
if rate > 0.60:
    fail.append('[4] 压暗 0.70 之后还有 %.0f%% 全中, 指纹疑似只认亮度' % (rate * 100))

# ------------------------------------- [5] 锁住"设计内盲区"分类器本身
print('[5] known_blind: 放行要看一条独立证据(同一次 step 的 OCR 复核帧, 逐字节相同)')
import known_blind as kb
import PIL.Image as I

TMPD = os.path.join(ROOT, 'scratch', 'tmp', 'kb')
if not os.path.isdir(TMPD):
    os.makedirs(TMPD)


def _mk(name, seed):
    """造一张参考分辨率的假帧并落盘(同 seed => 两张图逐字节相同)"""
    import colorprint as cp
    w, h = cp.REF_SIZE
    a = np.random.default_rng(seed).integers(0, 255, (h, w, 3), dtype=np.uint8)
    p = os.path.join(TMPD, name)
    I.fromarray(a).save(p)
    return p


def _pair(page, s1, s2, seed1=1, seed2=None):
    """写一对 dbg/ocr 证据帧 -> 返回 dbg 那条的路径"""
    _mk('dbg_9_%s_%06d.png' % (page, s1), seed1)
    _mk('ocr_%s_%06d.png' % (page, s2), seed2 if seed2 is not None else seed1)
    return os.path.join(TMPD, 'dbg_9_%s_%06d.png' % (page, s1))


def ok(r):
    return r is not None


def no(r):
    return r is None


for tag, cond, why in [
    ('同秒+同页+逐字节相同 -> 放行',
     ok(kb.unclaimed_note(_pair('result', 100000, 100001), 0.067, None)), 'a'),
    ('差 11 秒 -> 不放行(不是同一次 step)',
     no(kb.unclaimed_note(_pair('result', 110000, 110011), 0.067, None)), 'b'),
    ('页名不在指纹表(新页面) -> 绝不放行',
     no(kb.unclaimed_note(_pair('banana', 120000, 120000), 0.067, None)), 'c'),
    ('两张图不一样 -> 不放行(凭证不成立)',
     no(kb.unclaimed_note(_pair('result', 130000, 130000, 1, 2), 0.067, None)), 'd'),
    ('有页认领(src 非空) -> 不放行(认错页零容忍)',
     no(kb.unclaimed_note(_pair('result', 140000, 140001), 0.99, 'soft')), 'e'),
    ('有页贴着软命中门限抢(0.20) -> 不放行',
     no(kb.unclaimed_note(_pair('result', 150000, 150001), 0.20, None)), 'f'),
]:
    check(cond, tag)

# 现场那一对: 压暗帧必须被认成盲区, 它 9 秒前的正常帧必须"不放行"(它本来就能定页)
if os.path.exists(DARK):
    pg, score, src = match_print(ALL_PAGES, load(DARK))
    check(kb.unclaimed_note(DARK, score, src) is not None,
          '真机压暗帧 %s -> 分类器认账(score=%.3f src=%s)' % (os.path.basename(DARK), score, src))
else:
    print('  SKIP 现场压暗帧不在(%s 不进仓库)' % os.path.relpath(DARK, ROOT))
if os.path.exists(BRIGHT):
    pg2, score2, src2 = match_print(ALL_PAGES, load(BRIGHT))
    check(kb.unclaimed_note(BRIGHT, score2, src2) is None,
          '对照正常帧 %s -> 不许被豁免进盲区(src=%s)' % (os.path.basename(BRIGHT), src2))
check(kb.FP_PAGES and 'battle' in kb.FP_PAGES and 'unknown' not in kb.FP_PAGES,
      '分类器用的指纹页表就是运行时候那张表(新页面标签过不了闸)')
check(kb.blind_cap(1971) == 9 and kb.blind_cap(100) == 4,
      '盲区帧数上界: 1971 张 -> 9, 100 张 -> 4 (实测当前 1 张)')

print()
if fail:
    for f in fail:
        print('!! ' + f)
    print('SUMMARY failures = %d' % len(fail))
    sys.exit(1)
print('ALL DONE 压暗闸门回归全绿')