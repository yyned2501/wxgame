# -*- coding: utf-8 -*-
"""战斗格子纯颜色扫描 (numpy/cv2, 无 OCR, 每次 ~10-20ms)

规则(用户确认):
  - 价格标签: 白色=钱够可点, 红色=钱不够不能点
  - 图标: 白色团块中有 2-3 条竖直缝隙 = 矿(加钱) -> mine=True
  - 兵营 = 怪物头像(非白色), 问号 = 白 '?' 形状
返回 [{x, y, w, h, white, mine, cls}]
  cls: '50'/'25'/'2d'(二位数字相近) / '3d'(三位数) / 'red'
"""
import os
import numpy as np

_ROOT = os.path.dirname(os.path.abspath(__file__))
_TEMPLATES = None


def _load_templates():
    global _TEMPLATES
    if _TEMPLATES is None:
        _TEMPLATES = np.load(os.path.join(_ROOT, 'battle_templates.npz'))
    return _TEMPLATES


def _norm_glyph(m, tw=30, th=18):
    from PIL import Image
    im = Image.fromarray((m * 255).astype(np.uint8)).resize((tw, th))
    g = np.asarray(im, dtype=np.float32) / 255.0
    g = g - g.mean()
    n = np.linalg.norm(g)
    return (g / n).astype(np.float32) if n > 0 else g


def _classify_word(mask):
    """白字二位价格: '50' / '25' / '2d'(分不清)"""
    D = _load_templates()
    t25, t50 = D['t25'], D['t50']
    g = _norm_glyph(mask.astype(np.float32))
    s25 = max(float((g * t).sum()) for t in t25)
    s50 = max(float((g * t).sum()) for t in t50)
    if s25 < 0.32 and s50 < 0.32:
        return '2d'
    if abs(s25 - s50) < 0.04:
        return '2d'
    return '50' if s50 > s25 else '25'


def _is_rock(mask):
    """白团中下部有 >=2 条竖直黑色缝隙 -> 石头矿"""
    ih, iw = mask.shape
    if ih < 9 or iw < 8:
        return False
    band = mask[int(ih * 0.40):int(ih * 0.85), :]
    if band.shape[0] < 2:
        return False
    col_white = (band > 0.5).sum(axis=0)
    th = max(1, band.shape[0] * 0.55)
    gaps, in_gap = 0, False
    for v in col_white < th:
        if v and not in_gap:
            gaps += 1
            in_gap = True
        elif not v:
            in_gap = False
    return gaps >= 2


def scan_battle_cells(img, board_frac=(0.46, 0.90)):
    """扫描战斗棋盘. 返回 [{x,y,w,h,white,mine,cls}] 按 y,x 排序. 纯 numpy/cv2."""
    import cv2
    if isinstance(img, np.ndarray):
        arr = img
    else:
        arr = np.asarray(img.convert('RGB'))
    h, w = arr.shape[:2]
    y0, y1 = int(board_frac[0] * h), int(board_frac[1] * h)
    board = arr[y0:y1]
    white = ((board[:, :, 0] > 205) & (board[:, :, 1] > 205) & (board[:, :, 2] > 205)).astype(np.uint8)
    red = ((board[:, :, 0] > 170) & (board[:, :, 1] < 95) & (board[:, :, 2] < 95)).astype(np.uint8)

    def comps(mask):
        n, lab, stats, cents = cv2.connectedComponentsWithStats(mask, 8)
        raw = []
        for i in range(1, n):
            x, y, ww, hh, area = stats[i]
            if area < 15 or ww > 60 or hh > 26:
                continue
            raw.append([int(x), int(y) + y0, int(ww), int(hh), int(area),
                        int(cents[i][0]), int(cents[i][1]) + y0])
        raw.sort(key=lambda c: (c[1], c[0]))
        merged = []
        for c in raw:
            if merged and abs(c[6] - merged[-1][6]) < 12 and c[0] - merged[-1][0] < 40 \
                    and c[0] + c[2] - merged[-1][0] < 60:
                t = merged[-1]
                x2 = max(t[0] + t[2], c[0] + c[2])
                y2 = max(t[1] + t[3], c[1] + c[3])
                t[2], t[3], t[4] = x2 - t[0], y2 - t[1], t[4] + c[4]
                continue
            merged.append(list(c))
        return merged

    wcomps = comps(white)
    rcomps = comps(red)

    def is_tag(c):
        return 64 <= c[0] <= w - 64 and 16 <= c[2] <= 52 and 9 <= c[3] <= 22

    wtags = [i for i, c in enumerate(wcomps) if is_tag(c)]
    rtags = [i for i, c in enumerate(rcomps) if is_tag(c)]

    def find_icon(tag_y, tag_cx):
        """找标签上方最大的白色图标, 返回 (wcomps下标, 图标bbox) 或 None"""
        best = None
        for j, ic in enumerate(wcomps):
            if not (6 <= ic[2] <= 26 and 6 <= ic[3] <= 22):
                continue
            gap = tag_y - (ic[1] + ic[3])
            if 2 <= gap <= 20 and abs(ic[0] + ic[2] // 2 - tag_cx) < 15:
                if best is None or ic[4] > best[1][4]:
                    best = (j, ic)
        return best

    # 1) 白标签: 认领图标 + 石矿判定; 红标签: 认领图标(避免幽灵白标签)
    consumed = set()
    for i in wtags:
        c = wcomps[i]
        hit = find_icon(c[1], c[0] + c[2] // 2)
        if hit is None:
            wcomps[i].append(False)
            continue
        j, ic = hit
        consumed.add(j)
        ix, iy, iw, ih = ic[:4]
        m = white[iy - y0:iy + ih - y0, ix:ix + iw].astype(np.float32)
        wcomps[i].append(_is_rock(m))
    for i in rtags:
        c = rcomps[i]
        hit = find_icon(c[1], c[0] + c[2] // 2)
        if hit is not None:
            consumed.add(hit[0])

    out = []
    for i in wtags:
        if i in consumed:
            continue
        c = wcomps[i]
        x, y, ww, hh = c[:4]
        cls = '3d' if ww >= 33 else _classify_word(
            white[y - y0:y + hh - y0, x:x + ww].astype(np.float32))
        out.append(dict(x=x, y=y, w=ww, h=hh, white=True, mine=bool(c[7]), cls=cls))
    for i in rtags:
        c = rcomps[i]
        out.append(dict(x=c[0], y=c[1], w=c[2], h=c[3], white=False, mine=False, cls='red'))
    out.sort(key=lambda t: (t['y'], t['x']))
    return out
