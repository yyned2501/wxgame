# -*- coding: utf-8 -*-
"""锚点相对点色(anchor_prints)回归 —— 弹窗面板会浮动, 绝对坐标指纹压不住

用户定案: 识别一律用点色, OCR 又慢又不准。奖励弹窗(月卡/特权/礼包)的面板位置**随内容浮动**:
实测同一个弹窗的关闭徽章在 (455,461) 和 (459,545) 两种高度, 写死的 prints 只对第一 kinds 有效,
剩下的帧只能每帧跑一次全图 OCR(675ms)才认出弹窗 —— 这就是 test_zero_ocr 里那条 BAD。
现在: 绝对指纹没全中 -> find_close_badge() 用颜色现量锚点 -> 按偏移(anchor_prints)再试一轮。
锁死五件事:
  1) 弹窗语料 12 帧全部点色定页, 其中原先要靠 OCR 的那帧现在 src='anchor'
  2) 锚点组平移不变: 把"徽章 + 左边金币排"整块搬到别处, 仍然认成 vip_popup
  3) 异页 0 误中: 全语料 + 真机帧里凡是靠 anchor 定页的, 页面身份必须是 vip_popup
  4) 锚点组只有 5 个点 < SOFT_MIN_PTS(8) -> 差 1 个点不许软命中, 老实交回 OCR 兜底
  5) find_close_badge 对 PIL 截图和语料 ndarray 给同一个答案(主循环吃 PIL, 回归吃 ndarray)

用法(游戏目录): python -X utf8 test_anchor_print.py      # 退出码 0 = 全通过
"""
import glob
import os
import re
import sys
import time

import numpy as np
import PIL.Image as I

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import colorprint as cp
import pick_print as pp
from colorprint import REF_SIZE
from pages import ALL_PAGES
from pages.base import (SOFT_MIN_PTS, anchor_points, find_close_badge,
                        route_prints)
from colorprint import print_score

VIP = [p for p in ALL_PAGES if p.name == 'vip_popup'][0]
FAILS = []


def chk(cond, msg):
    print('  %-4s %s' % ('ok' if cond else 'FAIL', msg))
    if not cond:
        FAILS.append(msg)


def arr_of(path):
    im = I.open(path).convert('RGB')
    if im.size != REF_SIZE:
        im = im.resize(REF_SIZE)
    return cp.to_arr(im)


def anchor_best(arr):
    """本页锚点组的最高命中比例(不看绝对指纹, 专门给误中检查用)"""
    b = find_close_badge(arr)
    if b is None:
        return 0.0
    return max([print_score(arr, anchor_points(fp, b), VIP.degree, VIP.pos_tol,
                           size=REF_SIZE) for fp in VIP.anchor_fingerprints()] or [0.0])


def by_name(name):
    p = pp.img_path(name)
    assert p, name
    return arr_of(p)


def badge_frame(arr, dst=(300, 300)):
    """裁下"关闭徽章 + 左边那排金币", 平移到 dst 处贴到纯色背景上 -> 新帧"""
    bx, by = find_close_badge(arr)
    x0, x1, y0, y1 = bx - 130, bx + 30, by - 45, by + 45
    patch = arr[y0:y1, x0:x1].copy()
    bg = np.empty(arr.shape, dtype=np.uint8)
    bg[...] = np.array([0x21, 0x33, 0x45], dtype=np.uint8)
    dx, dy = dst[0] - bx, dst[1] - by
    bg[y0 + dy:y1 + dy, x0 + dx:x1 + dx] = patch
    return bg


def corpus_rows():
    for lbl, names in sorted(pp.LABELS.items()):
        for n in names:
            p = pp.img_path(n)
            if p:
                yield pp.group_of(lbl), '语料', os.path.basename(p), arr_of(p)
    for p in sorted(glob.glob(os.path.join(ROOT, 'shots_live', 'dbg_*.png'))):
        m = re.match(r'dbg_\d+_(\w+?)_(\d+)\.png', os.path.basename(p))
        if m:
            yield pp.group_of(m.group(1)), '真机', os.path.basename(p), arr_of(p)


def main():
    # ---- 1) 弹窗语料全部点色定页, 原先漏的那帧现在靠锚点 ----
    print('[1] 弹窗帧点色定页')
    srcs = {}
    for lbl, names in pp.LABELS.items():
        g = pp.group_of(lbl)
        for n in names:
            if g != 'vip_popup':
                continue
            page, score, src = route_prints(ALL_PAGES, by_name(n))
            srcs[n] = (src, score)
            chk(page is not None and page.name == 'vip_popup',
                '%s -> %s %s %.2f' % (n, page and page.name, src, score))
    chk(sum(1 for s, _ in srcs.values() if s is None) == 0,
        '弹窗帧没有一张需要 OCR 兜底 (共 %d 张)' % len(srcs))
    names = [n for n, (s, _) in srcs.items() if s == 'anchor']
    chk(len(names) >= 1, '其中 %d 张是绝对指纹没全中、靠锚点救回的: %s' % (len(names), names))

    # ---- 2) 平移不变 ----
    print('[2] 锚点相对指纹平移不变')
    base = by_name('vip_popup_live105350')
    for dst in ((300, 300), (200, 700), (430, 240)):
        f = badge_frame(base, dst)
        chk(find_close_badge(f) == dst, '徽章搬到 %s 后仍被颜色找到' % (dst,))
        page, score, src = route_prints(ALL_PAGES, f)
        chk(page is VIP and src == 'anchor',
            '%s -> %s %s (纯色底 + 绝对坐标全不对, 只有锚点组能中)' % (dst, page and page.name, src))

    # ---- 3) 异页 0 误中 ----
    print('[3] 全语料 + 真机帧: anchor 只许命中 vip_popup')
    rows = list(corpus_rows())
    used, wrong = [], []
    for grp, kind, name, arr in rows:
        page, score, src = route_prints(ALL_PAGES, arr)
        if src == 'anchor':
            used.append(name)
            if grp != 'vip_popup':
                wrong.append((name, grp, page.name))
    chk(not wrong, '误中 %s' % (wrong,))
    chk(len(used) >= 1, '%d 帧靠 anchor 定页, 全部是弹窗帧' % len(used))
    # 只有"锚点组"参评(绝对指纹那是另一回事, ask_battle 本来就靠它定页)
    ask = by_name('ask_battle')
    chk(anchor_best(ask) < 1.0,
        '同为弹窗但左侧不是金币排的 ask_battle: 锚点组最高只中 %.2f' % anchor_best(ask))
    worst = 0.0
    wname = None
    for grp, kind, name, arr in rows:
        if grp == 'vip_popup' or not VIP.anchor_fingerprints():
            continue
        s = anchor_best(arr)
        if s > worst:
            worst, wname = s, name
    chk(worst < 1.0, '全部 %d 张异页帧锚点组最高只中 %.2f (%s)' % (len(rows), worst, wname))

    # ---- 4) 差 1 点不许软命中 ----
    print('[4] 锚点组不参与软命中(点数 < SOFT_MIN_PTS=%d)' % SOFT_MIN_PTS)
    f = badge_frame(base, (300, 300))
    chk(route_prints(ALL_PAGES, f)[2] == 'anchor', '动刀前先确认能全中')
    for dx, dy in ((-30, 0), (-60, -20)):
        g = f.copy()
        cx, cy = 300 + dx, 300 + dy
        g[cy - 3:cy + 4, cx - 3:cx + 4] = np.array([0x21, 0x33, 0x45], dtype=np.uint8)
        page, score, src = route_prints(ALL_PAGES, g)
        chk(src is None and page is not VIP,
            '抹掉偏移 (%d,%d) 那 1 个点 -> %s %s %.2f (按设计交 OCR)'
            % (dx, dy, page and page.name, src, score))
    chk(VIP.anchor_fingerprints()[0].__len__() < SOFT_MIN_PTS,
        '锚点组 %d 个点, 结构上就进不了软命中' % len(VIP.anchor_fingerprints()[0]))

    # ---- 5) PIL / ndarray 一致 + 耗时 ----
    print('[5] 锚点查找对 PIL 与 ndarray 一致, 且只在绝对指纹失败时才花钱')
    im = I.open(pp.img_path('vip_popup_live105350')).convert('RGB')
    chk(find_close_badge(im) == find_close_badge(cp.to_arr(im)),
        'find_close_badge 两种输入同一个答案')
    blank = np.zeros((REF_SIZE[1], REF_SIZE[0], 3), dtype=np.uint8)
    t0 = time.time()
    for _ in range(20):
        route_prints(ALL_PAGES, blank)
    ms = (time.time() - t0) * 1000 / 20
    chk(ms < 40.0, '绝对指纹全失败的一帧(含找锚点) %.1f ms << 全图 OCR 675 ms' % ms)

    print('')
    if FAILS:
        print('不通过 %d 项:' % len(FAILS))
        for m in FAILS:
            print('  - ' + m)
        return 1
    print('全部通过 (锚点相对点色: 弹窗浮动位置也零 OCR)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
