# -*- coding: utf-8 -*-
"""看广告回归 (2026-09-03 12:47 用户定案: "点击黄色的看广告领取, 可以看广告的地方就自动看完")

四段各自钉死的事:
  [1] 结算页黄色[领取]判据 ad_claim_pos —— 命中帧必须全是 result, 且和[宝箱立即开箱]
      /[升级领奖]那两颗**同一个黄**(0xFDCA33)互斥(靠外接框宽高分开, 见 pages/base.py)
  [2] 广告页左上状态药丸 ad_pill_right 逐帧读数 + "本场相对缩窄"阈值的分界
      (倒计时抖动 211->204 只差 7px 不算放完; 211->164 差 47px 才算)
  [3] 看广告窗口 _ad_tick 状态机(伪造时钟): 没放完一帧都不点; 放完只点一次[关闭];
      关闭后赖着不走重补一次; 已离开广告页 -> done; 压根没进广告 -> giveup; 超总闸 -> giveup
  [4] 端到端零 OCR: step() 从 result 点[领取] -> arm 窗口 -> 之后几轮只归窗口管,
      不定页、不跑 OCR、不瞎点
用法(项目根目录): python -X utf8 test_ad_watch.py      # 退出码 0 = 全通过
"""
import logging
import os
import sys
import time

D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
sys.path.insert(0, os.path.join(D, 'tools'))
logging.basicConfig(level=logging.CRITICAL)

from PIL import Image

import game_utils as g
import pick_print as pp

CLAIM = (412, 782)          # 黄色[领取]药丸中心(实测 412~413 / 779~782)
CLOSE = (488, 77)           # 广告页右上[关闭]药丸中心(实拍 watch_* 五帧恒定)
# 语料里带黄色[领取]横幅的结算页帧(scratch/scripts/claim_frames_0903.py 2026-09-03 dump)
CLAIMED = {
    'now', 'help_live', 'watch_124652', 'watch_124654', 'watch_124656', 'watch_124658',
    'watch_124700', 'watch_124705', 'result_live005639', 'result_live010726',
    'result_live010729', 'result_live030901', 'result_live030920', 'result_live031108',
    'result_live031408', 'result_live035436', 'result_live040817',
}
# 实拍连拍: 广告页左上状态药丸的右边界(文案越短越靠左)
PILL = [
    ('shots/watch_124711.png', 211, '广告 | 27 秒后可获得奖励'),
    ('shots/watch_124723.png', 211, '广告 | 27 秒后可获得奖励'),
    ('shots/watch_124735.png', 204, '广告 |  8 秒后可获得奖励'),
    ('shots/watch_124746.png', 164, '广告 | 已获得奖励'),
    ('shots/watch_124758.png', 164, '广告 | 已获得奖励'),
    ('shots/ad_popup_live122400.png', 209, '另一路广告 SDK: 已获得奖励(宽度不能当绝对阈值)'),
]
AD = 'shots/ad_popup_live122400.png'
FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print('  FAIL  ' + msg)


def near(p, q, d=3):
    return p is not None and abs(p[0] - q[0]) <= d and abs(p[1] - q[1]) <= d


def load(rel):
    return Image.open(os.path.join(D, rel)).convert('RGB')


def frames(label):
    """语料标签 -> {帧名主干: PIL 图}"""
    out = {}
    for nm in pp.LABELS[label]:
        path = pp.img_path(nm)
        if not path or not os.path.isfile(path):
            continue
        im = Image.open(path).convert('RGB')
        if im.size != (552, 1006):
            continue
        out[os.path.basename(path).rsplit('.', 1)[0]] = im
    return out


# ======================= 假窗口 / 假点击脚手架 =======================
QUEUE = []
CLICKS = []


def fake_capture(hwnd):
    item = QUEUE[0]
    if isinstance(item, Image.Image):
        return item, 1
    return load(item), 1


g.capture_window = fake_capture
g.find_game_window = lambda: 12345
try:
    g.u32.IsWindow = lambda h: True
except Exception:
    pass

import auto_bot
from auto_bot import App, BLANK_AD_AFTER
from pages.base import AD_PILL_SHRINK, ad_claim_pos, ad_close_pos, ad_pill_right


def new_app():
    app = App(dry_run=True, low_cpu=False)
    app.ensure_window()
    app.vision.refresh_hwnd(12345)
    app.click = lambda x, y: CLICKS.append((int(x), int(y)))
    return app


# ======================= [1] 黄色[领取]判据 =======================
print('[1] ad_claim_pos: 只认结算页那颗扁宽黄药丸, 与同色的开箱/领奖按钮互斥')
n_pos = 0
for nm, img in sorted(frames('result').items()):
    pos = ad_claim_pos(img)
    want = nm in CLAIMED
    check((pos is not None) == want,
          'result/%s claim=%s 与"横幅在不在"(真值 %s)不一致' % (nm, pos, want))
    if want:
        n_pos += 1
        check(near(pos, CLAIM), 'result/%s 落点 %s 不在 %s±3' % (nm, pos, CLAIM))
check(n_pos == len(CLAIMED), '结算页带横幅的帧数 %d != 码表 %d -> 语料变了就同步这里'
      % (n_pos, len(CLAIMED)))
# 反向: 除 result 之外的每一类语料帧都不许命中(chest_info / levelup 是同一个黄 0xFDCA33)
n_neg = 0
for lab in sorted(pp.LABELS):
    if lab == 'result':
        continue
    for nm, img in sorted(frames(lab).items()):
        pos = ad_claim_pos(img)
        check(pos is None, '%s/%s 误命中黄色[领取] %s' % (lab, nm, pos))
        n_neg += 1
print('    %d 帧结算页命中(全在 %s±3) / %d 帧异页(含同色的 chest_info+levelup)0 误命中'
      % (n_pos, CLAIM, n_neg))

# ======================= [2] 状态药丸 =======================
print('[2] ad_pill_right: 逐帧读数 + 放完判据用"本场相对缩窄"(绝对阈值会翻车)')
for rel, want, note in PILL:
    got = ad_pill_right(load(rel))
    check(got == want, '%s 药丸右边界 %s != 实测 %s (%s)' % (rel, got, want, note))
wide = ad_pill_right(load('shots/watch_124711.png'))
jitter = ad_pill_right(load('shots/watch_124735.png'))
done = ad_pill_right(load('shots/watch_124746.png'))
check(wide - jitter < AD_PILL_SHRINK,
      '倒计时抖动 %d->%d(缩 %d)被当成放完 -> 会提前关广告, 阈值 %d 太松'
      % (wide, jitter, wide - jitter, AD_PILL_SHRINK))
check(done is not None and wide - done >= AD_PILL_SHRINK,
      '真放完 %d->%d(缩 %d)判不出 -> 永远等不到关闭' % (wide, done, wide - done))
check(wide - ad_pill_right(load('shots/ad_popup_live122400.png')) < AD_PILL_SHRINK,
      '换一路广告 SDK(药丸天然窄)时相对判据仍不误判放完')

# ======================= [3] 窗口状态机(伪造时钟) =======================
print('[3] _ad_tick 状态机(伪造时钟): 放完才点[关闭], 中途一帧都不点')


class FakeTime:
    def __init__(self):
        self.t = 1000.0

    def time(self):
        return self.t

    def sleep(self, sec):
        self.t += sec

    def __getattr__(self, k):
        return getattr(time, k)


FT = FakeTime()
_real_time = time
auto_bot.time = FT
try:
    app = new_app()
    FT.t = 1000.0
    app.start_ad_watch('回归')
    check(app._ad_until > app._ad_t0, 'start_ad_watch 没开窗 (_ad_until=%s)' % app._ad_until)
    seq = [('shots/watch_124711.png', 0.0, 'wait'),      # 刚点上, 27s 倒计时
           ('shots/watch_124723.png', 5.0, 'wait'),      # 还是 27s
           ('shots/watch_124735.png', 5.0, 'wait'),      # 8s: 只缩 7px, 不算放完
           ('shots/watch_124746.png', 5.0, 'acted'),     # waited 15s + 缩 47px -> 点[关闭]
           ('shots/watch_124746.png', 3.0, 'acted'),     # 还赖在广告页 -> 重补一次
           ('shots/lobby_clean.png', 1.0, 'done')]       # 已离开广告页 -> 交回正常路由
    for i, (rel, dt, want) in enumerate(seq):
        FT.t += dt
        r = app._ad_tick(load(rel))
        check(r == want, '第%d轮(%s, t+=%.0f) -> %s, 应为 %s' % (i + 1, os.path.basename(rel), dt, r, want))
    check(app._ad_until == 0.0, 'done 之后窗口没关: _ad_until=%s' % app._ad_until)
    check(CLICKS == [CLOSE, CLOSE], '整个窗口只该点[关闭](放完 1 次 + 重补 1 次): %s' % (CLICKS,))
    check(app._ad_pill_max == wide, '本场最宽药丸 %s != 实测 %s' % (app._ad_pill_max, wide))

    # 等满 AD_WATCH_MAX 也要能收手: 有的广告 SDK 全程不缩窄(拿不到倒计时读数)
    CLICKS[:] = []
    FT.t = 5000.0
    app.start_ad_watch('回归-等满')
    same = 'shots/ad_popup_live122400.png'
    FT.t += 8
    check(app._ad_tick(load(same)) == 'wait', '才看 8s(<AD_WATCH_MIN)就点[关闭] -> 奖励作废')
    FT.t += 40
    check(app._ad_tick(load(same)) == 'acted', '等满 AD_WATCH_MAX 还不收手')
    check(CLICKS == [(472, 90)], '等满后点的应是它自己的[关闭]: %s' % (CLICKS,))

    # 总闸: 一条广告不许把主循环锁死超过 AD_WATCH_TOTAL
    CLICKS[:] = []
    FT.t = 9000.0
    app.start_ad_watch('回归-超时')
    FT.t += App.AD_WATCH_TOTAL + 5
    check(app._ad_tick(load(same)) == 'giveup', '超 AD_WATCH_TOTAL 必须撒手(防死等)')
    check(app._ad_until == 0.0 and not CLICKS, '撒手时不该留窗口也不该乱点: %s' % (CLICKS,))

    # 压根没进广告(点[领取]没跳转): 几秒内认出还是游戏自己的页 -> 撒手交回路由
    CLICKS[:] = []
    FT.t = 20000.0
    app.start_ad_watch('回归-没进广告')
    FT.t += App.AD_NOT_AD_AT + 1
    check(app._ad_tick(load('shots/lobby_clean.png')) == 'giveup',
          '没在看广告却把主循环锁住了 -> 认出游戏页就该撒手')
    check(app._ad_until == 0.0, 'giveup 之后窗口没关')
finally:
    auto_bot.time = _real_time

# ======================= [4] 端到端: result 点[领取] -> 窗口接管, 全程零 OCR =========
print('[4] step() 端到端: 结算页点黄色[领取] -> 窗口接管(不定页/不跑 OCR/不瞎点)')
OCR_CNT = [0]
app = new_app()
_orig_ocr = app.vision.ocr


def _ocr(*a, **kw):
    f, ran = _orig_ocr(*a, **kw)
    OCR_CNT[0] += int(bool(ran))
    return f, ran


app.vision.ocr = _ocr
QUEUE[:] = ['shots/result_live005639.png']
CLICKS[:] = []
page, acted, ocr_ran = app.step()
check(page is not None and page.name == 'result', '第 1 轮没定成 result: %s' % (page,))
check(acted and CLICKS == [CLAIM], '结算页没点到黄色[领取]: %s' % (CLICKS,))
check(app._ad_until > 0, '点完[领取]没 arm 看广告窗口')
check(ocr_ran is False and OCR_CNT[0] == 0, 'result 定页+点[领取]竟然花了 OCR')
n_round = 0
for rel in ('shots/watch_124711.png', 'shots/watch_124735.png', 'shots/other_live014216.png',
            'shots/watch_124746.png'):
    QUEUE[:] = [rel]
    CLICKS[:] = []
    page, acted, ocr_ran = app.step()
    n_round += 1
    check(page is None and not acted and not CLICKS,
          '看广告期间第 %d 轮竟然定页/动手: %s/%s/%s' % (n_round, page, acted, CLICKS))
check(OCR_CNT[0] == 0, '看广告窗口共花了 %d 次 OCR(应为 0)' % OCR_CNT[0])
check(app._ad_until > 0, '还没放完就把窗口关了(4 轮 < AD_WATCH_MIN)')
app._end_ad_watch()

print('')
if FAILS:
    print('不通过 %d 项:' % len(FAILS))
    for m in FAILS:
        print('  - ' + m)
    sys.exit(1)
print('全部通过 (黄色[领取]点色判据 / 药丸放完判据 / 看广告窗口状态机 / 全程零 OCR)')
print('覆盖: %d 帧结算页 + %d 帧异页 + %d 帧广告页 + %d 轮窗口状态机'
      % (n_pos, n_neg, len(PILL), n_round))
sys.exit(0)
