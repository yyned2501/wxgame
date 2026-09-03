# -*- coding: utf-8 -*-
"""离线路由回归: 点色指纹 -> route() 的完整决策链(不开窗口, 不跑 OCR)

tools/pick_print.py verify 只测 match_print(纯指纹层); 本脚本补 auto_bot.step()
真正调用的 route(): 指纹优先 -> prefer(上一步声明的转移候选) -> OCR 兜底 -> unknown.

用法(项目根目录): python -X utf8 test_print_route.py     # 退出码 0 = 全通过
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from PIL import Image

import colorprint as cp                        # 判色原语(造「只差一个点」的帧)
import pick_print as pp                        # 复用同一份语料标注, 不两处维护
from pages import ALL_PAGES
from pages.base import detect_ocr, is_soft, route, route_prints, soft_hit
from vision import ScreenFeature

# 无指纹页只允许两种存在方式: 只靠 OCR 认页的弹窗类(写在检查里),
# 或者像 tab_other 这样由"上下文 + 一条点色判据"推出身份、压根不需要 OCR
CONTEXT_PAGES = ('tab_other',)
FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print('  FAIL  ' + msg)


class _Fake:
    """软命中门限测试用的假页(只要 name 参与打分)"""

    def __init__(self, name):
        self.name = name


def blotch(img, pt, color=(0, 0, 0), r=1):
    """遮住单个判色点: 只涂该点自己的 3x3(pos_tol=1 的取样域)。

    指纹是「十字 5 点」一组组标出来的, 涂满 7x7 会一次干掉整组(5 个点),
    那是「页面真的变了」而不是动画遮挡 -> 本用例要复现的是差 1 个点这种最琐碎的情况。
    """
    x, y = pt[0], pt[1]
    a = np.asarray(img).copy()
    a[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1] = color
    return Image.fromarray(a)


def feat(name, text='', size=None):
    """造一帧真实的 ScreenFeature: img 用语料截图, joined 手喂(等价一次 OCR 结果)

    size 非空则把帧缩到该尺寸, 用来复现"玩家拖动了窗口 -> 指纹层整片失效"的真机场景。
    """
    img = Image.open(pp.img_path(name)).convert('RGB')
    if size and img.size != size:
        img = img.resize(size, Image.LANCZOS)
    return ScreenFeature(img=img, boxes=[], joined=text)


def main():
    corpus = pp.corpus()
    print('[1] 全语料 指纹定页: %d 张' % len(corpus))
    for lbl, name, _ in corpus:
        page, score, src = route(ALL_PAGES, feat(name), prefer=())
        want = pp.group_of(lbl)
        if want == 'other':
            check(not src.startswith('print'),
                  'other %s 不该被指纹命中(实际 %s %s %.2f)' % (name, page.name, src, score))
        else:
            check(page.name == want and src.startswith('print') and score >= 1.0,
                  '%s(%s) 期望 %s, 实际 %s %s %.2f' % (name, lbl, want, page.name, src, score))

    print('[2] prefer(转移候选) 只影响顺序, 不改变结论')
    p, s, src = route(ALL_PAGES, feat('battle_full'), prefer=('battle',))
    check(p.name == 'battle' and src == 'print-prefer', 'battle_full prefer 命中应为 print-prefer, 实际 %s %s' % (p.name, src))
    p, s, src = route(ALL_PAGES, feat('battle_full'), prefer=('lobby',))
    check(p.name == 'battle' and src == 'print-order', 'battle_full prefer 未命中应回落 print-order, 实际 %s %s' % (p.name, src))
    p, s, src = route(ALL_PAGES, feat('chestinfo'), prefer=('lobby',))
    check(p.name == 'chest_info' and src == 'print-order', 'prefer 里的页不得压过真实指纹, 实际 %s %s' % (p.name, src))

    print('[3] 指纹(像素) 优先于文字: 大厅上叠弹窗文案时仍判大厅')
    p, s, src = route(ALL_PAGES, feat('live_lobby', text='购买礼包 月卡 特权 超值'), prefer=())
    check(p.name == 'lobby' and src.startswith('print'),
          '指纹应压过 vip_popup 文案, 实际 %s %s' % (p.name, src))

    print('[4] 指纹没全中 -> 回退 OCR 打分')
    other = [n for lbl, n, _ in corpus if lbl == 'other']
    p, s, src = route(ALL_PAGES, feat(other[0], text='玩家对战'), prefer=())
    check(p.name == 'lobby' and src == 'ocr', '兜底应走 OCR 判 lobby, 实际 %s %s %.2f' % (p.name, src, s))
    p, s, src = route(ALL_PAGES, feat(other[0], text=''), prefer=())
    check(p.name == 'unknown' and src == 'unknown', '指纹和文字都没依据时应 unknown, 实际 %s %s' % (p.name, src))
    for n in other:
        p, s, src = route(ALL_PAGES, feat(n), prefer=())
        check(src in ('ocr', 'unknown'), 'other %s 落到了指纹层 %s %s' % (n, p.name, src))

    print('[5] 页面声明自检')
    n_fp = 0
    for pg in ALL_PAGES:
        fps = pg.fingerprints()
        if fps:
            n_fp += 1
            check(all(len(fp) >= 15 for fp in fps),
                  '%s 有指纹组不足 15 个判色点(3 个十字单元)' % pg.name)
        else:
            # 无指纹页只允许两种存在方式:
            #   a 只靠 OCR 认页(弹窗类, 文案就是身份)
            #   b 靠"上下文 + 一条点色判据"推出身份, 根本不需要 OCR —— tab_other 就是这样:
            #     底部导航栏在(16 个静态像素)而大厅指纹没中 => 我在别的页签上
            check(pg.name in ('ad_popup', 'claim_popup', 'diamond_popup', 'unknown')
                  or pg.name in CONTEXT_PAGES,
                  '%s 没有指纹, 既不在只走 OCR 的清单里, 也不在上下文页清单里' % pg.name)
    check(ALL_PAGES[-1].name == 'unknown', 'ALL_PAGES 最后一项必须是 unknown(兜底)')
    print('    %d/%d 页已标点色指纹; 只走 OCR: %s'
          % (n_fp, len(ALL_PAGES), ', '.join(p.name for p in ALL_PAGES if not p.fingerprints())))

    print('[6] OCR 同分 tie-break: 常驻文案不得把大厅抢成 VIP 弹窗')
    # 真机陷阱: 大厅右上角一直挂着"月卡", 和 vip_popup 的关键词同分(都 1.0);
    # ALL_PAGES 里 vip_popup 排在 lobby 前面 -> 旧版按注册顺序取先出现的最大值, 会误判成弹窗。
    txt = '玩家对战 月卡 特权 购买礼包'      # 大厅常驻"月卡" => 与 vip_popup 的 detect 同分 1.0
    for sz in [(431, 788), (500, 911)]:      # 窗口被拖动缩放 -> 指纹没全中, 只能走 OCR 兜底
        f6 = feat('live_lobby', text=txt, size=sz)
        p6, s6 = detect_ocr(ALL_PAGES, f6)
        check(p6.name == 'lobby', '%dx%d 同分应判 lobby, 实际 %s %.2f' % (sz + (p6.name, s6)))
        # 缩放过的帧点色可能仍能「软命中」(指纹按整帧比例换算), 但绝不能被同分的 vip_popup 抢走
        p6b, _s6b, src6 = route(ALL_PAGES, f6, prefer=())
        check(p6b.name == 'lobby' and (src6 == 'ocr' or src6.startswith('print')),
              '%dx%d 路由应落 lobby(点色/软命中/ocr 都行), 实际 %s %s' % (sz + (p6b.name, src6)))
    # 反过来: 只剩弹窗文案(没有"玩家对战")时, 不得被 tie-break 抢给大厅
    f6c = feat('live_lobby', text='购买礼包 月卡 特权', size=(431, 788))
    p6c, _ = detect_ocr(ALL_PAGES, f6c)
    check(p6c.name == 'vip_popup', '只有弹窗文案时应照旧判 vip_popup, 实际 %s' % p6c.name)

    print('[7] 顶栏闸门: 指纹不得只靠顶栏资源数字(y<130)')
    # 真机教训: 旧 lobby 指纹 15 个点全落在金币/钻石数字上, 语料里恰好数值相同 -> 70/70 是假绿灯,
    # 换个账号/资源一变就整片失效。lobby 已重新标定到 y>=130, 这里钉死; 其余页只报警不判失败。
    for pg in ALL_PAGES:
        ys = [y for fp in pg.fingerprints() for xy in fp for y in (xy[1],)]
        if not ys:
            continue
        if pg.name == 'lobby':
            check(min(ys) >= 130, 'lobby 指纹落进顶栏数字区(最小 y=%d < 130)' % min(ys))
        elif max(ys) < 130:
            print('    !! %s 的指纹全在顶栏 y<130 (%d~%d): 换账号数值即失效, 需真机补拍再重标'
                  % (pg.name, min(ys), max(ys)))


    print('[8] 宝箱槽位坐标: 必须落在实测卡片矩形内部(旧值 y=741 在卡片外, 真机 19 次点空)')
    import numpy as np
    from pages.lobby import CHEST_SLOTS, CHEST_BAND

    def card_grid(path):
        """不靠人工标注, 直接从像素反推 4 张宝箱卡片的矩形 -> (y0, y1, [(x0,x1), ...])"""
        a = np.asarray(Image.open(path).convert('RGB')).astype(int)
        r, g2, b = a[..., 0], a[..., 1], a[..., 2]
        bg = (b < 130) & (r < 60)                     # 卡片之间/两侧的深色底
        prof = [bg[y, 40:512].mean() for y in range(700, 905)]
        on = [(p > 0.10) and (p < 0.45) for p in prof]  # 一行里正好"4 张卡 + 3 条缝"
        best, s = (0, 0, 0), None
        for i, v in enumerate(on):
            if v and s is None:
                s = i
            if (not v or i == len(on) - 1) and s is not None:
                if i - s > best[0]:
                    best = (i - s, s + 700, i - 1 + 700)
                s = None
        y0, y1 = best[1], best[2]
        cols = [bg[y0:y1 + 1, x].mean() < 0.35 for x in range(40, 512)]
        runs, s = [], None
        for i, v in enumerate(cols):
            if v and s is None:
                s = i
            if (not v or i == len(cols) - 1) and s is not None:
                if i - s >= 40:
                    runs.append((s + 40, i - 1 + 40))
                s = None
        return y0, y1, runs

    LV = os.path.join(ROOT, 'shots_live')
    geo = [os.path.join(ROOT, 'shots', n + '.png') for n in
           ('lobby_clean', 'after_battle_btn', 'live_20260902_a')]
    geo += [os.path.join(LV, f) for f in (sorted(os.listdir(LV)) if os.path.isdir(LV) else [])
            if f.startswith('probe_ref_')]
    for gp in geo:
        y0, y1, runs = card_grid(gp)
        base = os.path.basename(gp)
        check(y1 - y0 > 100, '%s 卡片带太窄: %d..%d' % (base, y0, y1))
        for i, (sx, sy) in enumerate(CHEST_SLOTS):
            check(any(x0 <= sx <= x1 for x0, x1 in runs),
                  '%s 槽%d x=%d 落在卡片外, 列块=%s' % (base, i + 1, sx, runs))
            check(y0 + 20 <= sy <= y1 - 8,
                  '%s 槽%d y=%d 出卡片纵向范围(%d..%d)' % (base, i + 1, sy, y0, y1))
        check(CHEST_BAND[0] <= y0 + 10 and CHEST_BAND[1] >= y0 + 30,
              '%s CHEST_BAND=%s 罩不住卡片顶部的倒计时角标(y%d..%d)'
              % (base, CHEST_BAND, y0, y0 + 30))
        print('    %-28s 卡片带 y%d..%d  列块 %s' % (base, y0, y1, runs))


    print('[9] 宝箱槽位/玩家对战: 动作层点色判据, 码表须与人工核对过的真值一致(零 OCR)')
    from pages.lobby import (LobbyPage, CHEST_SLOTS as SLOTS, PVP_BOX, PVP_COLOR, PVP_MIN_PX)
    from pages.base import color_button

    # 真值来源: 2026-09-03 逐槽用 OCR 读出按钮文字再人工订正, 与点色判据 132 个观测全部对上
    # (复核脚本 scratch/scripts/slot_truth2.py, 明细 scratch/o_truth2.txt; 改阈值后重跑它即回归)
    #   o=[开启]倒计时结束免费领  U=[点击解锁]且卡片右上角有红感叹号(点它免费解锁)
    #   p=[点击解锁]但没有红角标 —— 面板只会是[开启 💎120], 点它=白跑一趟, 一律不点
    #   .=空槽位(按钮行没东西)  a=[[AD]-30分钟]冷却中 —— 点它=看激励视频减冷却, 这一格**永远不点**
    #     (与 config.WATCH_ADS 无关: 它的下游面板从未采集过, 而且要占一天 8 次的广告额度, 见 pages/lobby.py)
    # 2026-09-03 19:2x: 旧码表的 u 全拆成 U/p。角标判据实测(回归脚本 test_chest_unlock.py):
    #   149 帧大厅 x 4 槽 = 596 个观测, 角标像素只有 0 和 120~128 两簇, 中间值 0 个;
    #   chest_info 面板帧按时间戳配对复核 43 次(免费 9 / 付费 34), 零反例。见 pages/lobby.py CHEST_BADGE_*
    # 已核对过的 OCR 误读(点色判据比它准): live_lobby 槽4 / guide_live2 槽1(开启读成"开")
    #   / lobby_cooling_2335 / lobby_mixed_0019 / lobby_live010807 槽1(-30分钟读成"-30分神")
    EXPECT = {
        'after_battle_btn': '....', 'after_click': '....', 'after_click2': '....',
        'before_click': '....', 'bg_after': '....', 'bg_before': '....',
        'expl_a_slot': '....', 'expl_b_after_slot': '....', 'flow_0_lobby': '....',
        'flow_1_after_pvp_click': '....', 'probe_flag2': '....', 'screen_current': '....',
        'step0_main': '....', 'step1_battle_entry': '....', 'view1': '....',
        'lobby_live014209': '....',
        'flow4_s1_after_continue': 'U...', 'flow4_s2_later': 'U...',   # 与 lobby_clean 槽1 同帧(yb=0 w=392)=点击解锁+红角标=免费
        'live_20260902_a': 'o...', 'live_20260902_b': 'o...', 'live_20260902_c': 'o...',
        'live_20260902_d': 'o...', 'lobby_chest_ready_2355': 'o...', 'lobby_live013938': 'o...',
        'lobby_live014158': 'o...',                      # 槽1[开启]满金, 槽2-4 空槽位
        'live_lobby': 'pppa', 'live_now2': 'UUUo', 'lobby_clean': 'UUUU',
        'guide_live2': 'oUUU', 'lobby_cooling_2335': 'a...', 'lobby_live010807': 'a...',
        'lobby_mixed_0019': 'ap..', 'lobby_live004222': '.U..', 'lobby_live010733': 'Uo..',
        'lobby_live035055': 'oU..',                      # 槽1[开启] + 槽2[点击解锁](15分) 同时存在
        # 下面 15 帧是同一段真机 burst(按钮行逐帧有动画), 人工核对: 解锁/解锁/开启/解锁
        'lobby_live100100': 'UUoU',
        'lobby_live100200': 'UUoU',
        'lobby_live100201': 'UUoU',
        'lobby_live100202': 'UUoU',
        'lobby_live100203': 'UUoU',
        'lobby_live100204': 'UUoU',
        'lobby_live100205': 'UUoU',
        'lobby_live100206': 'UUoU',
        'lobby_live100207': 'UUoU',
        'lobby_live100208': 'UUoU',
        'lobby_live100209': 'UUoU',
        'lobby_live100210': 'UUoU',
        'lobby_live100211': 'UUoU',
        'lobby_live100212': 'UUoU',
        'lobby_live100213': 'UUoU',
    }
    lp = LobbyPage()
    n_chk = 0
    for nm in pp.LABELS['lobby']:
        base = os.path.basename(nm).rsplit('.', 1)[0]
        path = pp.img_path(nm)
        if not path or os.path.splitext(os.path.basename(path))[0] != base:
            continue                      # 只认 shots/<stem>.png 的真图帧
        want = EXPECT.get(base)
        if want is None:
            print('    ?? %-24s 码表未登记, 请核对后补进 EXPECT' % base)
            continue
        img = Image.open(path).convert('RGB')
        n_chk += 1
        got = lp.chest_states(img)
        check(got == want, '%s 槽位点色码 %s != 真值 %s' % (base, got, want))
        # 可点槽位必须恰好是码里 o/u 那几格: 少了=漏领(23:55 真机就是这样永远不开箱),
        # 多了=把冷却中的 [[AD]] 格点成了看广告
        ready = lp._ready_chests(img)
        exp = [SLOTS[i] for i, ch in enumerate(want) if ch in 'oU']
        check(ready == exp, '%s 可点槽位 %s != %s' % (base, ready, exp))
        # [玩家对战]按钮: 外接框中心恒为 (180,675)(取样框 2026-09-03 收紧过, 见 pages/lobby.py PVP_BOX)
        pos = color_button(img, PVP_BOX, PVP_COLOR, PVP_MIN_PX)
        check(pos is not None and abs(pos[0] - 180) <= 8 and abs(pos[1] - 675) <= 8,
              '%s 玩家对战按钮点色没命中/跑偏: %s' % (base, pos))
    check(n_chk >= len(EXPECT) - 5,
          'lobby 帧只核了 %d/%d 张, 语料或码表脱节了' % (n_chk, len(EXPECT)))
    print('    %d 帧: 槽位状态 + 可点集合 + 玩家对战中心 全部点色命中' % n_chk)

    print('[10] 软命中门限: 差<=1 点且甩开第二名才放行, 差 2 点交回 OCR')
    # 门限本身用假分数直接钉死(不必造图, 也不会随语料漂移)
    pa, pb = _Fake('a'), _Fake('b')
    check(soft_hit([(14 / 15, 15, pa, 'order')])[0] is pa, '15 点差 1 个应软命中')
    # soft_hit 只回原始来源, '-soft' 后缀由 match_print 打(端到端见下面的真图用例)
    check(soft_hit([(24 / 25, 25, pa, 'order')])[2] == 'order', '软命中须保留原始来源(order)')
    check(soft_hit([(24 / 25, 25, pa, 'prefer')])[2] == 'prefer', '软命中须保留原始来源(prefer)')
    check(soft_hit([(24 / 25, 25, pa, 'order'), (0.9, 25, pb, 'order')])[0] is None,
          '只甩开 0.06(<0.20)不得软命中')
    check(soft_hit([(28 / 30, 30, pa, 'order')])[0] is None, '差 2 点不得软命中')
    check(soft_hit([(0.0, 0, pa, 'order')])[0] is None, '没指纹的页(点数<8)不得白捡软命中')
    for base, lbl in (('live_lobby', 'lobby'), ('battle_full', 'battle')):
        img0 = Image.open(pp.img_path(base)).convert('RGB')
        pg = [q for q in ALL_PAGES if q.name == lbl][0]
        p, sc, src = route_prints(ALL_PAGES, img0)
        check(p is pg and not is_soft(src),
              '%s(%s) 原图应点色全中, 实际 %s %s %.3f' % (base, lbl, p and p.name, src, sc))
        crit = next((xy for xy in pg.fingerprints()[0] if pg.print_score(blotch(img0, xy)) < 1.0), None)
        check(crit is not None, '%s 找不到「遮住就不全中」的关键点, 该页指纹形同虚设?' % base)
        if crit:
            p, sc, src = route_prints(ALL_PAGES, blotch(img0, crit))
            check(p is pg and is_soft(src),
                  '%s(%s) 遮 1 个点应软命中(不许跑 OCR), 实际 %s %s %.3f'
                  % (base, lbl, p and p.name, src, sc))
            others = [xy for xy in pg.fingerprints()[0] if xy != crit]
            p, sc, src = route_prints(ALL_PAGES, blotch(blotch(img0, crit), others[0]))
            check(p is None,
                  '%s(%s) 遮 2 个点该交 OCR 兜底, 实际 %s %s %.3f' % (base, lbl, p and p.name, src, sc))
    print('')
    if FAILS:
        print('不通过 %d 项:' % len(FAILS))
        for m in FAILS:
            print('  - ' + m)
        return 1
    print('全部通过 (共 %d 张语料)' % len(corpus))
    return 0


if __name__ == '__main__':
    sys.exit(main())
