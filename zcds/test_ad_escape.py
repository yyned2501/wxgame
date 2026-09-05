# -*- coding: utf-8 -*-
"""激励视频广告页出口回归锁 (2026-09-03 真机踩出来的坑)

现场: 12:18:18 battle -> 整页黑, 顶栏左边"广告|已获得奖励" 右边一颗"关闭"药丸。
      广告已经放完 -> pages/ad_popup.py 靠 OCR 找的两个关键词("放弃"/"秒后可获得奖励")
      都没了, 于是 ad_popup 认不出; 点色也全表不中; is_transition 却把这一页当成
      "黑屏转场" -> 每轮既不动作也不跑 OCR, 真机连续 31 帧 / 4 分钟干等。
修法: 黑屏连着 BLANK_AD_AFTER 帧还不走 = 不是转场, 用点色几何认出右上[关闭]药丸。
     2026-09-03 12:47 二次改版(用户定案"可以看广告的地方就自动看完"): 认出[关闭]之后**不立刻点**,
     而是 arm 一条"看广告窗口"交给 App._ad_tick 管 —— 广告放完(左上状态药丸缩窄)才准点[关闭]。
     提前点 = 奖励作废 + 弹"是否继续观看视频"挽留框。窗口本身的行为在 test_ad_watch.py 里钉。
"""
import logging, os, sys, time
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
from pages.base import ad_close_pos, ad_pill_right, is_transition
from auto_bot import App, BLANK_AD_AFTER

AD = 'shots/ad_popup_live122400.png'
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
    QUEUE[:] = [rel]
    CLICKS[:] = []
    app._nohit_streak = 0
    app._trans_streak = 0
    outs = []
    for _ in range(n):
        outs.append(app.step())
    page, acted, ocr_ran = outs[-1]
    return (page, any(o[1] for o in outs), any(o[2] for o in outs)), list(CLICKS)


print('[1] 判据本身: 广告页=黑屏转场形状, 但右上角有关闭按钮 (真转场没有)')
img = load(AD)
trans, why = is_transition(img)
check(trans and why == '黑屏', '这一页确实会被当成"黑屏转场" (实测 %s/%s) —— 坑的根源' % (trans, why))
pos = ad_close_pos(img)
check(pos is not None, 'ad_close_pos 认出[关闭]药丸: %s' % (pos,))
check(10 <= pos[1] <= 140 and pos[0] > 380, '落点在顶栏右半边 (x=%d y=%d)' % pos)


def near(p, q, d=8):
    return abs(p[0] - q[0]) <= d and abs(p[1] - q[1]) <= d


TARGET = (472, 90)
check(near(pos, TARGET), '落点与实拍标注一致 %s' % (TARGET,))
NORMAL = ['shots/lobby_clean.png', 'shots/battle_full.png', 'shots/chestinfo.png',
          'shots/flow4_s0_result.png', 'shots_live/tab_shop.png', 'shots_live/tab_guild.png']
bad = [r for r in NORMAL if ad_close_pos(load(r)) is not None]
check(not bad, '%d 张正常页一律找不到这个[关闭] (误命中: %s)' % (len(NORMAL), bad))

print('[2] 状态机: 第 1 帧黑屏仍当转场(不动手), 连续第 %d 帧才自救' % BLANK_AD_AFTER)
(page, acted, ocr_ran), clicks = step(AD, 1)
check(page is None and not acted and clicks == [],
      '单帧黑屏 = 正常转场, 本轮不动作 (%s/%s/%s)' % (page, acted, clicks))

print('[3] 连喂 %d 帧同一张广告页 -> 开"看广告窗口", 但**一帧都不点**(没放完就关 = 奖励作废)'
      % (BLANK_AD_AFTER + 2))
(page, acted, ocr_ran), clicks = step(AD, BLANK_AD_AFTER + 2)
check(page is None and not acted and clicks == [],
      '刚撞见广告页就点[关闭] %s -> 会被判"提前关闭", 奖励作废 (acted=%s)' % (clicks, acted))
check(app._ad_until > 0, '认出广告页却没开看广告窗口 (_ad_until=%s)' % app._ad_until)
check(app._ad_pill_first == ad_pill_right(load(AD)),
      '开窗时第 1 帧就记下本场药丸宽度 %s, 实际 %s' % (ad_pill_right(load(AD)), app._ad_pill_first))
check(ocr_ran is False and OCR_CNT[0] == 0, '自救全程不花一次 OCR (本段累计 %d)' % OCR_CNT[0])

print('[4] 放完(药丸缩窄)才动手: 伪造"已经看了 20s" -> 点它自己的[关闭]')
app._ad_t0 = time.time() - 20          # 只有"看了多久"是假的, 判据全用真帧
(page, acted, ocr_ran), clicks = step('shots/watch_124711.png', 1)
check(not acted and clicks == [],
      '倒计时态(药丸 211, 比本场最宽 209 还宽)不该点: %s' % (clicks,))
(page, acted, ocr_ran), clicks = step('shots/watch_124746.png', 1)
check(acted and len(clicks) == 1 and near(clicks[0], (488, 77), 8),
      '放奖态(211->164 缩了 47px)必须点[关闭]: %s' % (clicks,))
check(app._ad_closing, '点过[关闭]之后应进入"确认关掉了"阶段')
(page, acted, ocr_ran), clicks = step('shots/lobby_clean.png', 1)
check(app._ad_until == 0 and page is not None and page.name == 'lobby',
      '已经离开广告页 -> 关窗口并在同一帧交回正常路由 (%s/%s)' % (page, app._ad_until))

print()
print('全程 OCR 实际跑了 %d 次' % OCR_CNT[0])
if FAILED:
    print('FAILED %d 项' % len(FAILED))
    for m in FAILED:
        print('  - ' + m)
    sys.exit(1)
print('ALL DONE 广告页自救回归全绿')
