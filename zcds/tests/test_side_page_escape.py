# -*- coding: utf-8 -*-
"""侧页出口回归锁: 新手引导模态 / 兄弟页签 / 侧页返回箭头 —— 三条路全部零 OCR

为什么要有这三条路(全是 2026-09-03 真机踩出来的):
  引导模态  大白气泡把整页压暗 -> 连大厅指纹都不命中 -> 旧版只能 OCR 猜, 又慢又猜不动
  兄弟页签  引导走完落在商店页 / 手动停在排名页 -> 没人点最中间那个页签就永远回不到大厅
  返回箭头  竞技场晋级页这类侧页内容随等级变, 刻意不标指纹 -> 箭头本身就是出口
"""
import logging, os, sys
logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)s %(message)s')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image

import game_utils as g

D = os.path.dirname(os.path.abspath(__file__))
QUEUE = []
CLICKS = []


def fake_capture(hwnd):
    item = QUEUE[0]
    if isinstance(item, Image.Image):
        return item, 1
    return Image.open(os.path.join(D, item)).convert('RGB'), 1


g.capture_window = fake_capture
g.find_game_window = lambda: 12345
try:
    g.u32.IsWindow = lambda h: True
except Exception:
    pass

import colorprint as cp
from pages import ALL_PAGES
from pages.base import (NAV_LOBBY_TAB, NAV_MIN_HIT, back_arrow_pos, guide_modal,
                        guide_targets, nav_hits, nav_present, nav_tab_cx, route_prints)
from auto_bot import App

FAILED = []


def check(ok, msg):
    print('  %s %s' % ('ok  ' if ok else 'FAIL', msg))
    if not ok:
        FAILED.append(msg)


def load(rel):
    return Image.open(os.path.join(D, rel)).convert('RGB')


app = App(dry_run=True, low_cpu=False)
app.ensure_window()
app.vision.refresh_hwnd(12345)
OCR_CNT = [0]
_orig_ocr = app.vision.ocr


def _ocr(*a, **kw):
    f, ran = _orig_ocr(*a, **kw)
    OCR_CNT[0] += int(bool(ran))
    return f, ran


app.vision.ocr = _ocr
app.click = lambda x, y: CLICKS.append((int(x), int(y)))


def step(rel, n=1):
    """连喂 n 帧同一张图 -> 返回 (最后一次 page/acted/ocr_ran, 这几帧累计的真实点击)

    CLICKS 只在进函数时清一次: tab_other 自己带 2.5s 节流, 每帧清会把上一帧的
    战果擦掉, 看着像没点。"""
    QUEUE[:] = [rel]
    CLICKS[:] = []
    # 换个场景就把页面对象自带的节流/计数字段清掉(真机每个场景之间隔的是秒, 不是毫秒)
    for q in app.pages:
        for attr in ('_last', '_sig', '_tries', '_gave_up_at'):
            if hasattr(q, attr):
                setattr(q, attr, 0 if attr == '_gave_up_at' else None if attr == '_sig' else 0.0)
    app._nohit_streak = 0
    app._trans_streak = 0
    out = None
    for _ in range(n):
        app.clicked_cells = {}
        app.last_cell = 0
        app._act_gap = 0
        out = app.step()
    return out, list(CLICKS)


print('[1] 新手引导模态: 大白气泡 = 点色可认的身份, 且能算出该点哪里')
GUIDE = ['shots/lobby_dim_live09%04d.png' % i for i in
         (0, 107, 214, 321, 428, 535, 642, 749, 856, 903, 3000)] + \
        ['shots/other_live101005.png', 'shots/other_live101006.png']
bad = [r for r in GUIDE if not (guide_modal(load(r))[0] and guide_targets(load(r)))]
check(not bad, '%d 张引导帧全部判为引导模态且给出落点 (漏: %s)' % (len(GUIDE), bad))
NOTGUIDE = ['shots/lobby_live100100.png', 'shots/battle_full.png', 'shots/chestinfo.png',
            'shots/flow4_s0_result.png', 'shots_live/tab_shop.png', 'shots_live/tab_guild.png']
bad = [r for r in NOTGUIDE if guide_modal(load(r))[0]]
check(not bad, '%d 张正常页帧一律不判为引导 (误判: %s)' % (len(NOTGUIDE), bad))
p, sc, src = route_prints(ALL_PAGES, cp.to_arr(load('shots/lobby_dim_live090000.png')))
check(p is None, '引导帧连大厅指纹都不命中(整页被压暗): page=%s score=%.2f' % (p.name if p else None, sc))
for _ in range(3):
    (page, acted, ocr_ran), clicks = step('shots/lobby_dim_live090000.png', 3)
check(page.name == 'unknown' and not ocr_ran,
      '引导帧 -> 交 unknown 且零 OCR (实测 page=%s ocr=%s)' % (page.name, ocr_ran))
check(bool(clicks), 'unknown 当场照着落点表出手: %s' % (clicks,))

print('[2] 兄弟页签: 导航栏在 + 大厅指纹没中 -> 点中间[战斗]回大厅, 一次 OCR 不花')
for rel, cx in [('shots_live/tab_shop.png', 50), ('shots_live/tab_cards.png', 163),
                ('shots_live/tab_castle.png', 389), ('shots_live/tab_guild.png', 502)]:
    img = load(rel)
    check(nav_present(img) and nav_tab_cx(img) == cx,
          '%s 认出页签 x=%d (实测 %s / hits=%d)' % (rel, cx, nav_tab_cx(img), nav_hits(img)))
    (page, acted, ocr_ran), clicks = step(rel, 3)
    check(page is not None and page.name == 'tab_other' and not ocr_ran,
          '  -> 路由到 tab_other 且零 OCR (实测 page=%s ocr=%s)'
          % (page.name if page else None, ocr_ran))
    check(tuple(NAV_LOBBY_TAB) in clicks, '  -> 实际点了中间页签 %s (实测 %s)' % (NAV_LOBBY_TAB, clicks))
img = load('shots_live/tab_battle.png')
check(nav_present(img) and nav_tab_cx(img) == 276, '大厅帧: 亮着的就是中间页签 x=276')
(page, acted, ocr_ran), clicks = step('shots_live/tab_battle.png', 2)
check(page.name == 'lobby', '大厅帧仍由指纹定页, 不会被 tab_other 抢走: page=%s' % page.name)

print('[3] 侧页返回箭头: 竞技场/任务页 -> 零 OCR 交 unknown')
rel = 'shots/other_quest_0022.png'
check(back_arrow_pos(load(rel)) is not None and not nav_present(load(rel)),
      '%s 有返回箭头且没有导航栏: arrow=%s' % (rel, back_arrow_pos(load(rel))))
for i in range(5):
    r = 'shots/arena_live0846%02d.png' % i
    if not os.path.exists(os.path.join(D, r)):
        continue
    img = load(r)
    check(back_arrow_pos(img) is not None and not nav_present(img),
          '%s 有箭头无导航栏 arrow=%s' % (r, back_arrow_pos(img)))
(page, acted, ocr_ran), clicks = step(rel, 3)
check(page.name == 'unknown' and not ocr_ran,
      '任务页 -> unknown 且零 OCR (实测 page=%s ocr=%s 落点=%s)' % (page.name, ocr_ran, clicks))

print('[4] 卡牌页那颗青色图标会被误认成返回箭头 -> 所以页签判据必须排在箭头前面')
img = load('shots_live/tab_cards.png')
ar = back_arrow_pos(img)
check(ar is not None, '卡牌页确实会被 back_arrow_pos 误命中 %s' % (ar,))
(page, acted, ocr_ran), clicks = step('shots_live/tab_cards.png', 3)
check(page.name == 'tab_other',
      '但路由先认导航栏 -> page=%s (不是 unknown), 落点 %s' % (page.name, clicks))

print('[5] 导航栏判据在整份语料上的分界')
pos, neg = [], []
for d in ('shots', 'shots_live'):
    for fn in sorted(os.listdir(os.path.join(D, d))):
        if not fn.endswith('.png'):
            continue
        h = nav_hits(load(os.path.join(d, fn)))
        (pos if h >= NAV_MIN_HIT else neg).append((os.path.join(d, fn), h))
check(min(h for _, h in pos) >= 14 and max(h for _, h in neg) <= 9,
      '%d 张里 %d 张带栏(最低 %d) / %d 张不带(最高 %d) —— 门限 %d 上下各留 >=3 余量'
      % (len(pos) + len(neg), len(pos), min(h for _, h in pos), len(neg),
         max(h for _, h in neg), NAV_MIN_HIT))
bad = [n for n, h in pos if nav_tab_cx(load(n)) not in [50, 163, 276, 389, 502]]
check(not bad, '每个带栏帧都能说出亮着的是哪个页签 (漏: %s)' % bad[:5])

print('[6] unknown: 候选点完画面还不变 -> 停手, 绝不无限狂点')
from pages.unknown import MAX_TRY, UnknownPage


class _F(object):
    img = None


class _Ctx(object):
    unknown_idle = 0

    def click(self, x, y):
        CLICKS.append((int(x), int(y)))


unk = UnknownPage()
ctx = _Ctx()
ctx.f = _F()
ctx.f.img = load('shots/other_quest_0022.png')      # 画面签名恒定不变
CLICKS[:] = []
tries = 0
while unk.act(ctx) and tries < 20:
    tries += 1
check(0 < tries <= MAX_TRY, '同一帧最多点 %d 次就停手 (实测 %d 次 = 候选表长度), 之后 act 返回 False'
      % (MAX_TRY, tries))
check(all(c == CLICKS[i] for i, c in enumerate(CLICKS[:tries])),
      '每次点的都是候选表里下一个落点: %s' % (CLICKS[:tries],))

print()
print('全程 OCR 实际跑了 %d 次' % OCR_CNT[0])
if FAILED:
    print('FAILED %d 项' % len(FAILED))
    for m in FAILED:
        print('  - ' + m)
    sys.exit(1)
print('ALL DONE 侧页出口回归全绿')
