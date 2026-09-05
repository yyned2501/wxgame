# -*- coding: utf-8 -*-
"""看广告回归 (2026-09-03 12:47 用户定案: "点击黄色的看广告领取, 可以看广告的地方就自动看完")

四段各自钉死的事:
  [1] 结算页黄色[领取]判据 ad_claim_pos —— 命中帧必须全是 result, 且和[宝箱立即开箱]
      /[升级领奖]那两颗**同一个黄**(0xFDCA33)互斥(靠外接框宽高分开, 见 pages/base.py)
  [2] 广告页左上状态药丸 ad_pill_right 逐帧读数 + "本场相对缩窄"阈值的分界
      (倒计时抖动 211->204 只差 7px 不算放完; 211->164 差 47px 才算)
  [2c] 黑屏广告判据 ad_black_frac —— 真广告帧 5~6% / 游戏自己的页 96%+ / 过渡帧 37.6%,
       阈值 0.25 必须落在两头的空档里(实测值钉在码表里, 数字漂了就炸)
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

# 黄色[领取]药丸中心。2026-09-04 重建真值: 结算页的礼包面板有**两档纵向版式**(整块下移约 40px),
# 药丸中心因此是 (412,782) 和 (434,823) 两个, 和 pages/result.py 指纹的双形态同源;
# 失败礼包/胜利礼包两个标题在两档里都出现过 -> 落点跟胜负无关, 只跟面板位置有关。
# 人眼核对: scratch/tmp/an/result_claims.png(35 帧横幅区拼图) + claim_cross.png(落点画十字),
# 带内黄像素只有 0 和 2660~4768 两种状态, 检测器 ad_claim_pos 一帧没错。
CLAIM_CENTERS = ((412, 782), (434, 823))   # 实测 412~413/779~782 与 434/823
CLOSE = (488, 77)           # 广告页右上[关闭]药丸中心(实拍 watch_* 五帧恒定)
# 语料里带黄色[领取]横幅的结算页帧(scratch/scripts/claim_frames_0903.py 2026-09-03 dump)
CLAIMED = {
    'now', 'help_live', 'watch_124652', 'watch_124654', 'watch_124656', 'watch_124658',
    'watch_124700', 'watch_124705', 'result_live005639', 'result_live010726',
    'result_live010729', 'result_live030901', 'result_live030920', 'result_live031108',
    'result_live031408', 'result_live035436', 'result_live040817',
    # 2026-09-04 真机第 29~31 轮 12 帧(全在 CLAIM_CENTERS[1] 那一档版式上, 人眼核对见上)
    'result_live014557', 'result_live014913', 'result_live022442', 'result_live022626', 'result_live023249', 'result_live023639', 'result_live023919', 'result_live024104', 'result_live024421', 'result_live024720', 'result_live024904', 'result_live025130',
}
# 实拍连拍: 广告页左上状态药丸的右边界(文案越短越靠左)
PILL = [
    # 帧名                     右边界 带内白像素 药丸左边界  说明
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
from pages.base import (AD_BLACK_MAX_FRAC, AD_DIVERGE_FRAC, AD_PILL_LEFT_TOL, AD_PILL_LOW_HOLD,
                        AD_PILL_SHRINK, AD_PILL_SHRINK_PCT, ad_black_frac, ad_claim_pos,
                        ad_close_pos, ad_pill_right, ad_pill_state, is_ad_black, screen_div_frac)


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
        check(any(near(pos, c) for c in CLAIM_CENTERS),
              'result/%s 落点 %s 不在 %s 任一个 ±3 内' % (nm, pos, CLAIM_CENTERS))
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
      % (n_pos, CLAIM_CENTERS, n_neg))

# ======================= [2] 状态药丸 =======================
print('[2] ad_pill_right: 逐帧读数 + 放完判据用"本场相对缩窄"(绝对阈值会翻车)')
for rel, want, note in PILL:
    got = ad_pill_right(load(rel))
    check(got == want, '%s 药丸右边界 %s != 实测 %s (%s)' % (rel, got, want, note))
start_width = ad_pill_right(load('shots/watch_124711.png'))  # 27s 倒计时的自然起点
min_width = min(ad_pill_right(load(f)) for f in
             ('shots/watch_124711.png', 'shots/watch_124723.png', 'shots/watch_124735.png', 'shots/watch_124746.png'))  # 211/211/204/164 -> 164
jitter = ad_pill_right(load('shots/watch_124735.png'))
done = ad_pill_right(load('shots/watch_124746.png'))
check(start_width - jitter < AD_PILL_SHRINK,
      '倒计时抖动 %d->%d(缩 %d)被当成放完 -> 会提前关广告, 阈值 %d 太松'
      % (start_width, jitter, start_width - jitter, AD_PILL_SHRINK))
check(done is not None and start_width - done >= AD_PILL_SHRINK,
      '真放完 %d->%d(缩 %d)判不出 -> 永远等不到关闭' % (start_width, done, start_width - done))
check(start_width - ad_pill_right(load('shots/ad_popup_live122400.png')) < AD_PILL_SHRINK,
      '换一路广告 SDK(药丸天然窄)时相对判据仍不误判放完')

# ======================= [2b] 药丸第二把尺子: 带内白像素 =======================
print('[2b] ad_pill_state: 白像素数(=字数)是同一件事的第二种量法, 右边界不缩时它还能响')
WHITE = {'watch_124711': (211, 827, 32), 'watch_124723': (211, 830, 32),   # 倒计时 27s
         'watch_124735': (204, 794, 32),                                    # 倒计时 8s(掉一位数字)
         'watch_124746': (164, 606, 32), 'watch_124758': (164, 606, 32),    # 已获得奖励
         'ad_popup_live122400': (209, 914, 39)}                             # 另一路 SDK 的放奖帧
for rel, (wr_, wc, wl) in WHITE.items():
    got = ad_pill_state(load('shots/%s.png' % rel))
    check(got == (wr_, wc, wl), '%s 药丸读数 %s != 实测 %s' % (rel, got, (wr_, wc, wl)))
jitter = (830 - 794) / 830.0
drop = (830 - 606) / 830.0
check(jitter < AD_PILL_SHRINK_PCT < drop,
      '分界成立: 倒计时自身抖动只少 %.1f%% < 门限 %.0f%% < 换成放奖文案少 %.1f%%'
      % (jitter * 100, AD_PILL_SHRINK_PCT * 100, drop * 100))
check(914 > 830 and 914 > 830 * (1 - AD_PILL_SHRINK_PCT),
      '另一路 SDK 的放奖帧白像素 914 比本场倒计时峰值 830 还多 -> 只能跟本场峰值比, 不能定绝对阈值')

# ============ [2c] 黑屏广告判据: 真广告帧(黑画布+顶栏) / 游戏页 / 过渡帧 三头都要对上 ============
print('[2c] ad_black_frac: PrintWindow 抓不到视频层 -> 真广告帧 = 纯黑画布 + 顶栏(实测非黑 5~6%)')
# 2026-09-04 凌晨用 shots/watch_*(= 用户在场那一次的真机连拍)标定, 数值钉死在这里:
# 谁改了阈值/谁动了图, 这一段第一时间炸, 而不是等真机把一次奖励点没。
BLACK_AD = {'shots/watch_124711.png': 0.063, 'shots/watch_124723.png': 0.051,
            'shots/ad_popup_live122400.png': 0.053}
NOT_AD = {'shots/watch_124707.png': 0.376,       # 结算页正被黑屏盖上 = 过渡帧, 还不算广告
          'shots/watch_124652.png': 0.955,       # 结算页正常内容
          'shots/lobby_clean.png': 0.967,
          'shots/result_live005639.png': 0.961}
for rel, want in sorted(BLACK_AD.items()):
    f = ad_black_frac(load(rel))
    check(abs(f - want) < 0.02, '%s 非黑像素 %.1f%% 和码表 %.1f%% 差太多' % (rel, f * 100, want * 100))
    check(is_ad_black(load(rel)), '%s 是真广告帧却判成"不是黑屏广告"' % rel)
n_games = 0
for rel, want in sorted(NOT_AD.items()):
    f = ad_black_frac(load(rel))
    check(abs(f - want) < 0.05, '%s 非黑像素 %.1f%% 和码表 %.1f%% 差太多' % (rel, f * 100, want * 100))
    check(not is_ad_black(load(rel)), '%s 是游戏自己的页却判成黑屏广告' % rel)
    n_games += 1
check(max(BLACK_AD.values()) < AD_BLACK_MAX_FRAC < min(NOT_AD.values()),
      '阈值 AD_BLACK_MAX_FRAC=%s 没落在广告帧(<= %s)和游戏页(>= %s)的空档里'
      % (AD_BLACK_MAX_FRAC, max(BLACK_AD.values()), min(NOT_AD.values())))
print('    %d 帧真广告(5.1~6.3%%) + %d 帧非广告(37.6~96.7%%) 全对, 阈值 %s 在空档里'
      % (len(BLACK_AD), n_games, AD_BLACK_MAX_FRAC))


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
    check(app._ad_pill_min == min_width, '本场最窄药丸 %s != 实测 %s' % (app._ad_pill_min, min_width))

    # 🔴 2026-09-05 用户定案「广告得看满时间, 不能中途退出」: 旧锁"等满 40s 也当放完 -> 点[关闭]"
    #   翻转为 **时间不是放完的证据**: 没有药丸缩窄, 等过旧 40s 上限也只许继续等、一个键都不点,
    #   直到 AD_WATCH_TOTAL 撒手(撒手 = 不点击, 见下一段总闸测试)。
    CLICKS[:] = []
    FT.t = 5000.0
    app.start_ad_watch('回归-时间不算证据')
    same = 'shots/ad_popup_live122400.png'
    FT.t += 8
    check(app._ad_tick(load(same)) == 'wait', '才看 8s(<AD_WATCH_MIN)就点[关闭] -> 奖励作废')
    FT.t += 40
    check(app._ad_tick(load(same)) == 'wait', '等过旧 40s 上限、无缩窄证据 -> 不许中途退出')
    FT.t += 40
    check(app._ad_tick(load(same)) == 'wait', '48s 再一帧仍无证据 -> 继续等, 不点')
    check(CLICKS == [], '全程没放完证据就该一个键都没点: %s' % (CLICKS,))

    # 总闸: 一条广告不许把主循环锁死超过 AD_WATCH_TOTAL
    CLICKS[:] = []
    FT.t = 9000.0
    app.start_ad_watch('回归-超时')
    FT.t += App.AD_WATCH_TOTAL + 5
    check(app._ad_tick(load(same)) == 'giveup', '超 AD_WATCH_TOTAL 必须撒手(防死等)')
    check(app._ad_until == 0.0 and not CLICKS, '撒手时不该留窗口也不该乱点: %s' % (CLICKS,))

    # [3b] 尺子二: 右边界全程不缩(某家 SDK 两句文案同宽), 只有白像素变少 -> 也要能收手
    CLICKS[:] = []
    FT.t = 30000.0
    app = new_app()
    app.start_ad_watch('回归-尺子二')
    _real_pill = auto_bot.ad_pill_state
    SCRIPT = iter([(211, 827, 32), (211, 830, 32), (209, 600, 32), (209, 601, 32)])
    auto_bot.ad_pill_state = lambda img: next(SCRIPT)
    try:
        for dt, want in ((0.0, 'wait'), (5.0, 'wait'), (5.0, 'wait'), (4.0, 'acted')):
            FT.t += dt
            r = app._ad_tick(load('shots/watch_124711.png'))
            check(r == want, '尺子二 t+=%.0f -> %s, 应为 %s' % (dt, r, want))
        check(app._ad_pill_min == 209,
              '右边界最窄缩到 %s(差 2px < AD_PILL_SHRINK=%d) -> 第一把尺子确实没响'
              % (app._ad_pill_min, AD_PILL_SHRINK))
        check(app._ad_white_max == 830 and app._ad_pill_left == 32,
              '基准取的是"字最多"那帧: 白峰值=%s 左边界=%s' % (app._ad_white_max, app._ad_pill_left))
        check(CLICKS == [CLOSE], '尺子二只该点一次[关闭]: %s' % (CLICKS,))
        # 提前放奖不许抢跑: 白像素刚变少但还没持续够 AD_PILL_LOW_HOLD 秒
        CLICKS[:] = []
        FT.t = 31000.0
        app2 = new_app()
        app2.start_ad_watch('回归-尺子二-没持续够')
        quick = iter([(211, 830, 32), (211, 830, 32), (211, 600, 32), (211, 600, 32)])
        auto_bot.ad_pill_state = lambda img: next(quick)
        for dt in (0.0, 13.0, 1.0, 1.0):
            FT.t += dt
            check(app2._ad_tick(load('shots/watch_124711.png')) == 'wait',
                  '白像素只低了 %.0fs(<AD_PILL_LOW_HOLD=%.0fs)就点[关闭] -> 可能是假信号'
                  % (dt, AD_PILL_LOW_HOLD))
        check(not CLICKS, '持续不够就不该动手: %s' % (CLICKS,))
    finally:
        auto_bot.ad_pill_state = _real_pill

    # [3c] 门闩: 广告画面糊上顶栏(左边界从 32 跳到 222, 白像素暴跌到 157)不许被当成放奖
    #      故意把"低值"持续 5s+5s(> AD_PILL_LOW_HOLD) —— 少了这道门闩, 尺子二必然误判放奖去点[关闭]
    CLICKS[:] = []
    FT.t = 32000.0
    app3 = new_app()
    app3.start_ad_watch('回归-顶栏被盖')
    _real_pill = auto_bot.ad_pill_state
    covered = iter([(211, 830, 32), (211, 830, 32), (257, 157, 222), (257, 157, 222)])
    auto_bot.ad_pill_state = lambda img: next(covered)
    try:
        for dt in (0.0, 13.0, 5.0, 5.0):
            FT.t += dt
            r = app3._ad_tick(load('shots/watch_124711.png'))
            check(r == 'wait', '顶栏被广告盖住的帧竟然动了手 (t+=%.0f -> %s)' % (dt, r))
        check(not CLICKS and app3._ad_white_max == 830 and app3._ad_pill_left == 32
              and app3._ad_pill_min == 211,
              '盖住顶栏的帧两把尺子都不作数, 基准也没被污染: 白峰值=%s 左=%s 右峰值=%s 落点=%s'
              % (app3._ad_white_max, app3._ad_pill_left, app3._ad_pill_min, CLICKS))
        check(app3._ad_pill == (257, 157, 222),
              '门闩生效的前提是"确实量了这一帧再判它不可信", 读数是 %s' % (app3._ad_pill,))
    finally:
        auto_bot.ad_pill_state = _real_pill

    # 压根没进广告(点[领取]没跳转): 几秒内认出还是游戏自己的页 -> 撒手交回路由
    CLICKS[:] = []
    FT.t = 20000.0
    # 站在 result 上点的[领取], 6s 后硬命中的却是 lobby -> 那一页已经盖住结算页,
    # 广告不可能还在加载 -> 这一档必须立刻撒手(真机 18 次里 13 次是这种)
    app.cur_page = 'result'
    app.start_ad_watch('回归-没进广告')
    FT.t += App.AD_NOT_AD_AT + 1
    check(app._ad_tick(load('shots/lobby_clean.png')) == 'giveup',
          '没在看广告却把主循环锁住了 -> 认出游戏页就该撒手')
    check(app._ad_until == 0.0, 'giveup 之后窗口没关')

    # [3f] 另一档: 还停在点[领取]时那一页 -> 激励视频冷启动 5~15s, 这期间画面就是这页,
    #      4s 就撒手会把真广告判成没进广告、白丢一次奖励(真机 03:36 那次正是这种)
    app.cur_page = 'result'
    app.start_ad_watch('回归-还在加载')
    FT.t += App.AD_NOT_AD_AT + 1
    check(app._ad_tick(load('shots/result_live005639.png')) == 'wait',
          '还停在点[领取]那一页(视频可能在加载)就撒手了 -> 会白丢奖励')
    # 等满 AD_NOT_AD_SAME_AT: 黄色[领取]还在 -> 先"免费再点一次"(AD_CLAIM_RETRY), 重新计时
    CLICKS[:] = []
    FT.t += App.AD_NOT_AD_SAME_AT
    _want = ad_claim_pos(load('shots/result_live005639.png'))
    check(app._ad_tick(load('shots/result_live005639.png')) == 'acted',
          '停在同一页超过 AD_NOT_AD_SAME_AT 且黄色[领取]还在 -> 该免费再点一次, 不该干等')
    check(_want is not None and CLICKS == [_want],
          '重试点的落点应是它自己的黄色[领取] %s, 实为 %s' % (_want, CLICKS))
    check(app._ad_claim_retry == 1 and app._ad_until > app._ad_t0,
          '重试后该重新计时并记住预算: retry=%s until=%s t0=%s'
          % (app._ad_claim_retry, app._ad_until, app._ad_t0))
    # 预算用完还停在原页 -> 必须撒手(死等会把主循环锁满 AD_WATCH_TOTAL)
    FT.t += App.AD_NOT_AD_SAME_AT
    check(app._ad_tick(load('shots/result_live005639.png')) == 'giveup',
          '重试预算用完后停在同一页还不撒手 -> 死等, 主循环被锁死')
    check(app._ad_until == 0.0, 'giveup 之后窗口没关')

    # [3g] 反向用例: 同一页但黄色[领取]已经不见了 -> 没有可重试的目标, 第一次就该撒手
    CLICKS[:] = []
    FT.t = 21000.0
    app.cur_page = 'result'
    app.start_ad_watch('回归-没有领取')
    FT.t += App.AD_NOT_AD_AT + 1 + App.AD_NOT_AD_SAME_AT
    _real_claim = auto_bot.ad_claim_pos
    auto_bot.ad_claim_pos = lambda img: None
    try:
        check(app._ad_tick(load('shots/result_live005639.png')) == 'giveup',
              '看不到黄色[领取] 就没有免费重试的目标, 必须照常撒手, 不能死等')
    finally:
        auto_bot.ad_claim_pos = _real_claim
    check(app._ad_until == 0.0 and not CLICKS,
          '撒手时不该留窗口也不该乱点: %s' % (CLICKS,))

    # [3h] 黑屏档: 顶栏没认出来的黑屏帧同样是"广告正在放", 不许按"没进广告"撒手
    #      (撒手 = 主循环立刻去点别的地方 = 自己把广告打断 = 奖励作废);
    #      但豁免只有 AD_BLACK_GRACE 秒 —— 游戏自己的黑屏转场长得一样, 画面回到正常
    #      游戏页、顶栏还是认不出, 就该照常撒手, 不能把主循环锁死 100s。
    # [3i] 通道分歧度闸门: 屏幕上盖着一层 PrintWindow 拍不到的东西 = 广告正在放,
    #      这时撒手或"免费再点一次[领取]"都等于自己把广告打断(真机 R34 成功帧就是这种);
    #      反过来两条通道一致(实测基线 4.1~5.2%)才算"确实没广告" -> 照常走免费重试。
    CLICKS[:] = []
    FT.t = 22000.0
    base = load('shots/result_live005639.png')
    _real_sample, _real_screen = app._ad_sample, g.capture_screen
    app._ad_sample = lambda *a, **k: None      # 离线帧不许写进取证目录
    app.dry_run, app.ad_screen = False, True
    app.cur_page = 'result'
    app.start_ad_watch('回归-屏幕上有广告层')
    FT.t += App.AD_NOT_AD_AT + 1 + App.AD_NOT_AD_SAME_AT
    try:
        g.capture_screen = lambda hwnd: Image.new('RGB', base.size, (255, 255, 255))
        check(app._ad_tick(base) == 'wait',
              '屏幕通道显示有层盖着(分歧度 100%)却撒手/重试 -> 会自己把广告打断')
        check(not CLICKS and app._ad_until > 0, '这种帧一个像素都不该点: %s' % (CLICKS,))
        g.capture_screen = lambda hwnd: base.copy()
        FT.t += App.AD_NOT_AD_SAME_AT
        check(app._ad_tick(base) == 'acted',
              '两条通道一致 = 确实没广告 -> 该免费再点一次[领取], 不该干等')
        check(CLICKS == [ad_claim_pos(base)], '重试落点不对: %s' % (CLICKS,))
        _d = screen_div_frac(base, base.copy())
        print('    分歧度: 屏幕被广告盖住=%.0f%% / 两通道同一帧=%.0f%% / 阈值=%.0f%% (无广告基线实测 4.1~5.2%%)'
              % (screen_div_frac(base, Image.new('RGB', base.size, (255, 255, 255))) * 100,
                 _d * 100, AD_DIVERGE_FRAC * 100))
        check(_d < AD_DIVERGE_FRAC, '同一帧自比分歧度必须为 0, 实为 %s' % _d)
    finally:
        g.capture_screen, app._ad_sample = _real_screen, _real_sample
        app.dry_run = True

    CLICKS[:] = []
    FT.t = 30000.0
    black = Image.new('RGB', (552, 1006), (0, 0, 0))
    app.cur_page = 'result'
    app.start_ad_watch('回归-黑屏')
    FT.t += App.AD_NOT_AD_AT + 1
    check(app._ad_tick(black) == 'wait', '黑屏帧(正在放广告, 只是顶栏没认出来)竟然撒手了')
    check(not CLICKS, '黑屏窗口里不该点任何东西: %s' % (CLICKS,))
    FT.t += 3.0
    check(app._ad_tick(load('shots/lobby_clean.png')) == 'wait',
          '刚见过黑屏 %ss 就撒手 -> 广告里画面一闪会被判成没进广告' % 3.0)
    FT.t += App.AD_BLACK_GRACE
    check(app._ad_tick(load('shots/lobby_clean.png')) == 'giveup',
          '黑屏超过 %ss 不再出现、还硬命中别的游戏页 -> 该撒手, 不能死等' % App.AD_BLACK_GRACE)
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
# 两档版式各拿一张真机帧跑端到端: result_live005639 是药丸在 (412,782) 的老版式,
# result_live024104 是礼包面板整块下移 40px、药丸在 (434,823) 的新版式。
for rel, want in (('shots/result_live005639.png', (412, 782)),
                  ('shots/result_live024104.png', (434, 823))):
    QUEUE[:] = [rel]
    CLICKS[:] = []
    # 两轮共用一个 app: result 的[领取]有 120s 节流键(CLAIM_GAP), 不清历史第二轮会
    # 直接掉到[继续]分支(真机上这正确 —— 同一场结算不该连点两次礼包)
    app.last_action.clear()
    page, acted, ocr_ran = app.step()
    check(page is not None and page.name == 'result', '第 1 轮没定成 result(%s): %s' % (rel, page))
    check(acted and len(CLICKS) == 1 and near(CLICKS[0], want),
          '%s 结算页没点到黄色[领取](期望 %s±3): %s' % (rel, want, CLICKS))
    check(app._ad_until > 0, '点完[领取]没 arm 看广告窗口')
    check(ocr_ran is False and OCR_CNT[0] == 0, 'result 定页+点[领取]竟然花了 OCR')
    app._end_ad_watch()   # 换下一张帧之前先把窗口收了, 否则第二轮会被窗口吞掉
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
print('全部通过 (黄色[领取]点色判据 / 黑屏广告判据 / 药丸放完判据 / 看广告窗口状态机 / 全程零 OCR)')
print('覆盖: %d 帧结算页 + %d 帧异页 + %d 帧广告页 + %d 轮窗口状态机'
      % (n_pos, n_neg, len(PILL), n_round))
sys.exit(0)
