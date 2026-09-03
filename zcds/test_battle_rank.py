# -*- coding: utf-8 -*-
"""离线回归: 战斗页点格子的优先级 (pages/battle.py::rank_cell) —— 不开窗口, 只读 shots

用户 2026-09-03 的原话:
  "现在战斗中只会开 25 的, 开完就不开了。应该要先开 50 的矿, 然后开 50 的兵营,
   然后在考虑开 25 的。如果都没有就开 100 的"
旧版 rank_cell 是 "矿 > 50 > 2d > 25", 而价格识别当时把绝大多数格子塞进 "2d"(分不清) 桶,
"50 优先" 从未生效; 矿图标判定(_is_rock)又对头盔/问号恒为真 -> 实际退化成一味点最下面的格子。

用法: python -X utf8 test_battle_rank.py     退出码 0 = 通过
"""
import glob
import os
import sys
import time

T0 = time.time()

D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
from PIL import Image

from battle_scan import scan_battle_cells
from pages.battle import BattlePage, rank_cell

FAILS = []


def check(cond, msg):
    print(('  ok    ' if cond else '  FAIL  ') + msg)
    if not cond:
        FAILS.append(msg)


def cell(cls, icon, x=200, y=700, w=22, h=12, white=True):
    return dict(x=x, y=y, w=w, h=h, white=white, mine=(icon == 'ore'),
                icon=icon, clip=False, cls=cls)


print('[1] 用户指定的档位顺序')
order = [('50矿', cell(50, 'ore')), ('50兵营', cell(50, 'barracks')),
         ('50问号', cell(50, 'unknown')), ('25', cell(25, 'unknown')),
         ('100', cell(100, 'barracks')), ('250', cell(250, 'barracks'))]
keys = [rank_cell(c) for _, c in order]
check(keys == sorted(keys), ' -> '.join(n for n, _ in order) + ' 依次递减 %s' % (keys,))
for i in range(1, len(keys)):
    check(keys[i - 1] < keys[i], '%s 必须先于 %s' % (order[i - 1][0], order[i][0]))

print('\n[2] 同档内的次序: 靠塔侧先开, 再按行从下往上')
a = cell(25, 'unknown', x=300, y=758)          # cx>=276 且 y<=800 -> 靠塔侧
b = cell(25, 'unknown', x=100, y=758)
check(rank_cell(a) < rank_cell(b), '同一行里靠塔(x 大)的先开')
c = cell(25, 'unknown', x=300, y=694)          # 和 a 同在靠塔侧, 只是更靠上
check(rank_cell(a) < rank_cell(c), '同一列里下面(y 大)的先开')

print('\n[3] 整张合成棋盘: 出手顺序必须完全等于用户序列')
board = [cell(250, 'barracks'), cell(25, 'unknown'), cell(100, 'barracks'),
         cell(50, 'unknown'), cell(50, 'barracks'), cell(50, 'ore')]
got = [c['cls'] * 100 + {'ore': 0, 'barracks': 1, 'unknown': 2}[c['icon']]
       for c in sorted(board, key=rank_cell)]
check(got == [5000, 5001, 5002, 2502, 10001, 25001], '实际顺序 %s' % got)

print('\n[4] act(): 只点白色可点的, 认不出价钱的(cls=3)绝不点')


class FakeFrame:
    def __init__(self, img):
        self.img = img

    def has(self, *words):
        return False


class FakeCtx:
    def __init__(self, img, print_confirmed=True):
        self.f = FakeFrame(img)
        self.print_confirmed = print_confirmed
        self.clicked_cells = {}
        self.last_cell = 0.0
        self.clicks = []

    def click(self, x, y):
        self.clicks.append((x, y))


img = Image.open(os.path.join(D, 'shots', 'battle_full.png')).convert('RGB')
cells = scan_battle_cells(img)
ghost = [c for c in cells if c['cls'] == 3]
check(bool(ghost), '语料帧里有 cls=3 的假标签(左下角"镜头复位") %s'
      % [(c['x'], c['y']) for c in ghost])
ctx = FakeCtx(img)
BattlePage().act(ctx)
check(not any((c['x'] + c['w'] // 2, c['y'] + c['h'] // 2) == ctx.clicks[0] for c in ghost),
      'act() 没有点到 cls=3 的假标签 -> %s' % ctx.clicks)

print('\n[5] 真机全语料: 有 50 矿的帧必须先点 50 矿')
paths = sorted(glob.glob(os.path.join(D, 'shots', 'battle*.png'))) + \
    sorted(glob.glob(os.path.join(D, 'shots', 'exp_*.png'))) + \
    sorted(glob.glob(os.path.join(D, 'shots', 'flow2_*.png'))) + \
    sorted(glob.glob(os.path.join(D, 'shots_live', 'dbg_*_battle_*.png')))
n_ore = n_50 = n_act = 0
for p in paths:
    ck = [c for c in scan_battle_cells(Image.open(p).convert('RGB'))
          if c['white'] and c['cls'] != 3]
    if not ck:
        continue
    n_act += 1
    w = min(ck, key=rank_cell)
    if any(c['cls'] == 50 and c['icon'] == 'ore' for c in ck):
        n_ore += 1
        check_ok = w['cls'] == 50 and w['icon'] == 'ore'
        if not check_ok:
            check(False, '%s 有 50 矿却点了 cls=%s/%s' % (os.path.basename(p), w['cls'], w['icon']))
    if any(c['cls'] == 50 for c in ck):
        n_50 += 1
        if w['cls'] != 50:
            check(False, '%s 有 50 却点了 %s' % (os.path.basename(p), w['cls']))
check(True, '%d 帧可出手 / 其中 %d 帧有 50 矿、%d 帧有 50 -> 全部按档位先点 50'
      % (n_act, n_ore, n_50))

print('\n[6] 兜底定页守卫: 不再要求"看到矿"(矿只占 14%), 改成 >=2 个格子图标')
n_icon = sum(1 for p in paths for c in scan_battle_cells(Image.open(p).convert('RGB'))
             if c['icon'])
n_mine = sum(1 for p in paths for c in scan_battle_cells(Image.open(p).convert('RGB'))
             if c['mine'])
check(n_mine < n_icon * 0.5, '带图标标签 %d 个, 其中矿只有 %d 个 (%.0f%%) —— 旧守卫会漏判大半'
      % (n_icon, n_mine, 100.0 * n_mine / max(1, n_icon)))

print('\n[7] 第一名点过必须换第二名 (旧版只试 clickable[0], 真机 95s 一次没点)')
import pages.battle as B

board = [cell(50, 'ore', x=100, y=700), cell(50, 'barracks', x=300, y=700),
         cell(25, 'unknown', x=100, y=760)]
orig_scan = B.scan_battle_cells
B.scan_battle_cells = lambda img, *a, **k: [dict(c) for c in board]
try:
    page = BattlePage()
    ctx = FakeCtx(img)
    picks, acts = [], []
    for _ in range(4):
        ctx.last_cell = 0.0          # 只验"拉黑后换人", 冷却由 test_battle_loop 负责
        acted = page.act(ctx)
        acts.append(acted)
        picks.append(ctx.clicks[-1] if acted else None)
    exp = [(c['x'] + c['w'] // 2, c['y'] + c['h'] // 2) for c in board]
    check(picks[:3] == exp, '按档位连点 50矿 -> 50兵营 -> 25: %s' % (picks[:3],))
    check(acts[3] is False, '三格都在拉黑期内 -> 第 4 轮不动手')
    check(isinstance(ctx.clicked_cells, dict) and len(ctx.clicked_cells) == 3,
          'clicked_cells = dict(key->点击时刻), 现有 %d 条' % len(ctx.clicked_cells))
    stale = time.time() - B.CELL_RETRY - 1
    ctx.clicked_cells = {k: stale for k in ctx.clicked_cells}
    ctx.last_cell = 0.0
    acted = page.act(ctx)
    check(acted and ctx.clicks[-1] == exp[0],
          '拉黑满 CELL_RETRY=%.0fs -> 解禁, 又点回最优的 50 矿' % B.CELL_RETRY)
finally:
    B.scan_battle_cells = orig_scan

print('\nSUMMARY failures = %d  (耗时 %.1fs)' % (len(FAILS), time.time() - T0))
sys.exit(1 if FAILS else 0)
