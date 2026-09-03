# -*- coding: utf-8 -*-
"""弹窗出口回归锁: 点色认出[红底白叉关闭徽章] -> 零 OCR 关窗

语料对账(2026-09-03 15:40 复跑, 全 820 张 552x1006 帧, 脚本 scratch/scripts/badge_cross_0903.py):
    点色全表不中的 152 张 = 引导 68 / 返回箭头 44 / 转场 19 / 兄弟页签 12 /
                            关闭徽章 6 / 什么都不认得 3
  徽章那 6 帧(= 4 个不同弹窗, fu_02/hv_summon 在 shots_live/ 里还有同名副本)是指南弹窗
  与装备详情弹窗, 旧版每帧都要
  白烧一次 675ms 全图 OCR, 认完还是 unknown -> 只能盲点遮罩。现在徽章本身就是出口。
  而且这 6 帧**没有一帧同时带引导/页签/箭头** -> 新判据插在引导之后、页签之前,
  对既有三条零 OCR 出口零影响(本测试 [1] 段把它钉住)。
"""
import logging, os, sys
logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)s %(message)s')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools'))
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

from pages import ALL_PAGES
from pages.base import (NAV_LOBBY_TAB, back_arrow_pos, find_close_badge, guide_targets,
                        is_transition, nav_present, nav_tab_cx, route_prints)
from pages.claim_popup import ClaimPopupPage
from pages.diamond_popup import DiamondPopupPage
from auto_bot import App, OCR_ESCALATE_AFTER

FAILED = []
OCR_CNT = [0]


def check(ok, msg):
    print('  %s %s' % ('ok  ' if ok else 'FAIL', msg))
    if not ok:
        FAILED.append(msg)


def load(rel):
    return Image.open(os.path.join(D, rel)).convert('RGB')


BADGE = ['shots/guide_live1.png', 'shots/guide_live3.png',
         'shots/other_live_fu02.png', 'shots/other_live_hv_summon.png']

print('[1] 徽章帧: 关闭徽章认得出, 且既有三条出口都不响(证明插入位置零影响)')
for rel in BADGE:
    img = load(rel)
    page, score, src = route_prints(ALL_PAGES, img)
    tr, why = is_transition(img)
    check(page is None and not tr,
          '%s 点色全表不中(page=%s)且不是转场帧(trans=%s/%s)'
          % (rel, page.name if page else None, tr, why))
    bd = find_close_badge(img)
    check(bd is not None, '  关闭徽章认得出 %s' % (bd,))
    gts = guide_targets(img)
    tab = nav_present(img) and nav_tab_cx(img) != NAV_LOBBY_TAB[0]
    ar = back_arrow_pos(img)
    check(not gts and not tab and ar is None,
          '  引导/页签/箭头三条路都不抢(引导=%s 页签=%s 箭头=%s)' % (bool(gts), tab, ar))

print('[2] 真跑 App.step(): 徽章帧 -> unknown + 零 OCR + 点到徽章上')
app = App(dry_run=True, low_cpu=False)
app.ensure_window()
app.vision.refresh_hwnd(12345)
_orig_ocr = app.vision.ocr


def _ocr(*a, **kw):
    f, ran = _orig_ocr(*a, **kw)
    OCR_CNT[0] += int(bool(ran))
    return f, ran


app.vision.ocr = _ocr
app.click = lambda x, y: CLICKS.append((int(x), int(y)))

for rel in BADGE:
    img = load(rel)
    bd = find_close_badge(img)
    QUEUE[:] = [img]
    for q in app.pages:
        for attr in ('_last', '_sig', '_tries', '_gave_up_at'):
            if hasattr(q, attr):
                setattr(q, attr, 0 if attr == '_gave_up_at' else None if attr == '_sig' else 0.0)
    app._nohit_streak = 0
    app._trans_streak = 0
    CLICKS[:] = []
    out = None
    for _ in range(3):          # 第 1 帧只升级水位, 第 2 帧才该出手
        app.clicked_cells = {}
        app.last_cell = 0
        app._act_gap = 0
        out = app.step()
    page, acted, ocr_ran = out
    check(page is not None and page.name == 'unknown' and not ocr_ran,
          '%s -> page=unknown 且零 OCR (实测 page=%s ocr=%s)'
          % (rel, page.name if page else None, ocr_ran))
    hit = [c for c in CLICKS if abs(c[0] - bd[0]) <= 8 and abs(c[1] - bd[1]) <= 8]
    check(bool(hit), '  实际点到徽章附近: 徽章=%s 落点=%s' % (bd, CLICKS))

print('[3] claim_popup.act: 关闭徽章优先, 一个字都不读')
ctx = app
for rel in BADGE:
    app.f = type('F', (), {'img': load(rel), 'boxes': [], 'joined': ''})()
    app.last_action = {}
    CLICKS[:] = []
    ok = ClaimPopupPage().act(ctx)
    bd = find_close_badge(load(rel))
    check(ok and CLICKS and abs(CLICKS[0][0] - bd[0]) <= 2 and abs(CLICKS[0][1] - bd[1]) <= 2,
          '%s -> 点徽章 %s (实测 acted=%s 落点=%s)' % (rel, bd, ok, CLICKS))
check(OCR_CNT[0] == 0, '到目前为止 OCR 实际跑了 %d 次' % OCR_CNT[0])

print('[4] diamond_popup.act: 认不出来就什么都不点(旧版会盲点 (270,300) 赌命)')


class _Empty(object):
    def find(self, kw):
        return []


class _Ctx(object):
    def __init__(self, img):
        self.f = type('F', (), {'img': img, 'boxes': [], 'joined': ''})()

    def need_text(self):
        return _Empty()

    def acted(self, key, gap=None):
        return False

    def click(self, x, y):
        CLICKS.append((int(x), int(y)))


CLICKS[:] = []
ctx = _Ctx(load('shots/lobby_clean.png'))        # 正常大厅帧: 没有关闭徽章
dp = DiamondPopupPage()
src = os.path.join(D, 'pages', 'diamond_popup.py')
body = open(src, encoding='utf-8').read()
check('ctx.click(270, 300)' not in body, '源码里已经没有盲点遮罩那行')
check(dp.act(ctx) is False and not CLICKS,
      '徽章没中 + 文字也没中 -> 返回 False 且零点击 (实测 %s)' % (CLICKS,))
bd_ctx = _Ctx(load('shots/other_live_hv_summon.png'))
CLICKS[:] = []
check(dp.act(bd_ctx) is True and len(CLICKS) == 1,
      '有徽章时仍然点徽章: %s' % (CLICKS,))

print('[5] 全语料: 还要花 OCR 的帧只剩 3 张(上界锁死, 防新页面把 OCR 路由撑回去)')
import glob
need = []
n = 0
for p in sorted(glob.glob(os.path.join(D, 'shots', '**', '*.png'), recursive=True)) + \
         sorted(glob.glob(os.path.join(D, 'shots_live', '*.png'))):
    try:
        im = Image.open(p)
        if im.size != (552, 1006):
            continue
        im = im.convert('RGB')
    except Exception:
        continue
    n += 1
    page, _score, _src = route_prints(ALL_PAGES, im)
    if page is not None:
        continue
    if is_transition(im)[0]:
        continue
    if guide_targets(im):
        continue
    if find_close_badge(im):
        continue
    if nav_present(im) and nav_tab_cx(im) != NAV_LOBBY_TAB[0]:
        continue
    if back_arrow_pos(im):
        continue
    need.append(os.path.relpath(p, D).replace(chr(92), '/'))
check(n >= 820 and len(need) <= 3,
      '%d 张帧里点色定不出页、四条零 OCR 出口也全不认的只剩 %d 张: %s'
      % (n, len(need), need))

print('[6] 2026-09-04 R28 血案帧: 开屏[秘境大冒险]活动弹窗(X n=973 被旧上限 950 拒)')
EVENT = ['shots/other_live_popup_event_004639.png', 'shots/other_live_popup_event_004908.png']
for rel in EVENT:
    img = load(rel)
    check(route_prints(ALL_PAGES, img)[0] is None,
          '%s 点色定不出页(这类弹窗内容随活动变, 刻意不标指纹)' % rel)
    bd = find_close_badge(img)
    check(bd == (477, 311), '  关闭徽章认得出且位置对: %s (修之前这里 None -> 掉全图 OCR)' % (bd,))
    QUEUE[:] = [img]
    CLICKS[:] = []
    app._nohit_streak = 0
    app._trans_streak = 0
    app._zerohit_run = 0
    app._ocr_zero = 0
    app.cur_page = 'unknown'
    for attr, val in (('_sig', None), ('_tries', 0)):
        if hasattr(app.pages[-1], attr):
            setattr(app.pages[-1], attr, val)
    out = None
    for _ in range(3):
        out = app.step()
    page, acted, ocr_ran = out
    check(page is not None and page.name == 'unknown' and not ocr_ran,
          '  连跑 3 帧仍是 unknown 且全程零 OCR (实测 page=%s ocr=%s)'
          % (page.name if page else None, ocr_ran))
    hit = [c for c in CLICKS if abs(c[0] - bd[0]) <= 8 and abs(c[1] - bd[1]) <= 8]
    check(bool(hit), '  落点打在徽章上: 徽章=%s 实测=%s' % (bd, CLICKS))
    check(app._ocr_zero < OCR_ESCALATE_AFTER,
          '  徽章出口本身就在动手, 不该把 OCR 升级计数器推到死路口 (实测 %d)' % app._ocr_zero)

print('[7] battle 页左上那坨红色装饰(60x60 / 72x60 / 60x72)仍然不是关闭徽章')
BATTLE_FP = ['shots/battle_live040659.png', 'shots_live/dbg_033_battle_040641.png',
             'shots_live/dbg_063_battle_040814.png', 'shots_live/dbg_053_battle_040743.png']
for rel in BATTLE_FP:
    if not os.path.exists(os.path.join(D, rel)):
        continue                       # shots_live/ 是 gitignore 的真机取证目录, 新克隆没有
    check(find_close_badge(load(rel)) is None, '  %s -> None' % rel)

print('[8] B 路卡页警报: 带动画的新页面每帧签名都在变, A 路数不到 -> 零命中计数必须补上')
import logging as _lg


class _Catch(_lg.Handler):
    def __init__(self):
        _lg.Handler.__init__(self)
        self.msgs = []

    def emit(self, record):
        self.msgs.append(record.getMessage())


_h = _Catch()
_lg.getLogger().addHandler(_h)
_saved = (app.cur_page, app._ad_until, app.unknown_idle)
app._stuck = 1                 # A 路故意停在 1: 证明下面的警报只可能来自 B 路
app._stuck_page = None
app.f = type('F', (), {'img': load(EVENT[0]), 'boxes': [], 'joined': ''})()


def _stuck_msgs(z, acted=False, name='versus', ad=0):
    _h.msgs[:] = []
    app.cur_page = name
    app._ad_until = ad
    app._zerohit_run = z
    app._flag_stuck(None, acted)
    return [m for m in _h.msgs if '[卡页]' in m]


check(len(_stuck_msgs(12)) == 1, '点色连续 12 帧零命中 + 页名是被误判的 versus(在 STUCK_EXEMPT 里) -> 必须报')
check(_stuck_msgs(11) == [], '11 帧(还没到阈值) -> 不报')
check(_stuck_msgs(12, acted=True) == [], '这帧真动了手 -> 不报')
check(_stuck_msgs(12, ad=1) == [], '看广告窗口整段豁免 -> 不报')
check(_stuck_msgs(0) == [], '零命中计数为 0 -> 不报')
app.cur_page, app._ad_until, app.unknown_idle = _saved
_lg.getLogger().removeHandler(_h)

print()
print('全程 OCR 实际跑了 %d 次' % OCR_CNT[0])
if FAILED:
    print('FAILED %d 项' % len(FAILED))
    for m in FAILED:
        print('  - ' + m)
    sys.exit(1)
print('ALL DONE 弹窗出口回归全绿')
