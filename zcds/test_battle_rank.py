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

print('\n[8] 档位盘点 tier_census(): 把「点 25 的时候还有没有没点过的 50」写进日志')
from pages.battle import tier_census, cell_key, TIER_NAMES

board8 = [cell(50, 'ore', x=100, y=700), cell(50, 'barracks', x=200, y=700),
          cell(50, 'unknown', x=300, y=700), cell(25, 'unknown', x=100, y=760),
          cell(100, 'barracks', x=200, y=760), cell(250, 'barracks', x=300, y=760)]
# 红标签: white=False, 所以它**不进** clickable, 只贡献 census 里的「红N」列
red8 = [cell('red', 'barracks', x=400, y=700, white=False),
        cell('red', 'unknown', x=400, y=760, white=False)]
c0 = tier_census(board8, set(), len(red8))
check(c0 == '在架6 可点6 红2 50矿:1 50兵:1 50问:1 25:1 100:1 250:1',
      '全部未点 -> %s' % c0)
# 把三个 50 塞进冷却表(键算法必须和 act() 用的是同一个 cell_key)
busy = {cell_key(c) for c in board8 if c['cls'] == 50}
c1 = tier_census(board8, busy, len(red8))
check(c1 == '在架6 可点3 红2 25:1 100:1 250:1', '50 全在冷却 -> %s' % c1)
# 注意不能直接判 "'50' not in": 250 里就含一个 50
check(not any(('%s:' % k) in c1 for k in ('50\u77ff', '50\u5175', '50\u95ee')),
      '50 \u4e09\u6863\u5168\u90e8\u6d88\u5931 = \u8fd9\u884c\u80fd\u8bc1\u660e\"\u70b9 25 \u65f6\u786e\u5b9e\u6ca1\u6709\u672a\u70b9\u7684 50\": %s' % c1)
check(tier_census([], set()) == '在架0 可点0 红0', '空棋盘不炸: %r' % tier_census([], set()))
check(tier_census(board8, set()) == '在架6 可点6 红0 50矿:1 50兵:1 50问:1 25:1 100:1 250:1',
      'red 缺省 0: 老调用点不传第三个参数也不会没了这一列')
check(TIER_NAMES[rank_cell(cell(50, 'unknown'))[0]] == '50\u95ee'
      and TIER_NAMES[rank_cell(cell(30, 'unknown'))[0]] == '\u5206\u4e0d\u6e05',
      'TIER_NAMES 和 rank_cell 的档位编号对齐')

import logging

recs = []


class _Cap(logging.Handler):
    def emit(self, r):
        recs.append(r.getMessage())


_lg = logging.getLogger()
_old_lvl = _lg.level
_lg.setLevel(logging.DEBUG)
_cap = _Cap()
_saved = _lg.handlers[:]   # 摘掉根 logger 原有 handler, 别让这条日志同时泄到 stderr
_lg.handlers = [_cap]
B.scan_battle_cells = lambda img, *a, **k: [dict(c) for c in board8 + red8]
try:
    ctx8 = FakeCtx(img)
    BattlePage().act(ctx8)
finally:
    B.scan_battle_cells = orig_scan
    _lg.handlers = _saved
    _lg.setLevel(_old_lvl)
line8 = [r for r in recs if '\u70b9\u683c\u5b50' in r]
check(len(line8) == 1 and '| 在架6 可点6 红2 50矿:1' in line8[0],
      'act() 日志尾巴带盘点: %s' % (line8[0][-70:] if line8 else '<无>'))


print('\n[9] 白标签判据不许随地图底色漂移 (真机 2026-09-04: 用户「战斗中都不会点格子了」)')
# 根因: 旧掩膜是固定三通道 >205。浅色地图把棋盘底色从 ~200 抬到 215~235, 整块棋盘糊成
# 一个超宽连通块 -> scan_words 要 2~3 个 20px 宽数字块, 巨块被丢弃 -> 全天 2349 帧战斗语料
# 里 600 帧(25%)一个格子都扫不到; 真机日志「在架」从早 8 点前的 avg 4.4~7.2/max 23
# 塌成 9 点后的 avg 1.0/max 1。修完(局部对比 + 亮盘兜底降门)真机 avg 回到 6.4~8.0/max 17。
import numpy as np

from battle_scan import WHITE_BASE, scan_words


def _board(a):
    h, w = a.shape[:2]
    y0, y1 = int(0.46 * h), int(0.90 * h)
    b = a[y0:y1]
    nz = np.where(b.max(axis=2).max(axis=0) > 40)[0]
    content = (int(nz[0]), int(nz[-1])) if nz.size else None
    red = ((b[:, :, 0] > 170) & (b[:, :, 1] < 95) & (b[:, :, 2] < 95)).astype(np.uint8)
    return y0, b, content, scan_words(red, y0, content)


def _old_words(a):
    """旧判据(固定 >205) + 完全相同的切词/去红逻辑 -> 用来证明新判据严格更好"""
    y0, b, content, rwords = _board(a)
    white = ((b > WHITE_BASE).all(axis=2)).astype(np.uint8)
    return [t for t in scan_words(white, y0, content) if t['cls'] != 3
            if not any(abs(c['x'] + c['w'] // 2 - (t['x'] + t['w'] // 2)) < 20
                       and abs(c['y'] + c['h'] // 2 - (t['y'] + t['h'] // 2)) < 16 for c in rwords)]


BRIGHT = os.path.join(D, 'shots_live', 'dbg_510_battle_102511.png')   # 浅色地图, 棋盘 p50=216
DARK = os.path.join(D, 'shots_live', 'dbg_446_battle_082054.png')     # 深色地图, 棋盘 p50=199


def _white(a):
    return [c for c in scan_battle_cells(a) if c['white'] and c['cls'] != 3]


def _shift(a, d):
    return np.clip(a.astype(np.int16) + d, 0, 255).astype(np.uint8)


for tag, p, level, lo in (('亮图', BRIGHT, 216, 3), ('暗图', DARK, 199, 4)):
    if not os.path.exists(p):
        check(False, '缺少语料 %s' % p)
        continue
    a = np.asarray(Image.open(p).convert('RGB'))
    cs = _white(a)
    mn50 = int(np.median(_board(a)[1].min(axis=2)))
    check(abs(mn50 - level) <= 6, '%s 棋盘 min 通道中位数 %d (登记值 %d)' % (tag, mn50, level))
    check(len(cs) >= lo + 1, '%s 现在能扫到 %d 个可点格子 %s' % (
          tag, len(cs), [(c['x'], c['y'], c['cls'], c['icon']) for c in cs]))
    if tag == '亮图':
        # 暗图上旧判据碰巧还能用(差 1 个), 亮图上它一个标签都交不出来 —— 这就是现场事故
        check(len(_old_words(a)) == 0,
              '亮图 旧的固定 >%d 扫到 %d 个可点格子 -> 正是这个判据把格子全吃掉的'
              % (WHITE_BASE, len(_old_words(a))))
    # 整体再压亮 20(比全语料最亮的地图 p50=218 还亮) -> 必须还看得见格子
    up = len(_white(_shift(a, 20)))
    check(up >= lo, '%s 压亮 +20 (min 通道中位数 %d) 还剩 %d 个可点格子 (亮盘兜底降门生效)'
          % (tag, int(np.median(_board(_shift(a, 20))[1].min(axis=2))), up))
    # 压暗 30 也不能丢(夜战/弹窗压暗闸门之外的正常变化)
    check(len(_white(_shift(a, -30))) >= lo, '%s 压暗 -30 还剩 %d 个' % (
          tag, len(_white(_shift(a, -30)))))

# 全语料等距抽样: 新判据必须严格优于旧的固定阈值, 且「看不见格子」的帧必须少于一半
sub = paths[::13]
n_new = n_old = e_new = e_old = 0
for p in sub:
    a = np.asarray(Image.open(p).convert('RGB'))
    cw, co = _white(a), _old_words(a)
    n_new += len(cw); n_old += len(co)
    e_new += not cw; e_old += not co
check(n_new >= n_old * 1.4, '抽样 %d 帧: 新判据 %d 个可点格子 vs 旧判据 %d 个 (%.2f 倍)' % (
      len(sub), n_new, n_old, n_new / float(max(1, n_old))))
check(e_new <= len(sub) * 0.25, '抽样里「一个可点格子都扫不到」的帧 %d/%d = %.1f%% (旧判据 %.1f%%)' % (
      e_new, len(sub), 100.0 * e_new / len(sub), 100.0 * e_old / len(sub)))

print('\n[10] 「一格都点不了」要说清是买不起还是看不见, 且发牌帧不许报警 (2026-09-04 §34.7)')
_red_only = [dict(c) for c in red8]     # 红标签 white=False -> 可点集为空, 但看得见
_nothing = []   # 连红标签都没扫到 = 判据瞎了的形状
_seen = []


class _Cap10(logging.Handler):
    def emit(self, r):
        _seen.append(r.getMessage())


_lg.setLevel(logging.DEBUG)
_saved10 = _lg.handlers[:]
_lg.handlers = [_Cap10()]
try:
    B._LAST_EMPTY_NOTE[0] = 0.0
    B._BLIND_STREAK[0] = 0
    B.scan_battle_cells = lambda im, *a, **k: [dict(c) for c in _red_only]
    acted10 = BattlePage().act(FakeCtx(img))           # 1) 看得见, 只是买不起
    B.scan_battle_cells = lambda im, *a, **k: list(_nothing)
    BattlePage().act(FakeCtx(img))                     # 2) 节流窗口内: 不许刷屏
    B._LAST_EMPTY_NOTE[0] = B._BLIND_STREAK[0] = 0
    BattlePage().act(FakeCtx(img))                     # 3) 整盘零价签的第 1 帧
    B._LAST_EMPTY_NOTE[0] = 0.0
    BattlePage().act(FakeCtx(img))                     # 4) 连续第 2 帧 -> 才许报警
    BattlePage().act(FakeCtx(img))                     # 5) 又被节流吃掉
finally:
    streak10 = B._BLIND_STREAK[0]
    B.scan_battle_cells = orig_scan
    _lg.handlers = _saved10
    _lg.setLevel(_old_lvl)
    B._LAST_EMPTY_NOTE[0] = B._BLIND_STREAK[0] = 0
_empty_lines = [r for r in _seen if '[战斗] 无可点' in r]
check(acted10 is False, '无可点的帧不动手: acted=%s' % acted10)
check(len(_empty_lines) == 3, '20s 节流: 5 帧只留 3 条 -> %s' % len(_empty_lines))
check(len(_empty_lines) > 0 and '在架0 可点0 红2' in _empty_lines[0],
      '红标签数进 census: %s' % (_empty_lines[0] if _empty_lines else '<无>',))
check(len(_empty_lines) > 0 and '钱不够' in _empty_lines[0],
      '「买不起」要说清: %s' % (_empty_lines[0] if _empty_lines else '<无>',))
check(len(_empty_lines) > 1 and '红0' in _empty_lines[1] and 'white_mask' not in _empty_lines[1],
      '零价签第 1 帧不许报警(真机 R41 那 2 次都是刚进场的发牌帧): %s'
      % (_empty_lines[1] if len(_empty_lines) > 1 else '<无>',))
check(len(_empty_lines) > 2 and 'white_mask' in _empty_lines[2] and '连续2帧' in _empty_lines[2],
      '连续 2 帧零价签才升级成报警: %s'
      % (_empty_lines[2] if len(_empty_lines) > 2 else '<无>',))
check(streak10 == 3, '被节流吃掉的帧也要记账: 第 4 帧报警时算到 2, 第 5 帧继续累加 -> streak=%s' % streak10)

# [10b] 跨场不累积(真机 R42 误报): 上一局收场帧把 streak 顶到 2, 新一局进场清零后
#       第一帧零价签必须还是"第 1 帧"提示 —— 不许借旧账升级成"判据又瞎了"报警
print('\n[10b] 进场比赛 reset_blind_streak 后, 发牌帧不许借上一场的旧账报警 (R42)')
_seen10b = []


class _Cap10b(logging.Handler):
    def emit(self, r):
        _seen10b.append(r.getMessage())


_lg.setLevel(logging.DEBUG)
_saved10b = _lg.handlers[:]
_lg.handlers = [_Cap10b()]
try:
    B._BLIND_STREAK[0] = 2                       # 模拟: 上一局收场动画已连 2 帧零价签
    B.reset_blind_streak()
    check(B._BLIND_STREAK[0] == 0, '进场必须清零: streak=%d' % B._BLIND_STREAK[0])
    B._LAST_EMPTY_NOTE[0] = 0.0
    B.scan_battle_cells = lambda im, *a, **k: []
    BattlePage().act(FakeCtx(img))               # 新一局第 1 帧: 棋盘还没发牌
finally:
    streak10b = B._BLIND_STREAK[0]
    B.scan_battle_cells = orig_scan
    _lg.handlers = _saved10b
    _lg.setLevel(_old_lvl)
    B._LAST_EMPTY_NOTE[0] = B._BLIND_STREAK[0] = 0
_l10b = [r for r in _seen10b if '[战斗] 无可点' in r]
check(streak10b == 1, '进场后从 0 重新记账: streak=%d' % streak10b)
check(len(_l10b) == 1 and '连续1帧' in _l10b[0] and 'white_mask' not in _l10b[0],
      '新一局发牌帧只给提示、不报警: %s' % (_l10b[0] if _l10b else '<无>',))


print('\nSUMMARY failures = %d  (耗时 %.1fs)' % (len(FAILS), time.time() - T0))
sys.exit(1 if FAILS else 0)
