# -*- coding: utf-8 -*-
"""离线回归: 价格档位识别 (battle_scan._price_class) —— 不开窗口, 只吃合成字模 + 真机截图

为什么要有这个文件(2026-09-03):
  用户报"战斗中只会开 25 的, 开完就不开了"。根因有两层:
    1) 旧版把整块价格字缩到 30x18 和模板做相关, 绝大多数格子落进"分不清"桶 -> 50 优先从未生效;
    2) 改成"逐位数闭合孔"后又踩到: 截图右侧有一条黑边(游戏内容只画到第 543 列),
       贴着边界的价签末位被裁断, "50" 的 0 没了闭合孔 -> 孔签名和 "25" 一模一样, 整列被读成 25。
  所以这里同时锁两件事: 孔签名表 + 被裁末位的"左边缘断档"补救。

用法: python -X utf8 test_price_class.py     退出码 0 = 通过
"""
import os
import sys

import numpy as np

D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
from PIL import Image

from battle_scan import (_left_edge_gap, _price_class, scan_battle_cells,
                         scan_words, PRICE_SIGNS)

FAILS = []


def check(cond, msg):
    print(('  ok    ' if cond else '  FAIL  ') + msg)
    if not cond:
        FAILS.append(msg)


# ---- 手写字模(和真机同族像素字体: 只有 0 带闭合孔, 1/2/5 都没有) ----
G = {
    '0': ['.#####.', '#.....#', '#.....#', '#.....#', '#.....#', '#.....#',
          '#.....#', '#.....#', '#.....#', '#.....#', '.#####.'],
    '1': ['..#....', '.##....', '..#....', '..#....', '..#....', '..#....',
          '..#....', '..#....', '..#....', '..#....', '.###...'],
    '2': ['.#####.', '#.....#', '......#', '.....#.', '....#..', '...#...',
          '..#....', '.#.....', '#......', '#......', '#######'],
    '5': ['#######', '#......', '#......', '#####..', '.....#.', '.....##',
          '.....##', '#.....#', '#.....#', '.#####.', '.......'],
}


def word(s, gap=2, cut=0):
    """数字串 -> 二值掩膜; cut>0 时把整块词的右边切掉 cut 列(模拟贴渲染边界)"""
    cols = []
    for i, ch in enumerate(s):
        if i:
            cols.append(np.zeros((11, gap), np.uint8))
        cols.append(np.array([[1 if c == '#' else 0 for c in row] for row in G[ch]],
                             dtype=np.uint8))
    m = np.hstack(cols)
    return m[:, :m.shape[1] - cut] if cut else m


print('[1] 孔签名表本身')
check(PRICE_SIGNS == {(0, 0): 25, (0, 1): 50, (0, 1, 1): 100, (0, 0, 1): 250},
      '25/50/100/250 四档签名固定: %s' % (PRICE_SIGNS,))

print('\n[2] 未裁切价签: 四档 + 认不出的必须丢')
for s, want in (('25', 25), ('50', 50), ('100', 100), ('250', 250)):
    got = _price_class(word(s))
    check(got == want, '\"%s\" -> %s (期望 %s)' % (s, got, want))
# 价签只有 25/50/100/250 四档, 不存在别的二位数 -> 孔签名 (0,0) 一律读成 25 是设计不是 bug
for s, want in (('11', 25), ('12', 25), ('22', 25)):
    got = _price_class(word(s))
    check(got == want, '\"%s\" -> %s (期望 %s: 两位无孔 = 25)' % (s, got, want))
for s, want in (('2222', None), ('5', None), ('1', None), ('2525', None)):
    got = _price_class(word(s))
    check(got == want, '\"%s\" -> %s (期望 %s: 不是价格, 丢弃)' % (s, got, want))
check(_price_class(word('222')) == 3, '"222" 三位认不出 -> cls=3(绝不点)')

print('\n[3] 贴渲染边界被裁的价签: 必须靠左边缘断档救回来')
for s, want in (('25', 25), ('50', 50)):
    m = word(s, cut=3)                      # 末位右边掉 3 列 -> 0 的孔断了
    naive = _price_class(m)                 # 不告诉它被裁 -> 只能查表, 一律 25
    got = _price_class(m, clipped=True)
    check(got == want, '\"%s\"(裁 3 列) -> %s (期望 %s); 不告诉它被裁会读成 %s'
          % (s, got, want, naive))
for ch, arc in (('0', True), ('5', False)):
    g = np.array([[1 if c == '#' else 0 for c in r] for r in G[ch]], np.uint8)
    ys = np.where(g.any(axis=1))[0]
    gp = _left_edge_gap(g[ys.min():ys.max() + 1])
    check((gp < 3) == arc, "字模 '%s' 左边缘%s (断档 %d)" % (
        ch, '是一整条竖弧, 不断' if arc else '上半截+最底一行, 中间断', gp))

print('\n[4] 真机: 右边缘一列被裁的格子 (肉眼定案 50/50/50/25)')
p = os.path.join(D, 'shots', 'battle_live_031400.png')
if os.path.exists(p):
    a = np.asarray(Image.open(p).convert('RGB'))
    h, w = a.shape[:2]
    y0, y1 = int(0.46 * h), int(0.90 * h)
    b = a[y0:y1]
    white = ((b > 205).all(axis=2)).astype(np.uint8)
    nz = np.where(b.max(axis=2).max(axis=0) > 40)[0]
    got = {t['y']: t['cls'] for t in scan_words(white, y0, (int(nz[0]), int(nz[-1])))
           if t['x'] > 500}
    exp = {631: 50, 694: 50, 758: 50, 821: 25}
    check(got == exp, '右边缘列 y=631/694/758/821 -> %s (期望 %s)' % (got, exp))
    # 这些词必须全部带 clip 标记, 说明它们确实是"贴边被裁"而不是普通格子
    check(all(t['clip'] for t in scan_words(white, y0, (int(nz[0]), int(nz[-1])))
              if t['x'] > 500), '右边缘列全部标 clip=True')
else:
    check(False, '缺少语料 %s' % p)

print('\n[5] 认不出的三位数块不能混进可点集合')
cells = scan_battle_cells(Image.open(os.path.join(D, 'shots', 'battle_full.png')).convert('RGB'))
ghost = [c for c in cells if c['cls'] == 3]
check(ghost and all(c['x'] < 60 and c['y'] > 850 for c in ghost),
      'battle_full.png 里 cls=3 只有左下角"镜头复位"按钮 %s' % [(c['x'], c['y']) for c in ghost])
check(all(c['cls'] in (25, 50, 100, 250, 3) for c in cells if c['white']),
      '白色标签 cls 只会是 25/50/100/250/3 之一')

print('\nSUMMARY failures = %d' % len(FAILS))
sys.exit(1 if FAILS else 0)
