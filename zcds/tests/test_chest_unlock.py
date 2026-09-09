# -*- coding: utf-8 -*-
r"""宝箱槽位[免费解锁] vs [要宝石] 的角标判据回归(2026-09-03 19:2x 真机定案, 零 OCR)

坑(真机第 20 轮 bot.log L[7534:8337] 实测 12 次白跑): 卡片底部白字[点击解锁]对应**两种面板** ——
  免费 [解锁 🕐50分]  往这一格放一个宝箱 + 启动 50 分钟倒计时
  付费 [开启 💎120]   花 120 紫宝石立刻开
两种卡片长得一模一样(同一张宝箱图 / 同样的白字 / 同样的"5分/20分/1时"时长角标), 旧版把白字一律当免费,
于是每次都进面板被 chest_info 的宝石像素判成付费(实测 366) 再拉黑 300s —— 一次都没解锁成功过。

判据: 只有"此刻能免费操作"的格子, 卡片右上角才画红感叹号 ❗(实测 x=槽中心+36..+52 / y735..748)。
本脚本钉死四件事:
  [1] 语料全量: 每格角标像素数只能是 0 或 >=CHEST_BADGE_MIN, 不许有骑墙值(否则阈值站在悬崖上)
      帧尺子 = has_pvp 且 not nav_covered: 广告等待浮层(黑条)只盖 y>=845, [玩家对战]金按钮还露着,
      但宝箱卡片底部白字被切 -> 这类帧真机路由根本判不成大厅, 测试也不许当它是大厅帧(证据见 nav_covered)
  [2] 码表自洽: o/U 必带角标 / a/. 与 p 必不带(一条判据只计一次 -> 违反数 == 槽数)
  [3] 面板配对复核: 每张 chest_info 面板帧配到它前面最近(<=60s)的那张 lobby 帧,
      免费面板(带内宝石像素 0) <=> 那张大厅帧有 o/U 格; 付费面板(宝石像素 362) <=> 那张帧有 p 格
  [4] 行为: 有免费格只点免费格; 一格免费都没有 -> 试探点一格 p(用户口径, 面板宝石硬闸兜底); p 全拉黑 -> 改打对战
  [5] 本轮真机两帧(19:06 三格全免费 / 19:14 两格都要宝石), 帧不在就跳过
用法(脚本目录): python -X utf8 test_chest_unlock.py        # 退出码 0 = 全通过
"""
import os
import re
import sys
import glob
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from PIL import Image                                          # noqa: E402

import pick_print as pp                                        # noqa: E402
from auto_bot import App                                       # noqa: E402
from pages.base import color_button                            # noqa: E402
from pages.chest_info import ChestInfoPage, gem_cost_pixels, GEM_MIN   # noqa: E402
from pages.base import chest_slot_key, color_button                       # noqa: E402
from pages.lobby import (CHEST_SLOTS, CHEST_BADGE_MIN, CHEST_PROBE_P, LobbyPage,
                         PVP_BOX, PVP_COLOR, PVP_MIN_PX, CHEST_BLOCK_ALL)   # noqa: E402

FAILS = []
PAIR_WINDOW = 60          # 秒; 面板帧最多能比它来源的大厅帧晚 1 分钟


def check(cond, msg, detail=''):
    print('%-4s %-56s -> %s' % (cond, msg, detail))
    if not cond:
        FAILS.append(msg + ' | ' + detail)


def img_of(path):
    im = Image.open(path).convert('RGB')
    return im.resize(pp.REF) if im.size != pp.REF else im


LP = LobbyPage.__new__(LobbyPage)
CI = ChestInfoPage.__new__(ChestInfoPage)


def has_pvp(img):
    """[玩家对战]金按钮在 = 这张帧"看起来像大厅"。它**不是**最终尺子: 广告浮层帧也过(按钮画在黑条之上)。"""
    return img.size == pp.REF and color_button(img, PVP_BOX, PVP_COLOR, PVP_MIN_PX) is not None


# 🔴 帧尺子必须再叠一条"底部导航栏没被盖住", 否则测试比真机松 —— 2026-09-05 23:5x 假红实录:
#   现象: [1][2] 报"五档与角标像素完全自洽 违反=6", 定位到 3 个槽(shots_live/ads_141917_n /
#     ad_153914_n / ads_193653_n): st=.... 而 badge=[0,0,126,0] / [0,125,0,0] / [0,0,126,0]。
#   定性: 它们是 §35.1 点 a 格后 auto_bot 起的**广告窗口密拍 dump**(帧名 ad_*/ads_*_n.png, 现存 2542 张),
#     黑浮层([广告|30秒后可获得奖励]...[关闭])从 y~845 铺到窗底 -> 宝箱卡片底部的白字按钮带(y838..882)
#     被切掉 -> chest_states 读成 '.', 而卡片右上角那颗红 ❗(y735..748)露着 -> badge 125/126
#     与真 .UUU 帧的 120..127 **同一簇**(不是骑墙值, 判据没错, 帧才是脏的)。
#   实测(scratch/patch/_cu_band.py): 本页点色指纹 20 个判色点里的近黑数
#     正常大厅帧 0/20 (y845..905 暗像素 2.9% / y905..1005 12.5%)
#     上述密拍帧 20/20 (y845..905 暗 90.7~97.1% / y905..1005 90.3~100%)
#   => 真机路由对这些帧**一个指纹点都不中**, 永远不会进 LobbyPage.act() —— 判据侧无缺口,
#      要修的是测试的帧筛选: 让它和真机一样"看得见导航栏"才算大厅帧。
#   阈值取 15/20 而不是 20/20: 两簇实测 0 vs 20, 留余量是给"浮层只盖半屏"的改版, 不是给骑墙值开口子。
NAV_PRINT_POINTS = LobbyPage.prints[0]
NAV_COVER_BLACK_MAX = 45    # 单点地板: R/G/B 全 <45 记为"被黑条盖住"
NAV_COVER_MIN_POINTS = 15   # 20 个判色点 >=15 个变黑 -> 判为浮层帧


def nav_covered(img):
    """底部导航栏被广告等待浮层(黑条 + [关闭]药丸)盖住 -> 宝箱行不可信, 这张帧不参与大厅码表"""
    n = 0
    for x, y, _c in NAV_PRINT_POINTS:
        px = img.getpixel((x, y))[:3]
        if max(px[0], px[1], px[2]) < NAV_COVER_BLACK_MAX:
            n += 1
    return n >= NAV_COVER_MIN_POINTS


def is_lobby(img):
    """大厅帧尺子: [玩家对战]金按钮在 **且** 底部导航栏未被广告浮层盖住(证据见 nav_covered 上方)"""
    return has_pvp(img) and not nav_covered(img)


def ts6(stem):
    """帧名结尾的 HHMMSS; 没有(或不像时间)就返回 None"""
    m = re.search(r'(\d{6})$', stem)
    if not m:
        return None
    t = m.group(1)
    return t if int(t[:2]) < 24 and int(t[2:4]) < 60 and int(t[4:]) < 60 else None


def secs(t):
    return int(t[:2]) * 3600 + int(t[2:4]) * 60 + int(t[4:])


class Ctx(App):
    def click(self, x, y):
        self.clicks.append((int(x), int(y)))
        App.click(self, x, y)


def new_ctx(img):
    from vision import ScreenFeature
    c = Ctx(dry_run=True, low_cpu=False, resize=False)
    c.clicks = []
    c.f = ScreenFeature(img=img, boxes=[], joined='')
    c.last_action = {}
    return c


def main():
    paths = sorted(glob.glob(os.path.join(ROOT, 'shots', '*.png'))) + \
        sorted(glob.glob(os.path.join(ROOT, 'shots_live', '*.png')))

    lobby = []                       # (ts, 帧名, 状态码, 逐槽角标像素)
    hist = Counter()
    n_slot = n_gap = n_rule = 0
    n_cov = n_cov_ad = 0            # 被浮层排除的"伪大厅"帧: 总数 / 其中 ad 窗口密拍 dump
    cov_names = []                  # 非 dump 命名的浮层帧(出现就得人工看过才许放行)
    print('[1][2] 全量语料: 角标像素两簇 + 五档码表自洽')
    for p in paths:
        try:
            img = img_of(p)
        except Exception:
            continue
        stem = os.path.basename(p).rsplit('.', 1)[0]
        if not has_pvp(img):
            continue
        if nav_covered(img):
            # 广告浮层盖住底部 -> 宝箱行不可信, 不参与码表自洽(真机路由同样不会把这帧判成大厅)
            n_cov += 1
            if re.match(r'ads?_\d{6}_n$', stem):
                n_cov_ad += 1
            elif len(cov_names) < 8:
                cov_names.append(stem)
            continue
        st = LP.chest_states(img)
        bd = [LP.badge_pixels(img, cx) for cx, _ in CHEST_SLOTS]
        t = ts6(stem)
        if t:
            lobby.append((t, stem, st, bd))
        for i, code in enumerate(st):
            n_slot += 1
            hist[code] += 1
            has = bd[i] >= CHEST_BADGE_MIN
            if 0 < bd[i] < CHEST_BADGE_MIN:
                n_gap += 1
            # 一条判据只计一次。旧版这两条条件重叠: "o/U 该带角标却没带" 与 "a/. 不该带却带了"
            #   对同一个 '.'+带角标 的槽是同一件事 -> 一槽计 2 次, 3 个槽报成"违反=6", 数字对不上现场
            if has != (code in 'oU'):
                n_rule += 1
    check(n_slot >= 500, '大厅帧够多(逐槽观测数)', 'n_slot=%d' % n_slot)
    check(n_gap == 0, '角标像素没有 0..%d 之间的骑墙值' % CHEST_BADGE_MIN, '骑墙=%d' % n_gap)
    check(n_rule == 0, 'o/U/p/a/. 五档与角标像素完全自洽', '违反=%d 槽=%d' % (n_rule, n_slot))
    check(n_cov >= 1 and not cov_names,
          '广告浮层帧由 nav_covered 排除(测试帧尺子 == 真机路由)',
          '排除=%d ad密拍dump=%d 非dump命名=%s' % (n_cov, n_cov_ad, cov_names))
    check(min(hist.get(k, 0) for k in 'Upoa') >= 40, '四种状态都有足够样本', str(dict(sorted(hist.items()))))

    print('')
    print('[3] 面板配对复核: 免费面板<->有免费格, 付费面板<->有 p 格')
    lobby.sort()
    # 同一秒出现多张大厅帧且状态码不同 = 把面板帧挂到哪一张都无法归因
    # (实测来源: 两个 bot 并发往 shots_live/ 写帧)，这样的秒不参与配对
    _codes = {}
    for _lt, _lstem, _lst, _lbd in lobby:
        _codes.setdefault(_lt, set()).add(_lst)
    ambig = {k for k, v in _codes.items() if len(v) > 1}
    print('     同秒歧义大厅秒(状态码冲突, 不可归因) n_amb=%d %s'
           % (len(ambig), sorted(ambig)))
    pairs = set()
    n_amb_skip = 0
# 第一遍: 配对, 收集 panel -> lobby 配对
    _all_pairs = []
    for p in paths:
        stem = os.path.basename(p).rsplit('.', 1)[0]
        if 'chest_info' not in stem:
            continue
        t = ts6(stem)
        if not t:
            continue
        try:
            img = img_of(p)
        except Exception:
            continue
        btn = color_button(img, CI.BTN_BOX, CI.BTN_YELLOW, CI.BTN_MIN_PX)
        if btn is None:
            continue
        near = None
        for lt, lstem, lst, lbd in lobby:
            d = secs(t) - secs(lt)
            if 0 <= d <= PAIR_WINDOW and (near is None or d < near[0]):
                near = (d, lstem, lst, lt)
        if near is None:
            continue
        if near[3] in ambig:
            n_amb_skip += 1
            continue
        _all_pairs.append((t, gem_cost_pixels(img, btn[0], btn[1]) >= GEM_MIN, near[2], near[1], near[3]))
    # 第二遍: 同一大厅秒被 >= 2 张面板配对也当歧义 (R53 实证: 3 张面板 012039/012053/012122
    # 都配到 012039 那一张大厅帧, 但 lobby 已经被多次点击/状态变化, 单一快照不可靠)
    _paired_counts = {}
    for _, _, _, _, lt in _all_pairs:
        _paired_counts[lt] = _paired_counts.get(lt, 0) + 1
    stale_lobby = {k for k, v in _paired_counts.items() if v > 1}
    n_stale_skip = sum(_paired_counts[k] for k in stale_lobby)
    pairs = {(t, p, st, lstem) for (t, p, st, lstem, lt) in _all_pairs if lt not in stale_lobby}
    print('     同秒多面板歧义(lobby 快照被复用 n>=2 次) skip=%d ambig=%s'
          % (n_stale_skip, sorted(stale_lobby)))
    n_free = n_paid = v_free = v_paid = 0
    for t, paid, st, lstem in sorted(pairs):
        if paid:
            n_paid += 1
            if 'p' not in st:
                v_paid += 1
                print('     !! %s 付费面板, 但大厅帧 %s 没有 p 格: %s' % (t, lstem, st))
        else:
            n_free += 1
            if not any(c in 'oU' for c in st):
                v_free += 1
                print('     !! %s 免费面板, 但大厅帧 %s 一格免费的都没有: %s' % (t, lstem, st))
    print('     因歧义跳过的面板帧 n_amb_skip=%d' % n_amb_skip)
    check(n_free >= 8, '免费面板配对数', 'n_free=%d' % n_free)
    check(n_paid >= 25, '付费面板配对数', 'n_paid=%d' % n_paid)
    check(v_free == 0 and v_paid == 0, '配对零反例(角标判据 == 面板真值)',
          '违反 free=%d paid=%d' % (v_free, v_paid))

    print('')
    print('[4] 行为: [AD]格优先看广告 > 免费宝箱 > 试探 p 格 > 打对战 (2026-09-05 用户定案)')
    PVP = color_button(img_of(os.path.join(ROOT, 'shots', 'lobby_clean.png')),
                       PVP_BOX, PVP_COLOR, PVP_MIN_PX)
    # 含 a 格的四帧: 旧版(2026-09-03 晚口径)先试探 p; 09-05 起 a 格排第 0 优先。
    # probe_expect = "只把 a 格拉黑后"应回退到的 p 试探落点(= 旧版行为, 仍不许丢)
    AD_FIRST = [('shots/live_lobby.png', 'pppa', CHEST_SLOTS[3], CHEST_SLOTS[0]),
                ('shots/lobby_mixed_0019.png', 'ap..', CHEST_SLOTS[0], CHEST_SLOTS[1]),
                ('shots_live/tap_hero.png', 'appp', CHEST_SLOTS[0], CHEST_SLOTS[1]),
                ('shots_live/dbg_002_lobby_081833.png', 'ppap', CHEST_SLOTS[2], CHEST_SLOTS[0])]
    for rel, want, expect, probe_expect in AD_FIRST:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            print('     (跳过 %s)' % rel)
            continue
        img = img_of(p)
        st = LP.chest_states(img)
        check(st == want, '%-34s 状态码' % os.path.basename(rel), st)
        c = new_ctx(img)
        LobbyPage().act(c)
        check(c.clicks == [expect], '%-34s 广告优先点 a 格' % os.path.basename(rel), str(c.clicks))
        check(getattr(c, '_ad_until', 0) > 0,
              '%-34s 点 a 格必须同时 arm 看广告窗口' % os.path.basename(rel), str(c._ad_until))
        # p 格全拉黑(模拟面板判过付费): 广告优先不受影响, 仍点 a
        c2 = new_ctx(img)
        for slot, code in zip(CHEST_SLOTS, st):
            if code == 'p':
                c2.block(chest_slot_key(slot), 300, '回归: 模拟面板判付费')
        c2.last_action = {}
        LobbyPage().act(c2)
        check(c2.clicks == [expect], '%-34s p 全拉黑 -> a 格仍广告优先' % os.path.basename(rel), str(c2.clicks))
        # 只把 a 格拉黑: 回退到旧口径的 p 试探(免费/付费仍由面板宝石像素硬闸判)
        c3 = new_ctx(img)
        c3.block(chest_slot_key(expect), 300, '回归: 模拟 a 格广告入口失败')
        c3.last_action = {}
        LobbyPage().act(c3)
        check(c3.clicks == [probe_expect], '%-34s 只拉黑 a -> 回退试探 p' % os.path.basename(rel), str(c3.clicks))
        check(c3.chest_target == chest_slot_key(probe_expect),
              '%-34s 试探后回写 chest_target' % os.path.basename(rel), str(c3.chest_target))
        # a 和 p 都拉黑: 才轮到打对战
        c4 = new_ctx(img)
        for slot, code in zip(CHEST_SLOTS, st):
            if code in 'pa':
                c4.block(chest_slot_key(slot), 300, '回归: a/p 全拉黑')
        c4.last_action = {}
        LobbyPage().act(c4)
        check(c4.clicks == [PVP], '%-34s a/p 都拉黑 -> 打对战' % os.path.basename(rel), str(c4.clicks))

    DO_CHEST = [('shots/lobby_clean.png', 'UUUU'),          # 4 格全带角标
                ('shots/lobby_live004222.png', '.U..'),
                ('shots/live_20260902_a.png', 'o...'),
                ('shots/live_now2.png', 'UUUo')]

    # 合成状态矩阵: 真语料里"一格免费都没有"的帧恰好都带 p, 所以剩下三种组合只能造
    #   (做法 = 拿一张真 lobby 帧, 只把状态码换掉, 落点仍走真坐标)
    class StubLP(LobbyPage):
        fake = '....'

        def chest_states(self, img):
            return self.fake

    print('    合成状态矩阵(帧=shots/live_lobby.png, 只换状态码)')
    base = img_of(os.path.join(ROOT, 'shots', 'live_lobby.png'))
    for fake, why, want in [
            ('UpU.', '有免费格(U) -> 绝不点 p', [CHEST_SLOTS[0]]),
            ('op.o', '有[开启]格(o) -> 绝不点 p', [CHEST_SLOTS[0]]),
            ('a...', '只有[AD]格 -> 广告优先点它(2026-09-05)', [CHEST_SLOTS[0]]),
            ('....', '全空槽 -> 打对战', [PVP]),
            ('pp.p', '有 p 格 -> 试探最左那格', [CHEST_SLOTS[0]]),
    ]:
        StubLP.fake = fake
        c = new_ctx(base)
        StubLP().act(c)
        check(c.clicks == want, '合成 %s: %s' % (fake, why), str(c.clicks))
    StubLP.fake = 'pppp'
    c = new_ctx(base)
    c.block(CHEST_BLOCK_ALL, 60, '回归: 模拟用户手动开的面板判过付费')
    StubLP().act(c)
    check(c.clicks == [PVP], '合成 pppp + 整行拉黑: 连试探都不许', str(c.clicks))
    for rel, want in DO_CHEST:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            print('     (跳过 %s)' % rel)
            continue
        img = img_of(p)
        st = LP.chest_states(img)
        check(st == want, '%-34s 状态码' % os.path.basename(rel), st)
        c = new_ctx(img)
        LobbyPage().act(c)
        check(c.clicks and c.clicks[0] in CHEST_SLOTS,
              '%-34s 有免费格 -> 必须点宝箱' % os.path.basename(rel), str(c.clicks))

    print('')
    print('[5] 真机帧(在 scratch/ 里, 不在就跳过) + 行为')
    LIVE = [('scratch/chest_probe/live_190610.png', '.UUU', True),    # 19:06 三格免费[解锁 🕐50分]
            ('scratch/chest_probe/lobby_now.png', '..pp', False),     # 19:14 两格付费[开启 💎120]
            ('scratch/chest_probe/live_free.png', '.oUU', True),      # 19:33 第21轮首命中那一帧
            ]
    got = 0
    for rel, want, clickable in LIVE:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            continue
        got += 1
        img = Image.open(p).convert('RGB')
        st = LP.chest_states(img)
        check(st == want, '%-24s 状态码' % os.path.basename(rel),
              '%s 角标=%s' % (st, [LP.badge_pixels(img, cx) for cx, _ in CHEST_SLOTS]))
        c = new_ctx(img)
        LobbyPage().act(c)
        if clickable:
            check(c.clicks and c.clicks[0] in CHEST_SLOTS,
                  '%-24s 有免费格 -> 真机这帧确实点了宝箱' % os.path.basename(rel), str(c.clicks))
        else:
            first_p = CHEST_SLOTS[st.index('p')] if 'p' in st else PVP
            check(c.clicks == [first_p] and CHEST_PROBE_P,
                  '%-24s 无免费格 -> 真机这帧试探点了第一格 p' % os.path.basename(rel), str(c.clicks))
    if not got:
        print('     (真机帧都不在, 跳过)')

    print('')
    if FAILS:
        print('不通过 %d 项:' % len(FAILS))
        for m in FAILS:
            print('  - ' + m)
        return 1
    print('全部通过 (有免费格只点免费格; 一格免费都没有时试探点 p 格, 花不花钱交给面板的宝石像素硬闸)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
