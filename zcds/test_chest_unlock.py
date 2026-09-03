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
  [2] 码表自洽: o 必带角标 / a. 必不带 / U<->带角标 / p<->不带
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

ROOT = os.path.dirname(os.path.abspath(__file__))
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


def is_lobby(img):
    """大厅帧尺子: [玩家对战]那颗金按钮必须在(语料里与点色指纹 100% 同步)"""
    return img.size == pp.REF and color_button(img, PVP_BOX, PVP_COLOR, PVP_MIN_PX) is not None


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
    print('[1][2] 全量语料: 角标像素两簇 + 五档码表自洽')
    for p in paths:
        try:
            img = img_of(p)
        except Exception:
            continue
        if not is_lobby(img):
            continue
        stem = os.path.basename(p).rsplit('.', 1)[0]
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
            if has != (code in 'oU'):
                n_rule += 1
            if code in 'a.' and has:
                n_rule += 1
    check(n_slot >= 500, '大厅帧够多(逐槽观测数)', 'n_slot=%d' % n_slot)
    check(n_gap == 0, '角标像素没有 0..%d 之间的骑墙值' % CHEST_BADGE_MIN, '骑墙=%d' % n_gap)
    check(n_rule == 0, 'o/U/p/a/. 五档与角标像素完全自洽', '违反=%d' % n_rule)
    check(min(hist.get(k, 0) for k in 'Upoa') >= 40, '四种状态都有足够样本', str(dict(sorted(hist.items()))))

    print('')
    print('[3] 面板配对复核: 免费面板<->有免费格, 付费面板<->有 p 格')
    lobby.sort()
    pairs = set()
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
                near = (d, lstem, lst)
        if near is None:
            continue
        pairs.add((t, gem_cost_pixels(img, btn[0], btn[1]) >= GEM_MIN, near[2], near[1]))
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
    check(n_free >= 8, '免费面板配对数', 'n_free=%d' % n_free)
    check(n_paid >= 25, '付费面板配对数', 'n_paid=%d' % n_paid)
    check(v_free == 0 and v_paid == 0, '配对零反例(角标判据 == 面板真值)',
          '违反 free=%d paid=%d' % (v_free, v_paid))

    print('')
    print('[4] 行为: 有免费格只点免费格 / 全无免费 -> 试探点 p 格 / p 也拉黑了才去打对战')
    PVP = color_button(img_of(os.path.join(ROOT, 'shots', 'lobby_clean.png')),
                       PVP_BOX, PVP_COLOR, PVP_MIN_PX)
    # 无免费格(全 p 或 .)的四帧: 2026-09-03 晚改口径 -> 不再"只打对战", 而是试探点**第一格 p**
    PROBE = [('shots/live_lobby.png', 'pppa', CHEST_SLOTS[0]),        # 3 格白字无角标 + 1 格[AD]
             ('shots/lobby_mixed_0019.png', 'ap..', CHEST_SLOTS[1]),      # 1 格[AD] + 1 格白字无角标 -> 点那格 p
             ('shots_live/tap_hero.png', 'appp', CHEST_SLOTS[1]),     # 3 格 p -> 点最左那格 p
             ('shots_live/dbg_002_lobby_081833.png', 'ppap', CHEST_SLOTS[0])]
    DO_CHEST = [('shots/lobby_clean.png', 'UUUU'),          # 4 格全带角标
                ('shots/lobby_live004222.png', '.U..'),
                ('shots/live_20260902_a.png', 'o...'),
                ('shots/live_now2.png', 'UUUo')]
    for rel, want, expect in PROBE:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            print('     (跳过 %s)' % rel)
            continue
        img = img_of(p)
        st = LP.chest_states(img)
        check(st == want, '%-34s 状态码' % os.path.basename(rel), st)
        c = new_ctx(img)
        LobbyPage().act(c)
        if expect is None:
            check(c.clicks == [PVP], '%-34s 无免费格也没 p 格 -> 改打对战' % os.path.basename(rel), str(c.clicks))
        else:
            check(c.clicks == [expect], '%-34s 无免费格 -> 试探点 p 格' % os.path.basename(rel), str(c.clicks))
            check(c.chest_target == chest_slot_key(expect),
                  '%-34s 试探后回写 chest_target' % os.path.basename(rel), str(c.chest_target))
            # 那一格被面板判付费拉黑后: 不许再点第二格以外的东西, 也不许点 a/. 格
            c2 = new_ctx(img)
            for slot, code in zip(CHEST_SLOTS, st):
                if code == 'p':
                    c2.block(chest_slot_key(slot), 300, '回归: 模拟面板判付费')
            c2.last_action = {}
            LobbyPage().act(c2)
            check(c2.clicks == [PVP], '%-34s p 格全拉黑 -> 回到只打对战' % os.path.basename(rel), str(c2.clicks))

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
            ('a...', '只有[AD]格 -> 没得试探, 打对战', [PVP]),
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
