# -*- coding: utf-8 -*-
"""点色指纹库 —— 移植自 mxdzz/libs/app.py 的颜色对比部分, 适配本项目

与 mxdzz 的差异(刻意修正):
  1) 坐标顺序统一为 (x, y) —— mxdzz 的 points 实际是 numpy 的 [行, 列] 却命名为 (x, y),
     而 click_xy 又是 (x, y), 两套顺序混用极易标错。这里全库只用 (x=列, y=行)。
  2) 支持窗口缩放: 指纹按 REF_SIZE 标定, 匹配时按实际截图尺寸自动换算 + 坐标容差。
  3) 除"全中才算"(is_multi_color)外, 另给命中比例 print_score, 便于打分/排序/调试。

指纹约定:
  points = [(x, y, 0xRRGGBB), ...]   第一个点视为锚点(区域图案搜索以它为基准)
  degree = 颜色相似度百分比, 85 => 每通道容差 ±19
  pos_tol = 坐标容差(像素), 吸收窗口缩放取整/1px 抖动
"""
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np

# 标定基准: 占城大师微信小游戏窗口 PrintWindow 截图尺寸
REF_SIZE = (552, 1006)
DEFAULT_DEGREE = 85
DEFAULT_POS_TOL = 1

Point = Tuple[int, int, int]


# ---------------------------------------------------------------- 颜色换算
def c2rgb(c: int) -> List[int]:
    """0xRRGGBB -> [r, g, b]  (mxdzz: App.c2rgb)"""
    r = c // 0x10000
    g = c // 0x100 - r * 0x100
    b = c - r * 0x10000 - g * 0x100
    return [r, g, b]


def rgb2c(rgb: Sequence[int]) -> int:
    """[r, g, b] -> 0xRRGGBB  (mxdzz: App.rgb2c)"""
    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
    return r * 0x10000 + g * 0x100 + b


def tolerance(degree: float = DEFAULT_DEGREE) -> int:
    """相似度百分比 -> 每通道绝对容差  (mxdzz: same_color 里的 delta)"""
    return int((256 - 256 * degree // 100) // 2)


def to_arr(img) -> np.ndarray:
    """PIL.Image / np.ndarray -> HxWx3 uint8(RGB); 同一帧反复判色时缓存"""
    if isinstance(img, np.ndarray):
        a = img
        if a.ndim == 2:
            a = np.dstack([a] * 3)
        return a[:, :, :3] if a.shape[2] == 4 else a
    cached = getattr(img, "_cp_arr", None)
    if cached is not None:
        return cached
    src = img if img.mode == "RGB" else img.convert("RGB")
    arr = np.asarray(src, dtype=np.uint8)
    try:
        img._cp_arr = arr
    except Exception:
        pass
    return arr


def pixel_color(img, x: int, y: int) -> int:
    """取一点颜色(标定用)"""
    return rgb2c(to_arr(img)[y, x])


# ---------------------------------------------------------------- 缩放
def scale_points(points: Sequence[Point], size: Tuple[int, int],
                 ref=REF_SIZE) -> List[Point]:
    """把 REF_SIZE 下标定的指纹换算到实际截图尺寸 size=(w, h)"""
    w, h = size
    if (w, h) == tuple(ref):
        return [(int(x), int(y), c) for x, y, c in points]
    sx, sy = w / float(ref[0]), h / float(ref[1])
    return [(int(round(x * sx)), int(round(y * sy)), c) for x, y, c in points]


# ---------------------------------------------------------------- 单点/多点判色
def is_color(img, x: int, y: int, color: int,
             degree: float = DEFAULT_DEGREE, pos_tol: int = DEFAULT_POS_TOL) -> bool:
    """(x, y) 处颜色是否命中(允许 pos_tol 像素漂移)  (mxdzz: App.is_color)"""
    arr = to_arr(img)
    ref = np.array(c2rgb(color), dtype=np.int16)
    delta = tolerance(degree)
    y0, y1 = max(0, y - pos_tol), min(arr.shape[0], y + pos_tol + 1)
    x0, x1 = max(0, x - pos_tol), min(arr.shape[1], x + pos_tol + 1)
    if y0 >= y1 or x0 >= x1:
        return False
    patch = arr[y0:y1, x0:x1].astype(np.int16) - ref
    return bool((np.abs(patch) <= delta).all(axis=2).any())


def is_multi_color(img, points: Sequence[Point],
                   degree: float = DEFAULT_DEGREE,
                   pos_tol: int = DEFAULT_POS_TOL,
                   size=None) -> bool:
    """多点全中 => 命中该指纹  (mxdzz: App.is_multi_color)"""
    if not points:
        return False
    arr = to_arr(img)
    pts = scale_points(points, size or (arr.shape[1], arr.shape[0]))
    return all(is_color(arr, x, y, c, degree, pos_tol) for x, y, c in pts)


def print_score(img, points: Sequence[Point],
                degree: float = DEFAULT_DEGREE,
                pos_tol: int = DEFAULT_POS_TOL,
                size=None) -> float:
    """命中比例 0.0~1.0(全中即 1.0), 用于打分/排序/排错"""
    if not points:
        return 0.0
    arr = to_arr(img)
    pts = scale_points(points, size or (arr.shape[1], arr.shape[0]))
    hit = sum(1 for x, y, c in pts if is_color(arr, x, y, c, degree, pos_tol))
    return hit / len(pts)


def missing_points(img, points: Sequence[Point],
                   degree: float = DEFAULT_DEGREE,
                   pos_tol: int = DEFAULT_POS_TOL) -> List[Point]:
    """标定/排错用: 返回这帧里没命中的点"""
    arr = to_arr(img)
    return [(x, y, c) for x, y, c in scale_points(points, (arr.shape[1], arr.shape[0]))
            if not is_color(arr, x, y, c, degree, pos_tol)]


# ---------------------------------------------------------------- 区域图案搜索
def _shift_map(org: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """out[i, j] = org[i + dy, j + dx], 越界补 0  (mxdzz: reshape_same_size)"""
    tmp = org[max(0, dy):None if dy >= 0 else dy, max(0, dx):None if dx >= 0 else dx]
    return np.pad(tmp, ((max(-dy, 0), max(dy, 0)), (max(-dx, 0), max(dx, 0))))


def find_multi_color(img, points, degree=DEFAULT_DEGREE, region=None,
                     max_count: int = 0) -> List[List[int]]:
    """在 region 内搜索"整组相对色块"出现的位置(颜色图案搜索, 无需模板图)

    mxdzz: App.find_multi_color_in_region —— 按颜色组合找按钮/图标。
    points[0] 为锚点; 返回 [[y, x], ...](numpy 行优先), 要 (x, y) 用 find_multi_color_xy。
    """
    if not points:
        return []
    arr = to_arr(img)
    pts = scale_points(points, (arr.shape[1], arr.shape[0]))
    if region is None:
        ox, oy = 0, 0
        sub = arr
    else:
        rx0, ry0, rx1, ry1 = region
        ox, oy = rx0, ry0
        sub = arr[ry0:ry1, rx0:rx1]
    delta = tolerance(degree)
    ax, ay, _ = pts[0]
    acc = None
    for x, y, color in pts:
        diff = sub.astype(np.int16) - np.array(c2rgb(color), dtype=np.int16)
        hit = (np.abs(diff) <= delta).all(axis=2)
        shifted = _shift_map(hit, y - ay, x - ax)
        acc = shifted if acc is None else (acc & shifted)
    ys, xs = np.where(acc)
    out = [[int(y) + oy, int(x) + ox] for y, x in zip(ys, xs)]
    return out[:max_count] if max_count else out


def find_multi_color_xy(img, points, degree=DEFAULT_DEGREE, region=None,
                        max_count: int = 0) -> List[Tuple[int, int]]:
    """同上, 直接返回 (x, y) 列表, 方便 ctx.click(*pt)"""
    return [(x, y) for y, x in find_multi_color(img, points, degree, region, max_count)]


def clean_coordinates(coord_list: Iterable[Sequence[int]],
                      distance_limit: int = 10) -> List[List[int]]:
    """相邻命中点去重  (mxdzz: App.clean_coordinates)"""
    cleaned: List[List[int]] = []
    for coord in coord_list:
        if all((c[0] - coord[0]) ** 2 + (c[1] - coord[1]) ** 2 >= distance_limit ** 2
               for c in cleaned):
            cleaned.append(list(coord))
    return cleaned


# ---------------------------------------------------------------- 指纹自动生成
def sample_points(img, region: Sequence[int], n: int = 6, seed=None,
                  anchor_first: bool = True) -> List[Point]:
    """从区域随机采样 n 个点生成指纹  (mxdzz: App.get_points)

    region = (x0, y0, x1, y1); 默认首点为区域左上角(锚点), 其余随机。
    """
    arr = to_arr(img)
    x0, y0, x1, y1 = region
    x1, y1 = min(x1, arr.shape[1]), min(y1, arr.shape[0])
    w, h = x1 - x0, y1 - y0
    rng = np.random.default_rng(seed)
    idx = rng.choice(w * h, size=min(n, w * h), replace=False) if w > 0 and h > 0 else []
    pts: List[Point] = []
    if anchor_first:
        pts.append((x0, y0, rgb2c(arr[y0, x0])))
    for i in idx:
        x, y = int(i) % w + x0, int(i) // w + y0
        pts.append((x, y, rgb2c(arr[y, x])))
    return pts


def stable_points(imgs: Sequence, region: Sequence[int], step: int = 3,
                  degree: float = 96) -> List[Point]:
    """在多张同页截图里颜色始终一致的候选点(滤掉动画/倒计时/随机内容)"""
    arrs = [to_arr(im) for im in imgs]
    x0, y0, x1, y1 = region
    delta = tolerance(degree)
    base = arrs[0]
    out: List[Point] = []
    for y in range(max(0, y0), min(y1, base.shape[0]), step):
        for x in range(max(0, x0), min(x1, base.shape[1]), step):
            ref = base[y, x].astype(np.int16)
            ok = True
            for a in arrs[1:]:
                if a.shape[0] <= y or a.shape[1] <= x:
                    ok = False
                    break
                if (np.abs(a[y, x].astype(np.int16) - ref) > delta).any():
                    ok = False
                    break
            if ok:
                out.append((x, y, rgb2c(base[y, x])))
    return out


def fmt(points: Sequence[Point], per_line: int = 3, indent: str = "        ") -> str:
    """把指纹打印成可直接粘进 pages/*.py 的 Python 字面量(每行都带 indent)"""
    items = ["[%d, %d, 0x%06X]," % (x, y, c) for x, y, c in points]
    return "\n".join(indent + " ".join(items[i:i + per_line])
                     for i in range(0, len(items), per_line))


# ---------------------------------------------------------------- 批量判色(标定用)
def stack(imgs: Sequence) -> np.ndarray:
    """多帧 -> (N, H, W, 3) uint8"""
    return np.stack([to_arr(im) for im in imgs])


def color_match(imgs, pts, colors, degree: float = DEFAULT_DEGREE,
                pos_tol: int = 0) -> np.ndarray:
    """批量判色: (帧数, 点数) bool 矩阵 —— 第 i 帧第 j 点是否命中 colors[j]

    pos_tol>0 时与 is_color 一致: (2t+1)^2 邻域内任一像素命中即算命中。
    要求所有帧同尺寸(标定语料统一 REF_SIZE)。
    """
    st = imgs if (isinstance(imgs, np.ndarray) and imgs.ndim == 4) else stack(imgs)
    ys = np.fromiter((y for _x, y in pts), dtype=np.intp, count=len(pts))
    xs = np.fromiter((x for x, _y in pts), dtype=np.intp, count=len(pts))
    ref = np.asarray(list(colors), dtype=np.int16)[None, :, :]      # (1, M, 3)
    delta = tolerance(degree)
    h, w = st.shape[1], st.shape[2]
    acc = None
    for dy in range(-pos_tol, pos_tol + 1):
        for dx in range(-pos_tol, pos_tol + 1):
            got = st[:, np.clip(ys + dy, 0, h - 1), np.clip(xs + dx, 0, w - 1)].astype(np.int16)
            m = (np.abs(got - ref) <= delta).all(axis=2)
            acc = m if acc is None else (acc | m)
    return acc


def grid_points(region: Sequence[int], step: int = 4) -> List[Tuple[int, int]]:
    """区域网格采样点 (x, y)"""
    x0, y0, x1, y1 = region
    return [(x, y) for y in range(y0, y1, step) for x in range(x0, x1, step)]