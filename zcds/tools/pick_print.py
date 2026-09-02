# -*- coding: utf-8 -*-
"""点色指纹标定/校验工具 (mxdzz: App.get_points 的工程化版本)

用法(在项目根目录):
  python tools/pick_print.py check                        # 语料是否覆盖全部截图
  python tools/pick_print.py pick --label lobby           # 自动求 lobby 页指纹(自动分形态)
  python tools/pick_print.py pick --label battle -n 5 --region 0,300,552,1006
  python tools/pick_print.py pick --label result --no-cross   # 退化成 mxdzz 单点式指纹
  python tools/pick_print.py verify [-v]                  # 用 pages/*.py 的指纹跑全语料回归

标定原理(相对 mxdzz 手写 points 的改进):
  1) 同页截图先按画面差异聚类 -> 同一页面的不同形态(角标/卡槽/皮肤)各成一簇, 一页多组指纹
  2) 候选单元默认是"十字 5 点"(中心 + 上下左右 2px), 每点带自己的颜色
     -> 单点容易撞上巧合色(白字/黑边), 5 点局部模板几乎不会
  3) 候选单元要在本形态截图上稳定命中(--min-frames, 默认 100%) -> 自动滤掉动画/倒计时/随机棋盘
     判色基准统一取"本形态第一帧"的颜色: 否则算其他页时拿的是它自己的颜色当基准, 量的是自稳
  4) 贪心: 每步选"能排除最多其他页截图"的单元, 其他页清零后继续补足到 --min-cross
  5) 复核: 本簇每张全中 + 其他页零误中 + 打印 margin(其他页最高命中比例, 越低越安全)
"""
import argparse
import glob
import math
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import colorprint as cp                                              # noqa: E402

REF = cp.REF_SIZE
OFFSETS = [(0, 0), (2, 0), (-2, 0), (0, 2), (0, -2)]                 # 十字单元
# 语料: 每页多张真实截图(552x1006), 用于"同页要稳、异页要区分"
LABELS = {
    'lobby': ['shots/after_battle_btn', 'shots/after_click', 'shots/after_click2', 'shots/before_click',
              'shots/bg_after', 'shots/bg_before', 'shots/expl_a_slot', 'shots/expl_b_after_slot', 'shots/flow_0_lobby',
              'shots/flow_1_after_pvp_click', 'shots/flow4_s1_after_continue', 'shots/flow4_s2_later',
              'shots/live_lobby', 'shots/live_now2', 'shots/lobby_clean', 'shots/probe_flag2', 'shots/screen_current',
              'shots/step0_main', 'shots/step1_battle_entry', 'shots/view1', 'shots/guide_live2',
              'shots/live_20260902_a', 'shots/live_20260902_b', 'shots/live_20260902_c', 'shots/live_20260902_d',
              'shots/lobby_cooling_2335', 'shots/lobby_chest_ready_2355', 'shots/lobby_mixed_0019'],
    'battle': ['shots/battle_full', 'shots/exp_battle0', 'shots/exp_click50', 'shots/flow2_m0', 'shots/flow2_m1',
               'shots/flow2_m2', 'shots/flow2_m3', 'shots/flow2_m4', 'shots/flow2_m5', 'shots/flow3_r0', 'shots/sample4',
               'shots/watch_124607', 'shots/watch_124633', 'shots/battle_live_004258',
               'shots/battle_live_004301', 'shots/battle_live_004305',
               'shots/battle_live_004308', 'shots/battle_live_004311',
               'shots/battle_live_004314'],
    'result': ['shots/flow3_end1', 'shots/flow3_r1', 'shots/flow4_s0_result', 'shots/now', 'shots/st_1',
               'shots/help_live', 'shots/watch_124652', 'shots/watch_124654',
               'shots/watch_124656', 'shots/watch_124658', 'shots/watch_124700',
               'shots/watch_124705', 'shots/watch_124707'],
    'chest_info': ['shots/chestinfo', 'shots/stuck_010826', 'shots/stuck_011012',
                   'shots/stuck_011157', 'shots/stuck_011347', 'shots/stuck_011536',
                   'shots/stuck_011716', 'shots/chest_info_iron_2334',
                   # 5 张**要花钱**的面板(人眼核对: 按钮带内紫宝石像素都是 362), 命名即真值 ->
                   # 免费帧走上面的 <label>_live* 自动登记, 付费帧必须显式登记(名字里没有 live),
                   # 否则 harvest_live 挑进来会被当成免费帧, 价格护栏回归就假绿了。
                   'shots/chest_info_paid_005704', 'shots/chest_info_paid_005708',
                   'shots/chest_info_paid_031415', 'shots/chest_info_paid_035442',
                   'shots/chest_info_paid_040458'],
    'vip_popup': ['shots/ask_battle', 'shots/live_now', 'shots/now_state', 'shots/p0'],
    'vip_month': ['shots/st_2', 'shots/vip_month_0003'],                       # 月卡礼包弹窗(vip_popup 的另一种形态)
    'matching': ['shots/sm_after'],
    'chest_open': ['shots/chest_open_claim', 'shots/chest_open_close', 'shots/chest_open_reward'],
    'versus': ['shots/versus_live005730.png'],
    'other': ['shots/dbg', 'shots/probe_flag0', 'shots/st_0', 'shots/guide_live1', 'shots/guide_live3', 'shots/watch_124711',
              'shots/watch_124723', 'shots/watch_124735', 'shots/watch_124746',
              'shots/watch_124758', 'shots/other_quest_0022'],
}
# ---- 自动登记真机帧: 只要把 shots_live 挑出来的帧按 <label>_live<HHMMSS>.png 放进 shots/,
#      这里就自动并入 LABELS, 不必再手改本文件(标定闭环少一步 manual)。
_live_added = {}
for _lbl in list(LABELS):
    _known = {os.path.splitext(os.path.basename(n))[0] for n in LABELS[_lbl]}
    for _p in sorted(glob.glob(os.path.join(ROOT, 'shots', _lbl + '_live*.png'))):
        if os.path.splitext(os.path.basename(_p))[0] not in _known:
            LABELS[_lbl].append('shots/' + os.path.basename(_p))
            _live_added.setdefault(_lbl, 0)
            _live_added[_lbl] += 1

# 归到同一"页面身份"的标签(同一 Page 类的多种形态)
GROUPS = {'vip_popup': ['vip_popup', 'vip_month']}

_cache = {}


def img_path(name):
    for base in (ROOT, os.path.join(ROOT, 'shots')):
        p = os.path.join(base, name if name.endswith('.png') else name + '.png')
        if os.path.exists(p):
            return p
    return None


def load(name) -> np.ndarray:
    if name not in _cache:
        im = Image.open(img_path(name)).convert('RGB')
        if im.size != REF:
            im = im.resize(REF)
        _cache[name] = np.asarray(im, dtype=np.uint8)
    return _cache[name]


def corpus():
    return [(lbl, n, load(n)) for lbl, names in LABELS.items() for n in names]


def group_of(label):
    for g, members in GROUPS.items():
        if label in members:
            return g
    return label


def cluster(names, arrs, thresh):
    """按平均像素差贪心聚类 -> (多帧簇列表, 孤立帧索引, 距离矩阵)"""
    sub = arrs[:, 8:998:3, 8:544:3, :].astype(np.int16)
    d = np.abs(sub[:, None] - sub[None, :]).mean((2, 3, 4))
    groups = []
    for i in range(len(names)):
        for g in groups:
            if d[i, g[0]] <= thresh:
                g.append(i)
                break
        else:
            groups.append([i])
    big = [g for g in groups if len(g) >= 2]
    lonely = [i for g in groups if len(g) == 1 for i in g]
    return big, lonely, d


# ---------------------------------------------------------------- check
def cmd_check(_args):
    seen = {n for names in LABELS.values() for n in names}
    actual = []
    for base in (ROOT, os.path.join(ROOT, 'shots')):
        for p in sorted(glob.glob(os.path.join(base, '*.png'))):
            if Image.open(p).size == REF:
                rel = os.path.relpath(p, ROOT).replace(os.sep, '/')
                actual.append(rel if rel.startswith('shots/') else os.path.basename(rel))
    missing = [a for a in actual if a[:-4] not in seen and a not in seen
               and 'shots/' + a[:-4] not in seen]
    ghost = [n for n in seen if not img_path(n)]
    print(f'语料 {len(seen)} 张 / 实际 {REF} 截图 {len(actual)} 张')
    print('未标注:', missing or '无')
    print('不存在:', ghost or '无')
    return 0 if not missing and not ghost else 1


# ---------------------------------------------------------------- pick
def _units(region, step, cross):
    """候选单元: 每个中心 -> 十字 5 点(或单点); 越界中心整组丢弃, 保证每单元点数一致

    返回 (centers, pts, per): pts 顺序为"中心优先、每中心连续 per 个点", 供 reshape 用。
    """
    offs = OFFSETS if cross else [(0, 0)]
    centers, pts = [], []
    for cx, cy in cp.grid_points(region, step):
        if all(2 <= cx + dx < REF[0] - 2 and 2 <= cy + dy < REF[1] - 2 for dx, dy in offs):
            centers.append((cx, cy))
            pts.extend((cx + dx, cy + dy) for dx, dy in offs)
    return centers, pts, len(offs)


def _ref_colors(frame, pts):
    """取 pts 在某一帧上的颜色序列 (P,3), 作为整批判色的基准"""
    ys = np.fromiter((y for _x, y in pts), dtype=np.intp, count=len(pts))
    xs = np.fromiter((x for x, _y in pts), dtype=np.intp, count=len(pts))
    return frame[ys, xs]


def _unit_matrix(frames, ref, pts, per, deg, tol):
    """批量判色 -> (帧数, 单元数) bool: 每帧里每个十字单元是否整组命中 ref(不压帧轴)

    ref 由调用方传"本形态第一帧"的颜色, 不能在函数里取 frames[0]: 那样算其他页时拿的是
    其他页自己的颜色当基准, 量出来的是"它自己稳不稳", 而不是"它会不会误中本页指纹"。
    """
    m = cp.color_match(frames, pts, ref, deg, tol)
    return m.reshape(m.shape[0], m.shape[1] // per, per).all(2)


def _pick_units(own, foreign, centers, pts, per, args):
    """返回 (选中的中心索引列表, 每单元的 foreign 命中率)"""
    n = len(centers)
    if not n or not len(pts):
        return [], np.zeros(n, float)
    deg, tol = args.degree, args.pos_tol
    ref = _ref_colors(own[0], pts)                              # 判色基准: 本形态第一帧
    own_u = _unit_matrix(own, ref, pts, per, deg, tol)          # (帧数, 单元数) 本形态每帧整组命中
    foreign_u = _unit_matrix(foreign, ref, pts, per, deg, tol)  # (帧数, 单元数) 其他页整组误中
    rate = foreign_u.mean(0)                              # 每单元在其他页的误中比例
    need = max(1, int(math.ceil(len(own) * args.min_frames)))
    pool = np.flatnonzero(own_u.sum(0) >= need)
    print(f'    候选单元 {n} / 本形态稳定 >= {need}/{len(own)} 帧 {len(pool)} 个')
    if not len(pool):
        return [], rate
    # 注意: px/py/used 都是 pool 的"池内位置"索引, 必须与 pool 的最终顺序一致
    bright = np.array([own[0][centers[i][1], centers[i][0]].sum() for i in pool], float)
    pool = pool[np.lexsort((-bright, rate[pool]))]         # 先 foreign 命中低, 再亮色
    px = np.array([centers[i][0] for i in pool], float)
    py = np.array([centers[i][1] for i in pool], float)
    alive = np.ones(foreign_u.shape[0], bool)
    fp = foreign_u[:, pool]
    used = np.zeros(len(pool), bool)
    sel = []
    while len(sel) < args.n:
        if not alive.any() and len(sel) >= args.min_cross:
            break
        keep = fp[alive].sum(0).astype(float) if alive.any() else np.zeros(len(pool))
        blocked = used.copy()
        for j in sel:
            blocked |= (px - centers[j][0]) ** 2 + (py - centers[j][1]) ** 2 < args.min_sep ** 2
        score = np.where(blocked, np.inf, keep + rate[pool])
        k = int(np.argmin(score))
        if not np.isfinite(score[k]):
            break
        sel.append(int(pool[k]))
        used[k] = True
        alive &= fp[:, k]
    return sel, rate


def _points_of(own0, center, cross):
    cx, cy = center
    offs = OFFSETS if cross else [(0, 0)]
    return [(cx + dx, cy + dy, cp.rgb2c(own0[cy + dy, cx + dx])) for dx, dy in offs]


def cmd_pick(args):
    label = args.label
    own_names_all = LABELS[label]
    arrs_all = np.stack([load(n) for n in own_names_all])
    same = group_of(label)
    foreign_meta = [(l, n, a) for l, n, a in corpus() if group_of(l) != same]
    foreign = np.stack([a for _l, _n, a in foreign_meta])
    region = (tuple(int(v) for v in args.region.split(',')) if args.region
              else (args.margin, args.margin, REF[0] - args.margin, REF[1] - args.margin))
    groups, lonely, _d = cluster(own_names_all, arrs_all, args.cluster)
    if not args.drop_lonely:
        # 孤立帧(只有一张的页 / 与本页其它形态差异过大)也要各成一形参与选指纹,
        # 否则 verify 要求"这张图必须判成本页"却没有任何指纹覆盖它, 复核还会退化成 0/0。
        groups, lonely = groups + [[i] for i in lonely], []
    if not groups:
        groups = [list(range(len(own_names_all)))]
    print(f'[{label}] {len(own_names_all)} 张 -> {len(groups)} 种形态'
          + (f'; 忽略孤立帧 {[own_names_all[i] for i in lonely]}' if lonely else ''))
    centers, pts, per = _units(region, args.step, args.cross)
    prints = []
    for gi, g in enumerate(groups):
        names = [own_names_all[i] for i in g]
        print(f'  [形态{gi + 1}] {names[0]} 等 {len(names)} 张'
              + ('   !! 单帧形态, 建议现场补拍再标定' if len(names) == 1 else ''))
        sel, _fr = _pick_units(arrs_all[g], foreign, centers, pts, per, args)
        fp = []
        for i in sel:
            fp.extend(_points_of(arrs_all[g][0], centers[i], args.cross))
        if fp:
            prints.append((names, fp))
    if not prints:
        print('没选出任何指纹')
        return 1
    # 复核
    lonely_names = {own_names_all[i] for i in lonely}
    all_own = [n for n in own_names_all if n not in lonely_names]
    hit = lambda a: any(cp.is_multi_color(a, s, args.degree, args.pos_tol) for _nm, s in prints)
    miss_own = [n for n in all_own if not hit(load(n))]
    fp_fail = [(l, n) for l, n, a in corpus() if group_of(l) != same and hit(a)]
    margin = max((cp.print_score(a, s, args.degree, args.pos_tol)
                  for l, n, a in corpus() if group_of(l) != same
                  for _nm, s in prints), default=0.0)
    print(f'\n复核: 本页全中 {len(all_own) - len(miss_own)}/{len(all_own)}   其他页误中 {len(fp_fail)}'
          f'   margin(其他页最高命中比例) {margin:.2f}')
    for n in miss_own:
        a = load(n)
        names, best = max(prints, key=lambda t: cp.print_score(a, t[1], args.degree, args.pos_tol))
        print(f'   未全中 {n}(最近形态 {names[0]}): '
              f'{cp.missing_points(a, best, args.degree, args.pos_tol)}')
    for l, n in fp_fail:
        print(f'   误中 {l}/{n}')
    print(f'\n# ---- 粘进 pages/{label}.py ----')
    if len(prints) == 1:
        print('    points = [')
        print(cp.fmt(prints[0][1]))
        print('    ]')
    else:
        print('    prints = (')
        for names, sel in prints:
            print(f'        (   # 形态: {"/".join(names[:3])}{"..." if len(names) > 3 else ""}')
            print(cp.fmt(sel, indent='            '))
            print('        ),')
        print('    )')
    return 0 if not miss_own and not fp_fail else 2


# ---------------------------------------------------------------- verify
def cmd_verify(args):
    from pages import ALL_PAGES
    from pages.base import match_print
    data = corpus()
    names = [p.name for p in ALL_PAGES]
    print('匹配优先级(注册顺序):', ' > '.join(names))
    print('\n' + 'image'.ljust(20) + 'label'.ljust(12) + 'winner'.ljust(13) + 'src'.ljust(13)
          + ' '.join(n[:6].rjust(6) for n in names))
    ok = bad = unmatched = 0
    fails = []
    for lbl, n, arr in data:
        scores = {p.name: p.print_score(arr) for p in ALL_PAGES}
        page, score, src = match_print(ALL_PAGES, arr)
        got = page.name if page else None
        line = n.replace('shots/', '').ljust(20) + lbl.ljust(12) + (got or '-').ljust(13) \
            + (src or '-').ljust(13) + ' '.join(
                ('  HIT ' if scores[p.name] >= 1.0 else f'{scores[p.name]:6.2f}')
                for p in ALL_PAGES)
        want = group_of(lbl)
        good = (got == want) or (want == 'other' and got is None)
        if got is None:
            unmatched += 1
        if good:
            ok += 1
            if args.verbose:
                print(line)
        else:
            bad += 1
            fails.append((n, lbl, got, page))
            print('!! ' + line)
    print(f'\n点色指纹判定: 通过 {ok} / 不通过 {bad} / 共 {len(data)}'
          f'   (未全中 -> 交 OCR 兜底 {unmatched})')
    for n, lbl, got, page in fails:
        if page is not None:
            for fp in page.fingerprints():
                miss = cp.missing_points(load(n), fp, page.degree, page.pos_tol)
                if miss and len(miss) < len(fp):
                    print(f'   {n}: {page.name} 差 {len(miss)} 点 -> {miss}')
    return 0 if bad == 0 else 2


def main():
    ap = argparse.ArgumentParser(description='点色指纹标定/校验')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('check')
    p = sub.add_parser('pick')
    p.add_argument('--label', required=True, choices=list(LABELS))
    p.add_argument('-n', type=int, default=5, help='每个形态的指纹单元上限')
    p.add_argument('--min-cross', dest='min_cross', type=int, default=3, help='至少几个单元')
    p.add_argument('--region', help='x0,y0,x1,y1 (默认全图留边)')
    p.add_argument('--step', type=int, default=4, help='候选网格步长')
    p.add_argument('--margin', type=int, default=8)
    p.add_argument('--cluster', type=float, default=4.0, help='同页分形态的像素差阈值')
    p.add_argument('--degree', type=float, default=85, help='匹配相似度')
    p.add_argument('--pos-tol', dest='pos_tol', type=int, default=1)
    p.add_argument('--min-sep', dest='min_sep', type=int, default=45, help='单元间最小距离')
    p.add_argument('--min-frames', dest='min_frames', type=float, default=1.0,
                   help='单元在本形态多少比例的帧里稳定(默认 1.0=全部)')
    p.add_argument('--drop-lonely', dest='drop_lonely', action='store_true',
                   help='孤立帧不参与选指纹(旧行为)')
    p.add_argument('--no-cross', dest='cross', action='store_false', help='单点式(mxdzz 原味)')
    p.set_defaults(cross=True)
    v = sub.add_parser('verify')
    v.add_argument('-v', '--verbose', action='store_true')
    a = ap.parse_args()
    return {'check': cmd_check, 'pick': cmd_pick, 'verify': cmd_verify}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())