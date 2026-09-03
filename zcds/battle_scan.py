# -*- coding: utf-8 -*-
"""战斗格子纯颜色扫描 (numpy/cv2, 无 OCR, 每次 ~10-20ms)

规则(用户确认):
  - 价格标签: 白色=钱够可点, 红色=钱不够不能点
  - 图标: 白色多面矿石(黑棱线切成几块) = 矿; 头盔 = 兵营; 钩+点 = 问号
返回 [{x, y, w, h, white, mine, icon, clip, cls}]
  cls: 25 / 50 / 100 / 250 / 3(认不出的三位数) / 'red'(钱不够); 认不出是价格的块直接丢弃
  clip: True = 贴着渲染边界(截图右侧黑边), 末位被裁, 价签靠左边缘断档识别
  icon: ore(矿) / barracks(兵营) / unknown(问号) / None (标签正上方 32x24 窗口的白块几何)
"""
import numpy as np

# ---- 价格识别: 竖直投影切位 + 逐位闭合孔数签名 (真机 2026-09-03 重写) ----
# 坑(用户观察"战斗中只开 25 的, 开完就不开"): 旧 _classify_word 把整块字缩到 30x18,
#     和 battle_templates.npz 的 t25/t50 做归一化相关, 阈值 0.32/0.04 太松 ->
#     真机日志里绝大多数格子落进"分不清"的 2d 桶, rank_cell 的"50 优先"从未生效。
# 判据: 这个字体里只有 0 带一个闭合孔, 1/2/5 都没有 -> "位数 + 各位孔数"唯一确定价格:
#     (0,0)=25 / (0,1)=50 / (0,1,1)=100 / (0,0,1)=250
#     318 帧战斗语料 1488 个白色标签实测 614/535/205/65 个, 四簇零混叠, 裁图肉眼核对。
# 顺带修掉一个幽灵格 bug: 兵营的白色头盔图标宽高都落在旧的 is_tag 区间里, 旧版把它当成
#     价格标签(实测 105 个, 签名都是 1 段) -> 同一个六边形格被图标和价格各算一次。
PRICE_SIGNS = {(0, 0): 25, (0, 1): 50, (0, 1, 1): 100, (0, 0, 1): 250}
# 250 档在 shots/battle_live014252.png 里肉眼确认(全红标签, 钱不够); 其余三位数落 cls=3


def _digit_holes(m):
    """单个数字块(0/1) -> 闭合孔数: 背景连通块里不接触自身外接框边界的那些"""
    import cv2
    inv = (1 - m.astype(np.uint8)).astype(np.uint8)
    # connectivity 必须写关键字: connectedComponents(image, 4) 里的 4 会被当成 labels
    # 参数吞掉, 实际按 8 邻域跑 -> 1px 笔画的字四角漏气, 孔数恒为 0
    n, lab = cv2.connectedComponents(inv, connectivity=4)[:2]
    if n <= 1:
        return 0
    border = set(np.unique(lab[0, :])) | set(np.unique(lab[-1, :])) | \
             set(np.unique(lab[:, 0])) | set(np.unique(lab[:, -1]))
    return sum(1 for i in range(1, n)
               if i not in border and int((lab == i).sum()) >= 2)


def _runs(profile, lo=1):
    """一维 0/1 轮廓 -> [(起, 止)] 连续非零段"""
    out, s = [], None
    for x, v in enumerate(profile):
        if v >= lo and s is None:
            s = x
        elif v < lo and s is not None:
            out.append((s, x)); s = None
    if s is not None:
        out.append((s, len(profile)))
    return out


def _left_edge_gap(sub, k=2):
    """数字块左起 k 列的填充行号里最大的断档(>=2 行算断)"""
    rows = np.where(sub[:, :k].any(axis=1))[0]
    if len(rows) < 2:
        return 99
    return int(np.max(np.diff(rows)))


def _price_class(mask, clipped=False):
    """白色价格标签块 -> 25 / 50 / 100 / 250 / 3(三位数认不出) / None(不是价格, 丢弃)

    先在行轮廓上取"最宽的那条横带"(价格数字自成一带, 上方 ? 问号的白点会被切掉),
    再按列轮廓切成单字, 逐位数闭合孔 -> 查签名表。
    clipped=True 时末位被渲染边界裁断, 孔数不可信, 改用末位左边缘的连续性分 0/5。
    """
    m = mask.astype(np.uint8) if mask.dtype != np.uint8 else mask
    if m.ndim > 2:
        m = (m > 0).astype(np.uint8)
    m = (m > 0).astype(np.uint8)
    if m.size == 0 or m.shape[0] < 8:
        return None
    bands = [(a, b) for a, b in _runs(m.sum(axis=1)) if b - a >= 8]
    if not bands:
        return None
    a, b = max(bands, key=lambda r: int(m[r[0]:r[1]].sum()))
    band = m[a:b]
    segs = [(x0, x1) for x0, x1 in _runs(band.sum(axis=0)) if x1 - x0 >= 3]
    if not (2 <= len(segs) <= 3):
        return None
    sig = []
    for x0, x1 in segs:
        sub = band[:, x0:x1]
        ys = np.where(sub.any(axis=1))[0]
        if len(ys) < 6:
            return None
        sig.append(_digit_holes(sub[ys.min():ys.max() + 1]))
    if clipped and sig == [0, 0]:
        # 末位被裁断了闭合孔 -> "50" 和 "25" 的孔签名都是 (0,0), 查表会一律得到 25.
        # 用末位左边缘断档分: 0 左边是完整竖弧(不断), 5 左边只有上半截+最底一行(断 ~4 行)
        x0, x1 = segs[-1]
        sub = band[:, x0:x1]
        ys = np.where(sub.any(axis=1))[0]
        sub = sub[ys.min():ys.max() + 1]
        return 25 if _left_edge_gap(sub) >= 3 else 50
    v = PRICE_SIGNS.get(tuple(sig))
    if v is not None:
        return v
    return 3 if len(segs) == 3 else None


def scan_words(mask, y0, content=None):
    """二值掩膜(白色价格字 / 红色价格字通用) -> 标签词 [{x,y,w,h,cls,n,clip}] (y 已加回 y0)

    content=(左,右) 是画面里"游戏内容"的实际左右列(截图右侧有黑边), 贴边的词末位被裁。

    为什么不用旧的 comps() 链式合并: 那套合并条件不看竖直重叠, 只和"上一块"比 ->
    链式吸收, 把 ? 问号点/图标/数字串成一块(实测头盔 area 145->233, 数字块高 11->20),
    _price_class 要求 2~3 段就被搅乱 -> 74 帧里 21 帧零标签。
    改成"数字尺寸筛块 + 两两链接": 只有 竖错位<=3 且 竖直边差<=4 且 水平间隙 0~5px 的
    相邻数字才并成一词, 不做任何全局行聚类, 词内 2~3 字, 词宽<=40 词高<=20。
    """
    import cv2
    n, lab, stats, _cents = cv2.connectedComponentsWithStats(mask, 8)
    d = []
    for i in range(1, n):
        x, y, ww, hh, area = stats[i]
        if 4 <= ww <= 16 and 8 <= hh <= 18 and area >= 18:
            d.append([int(x), int(y) + y0, int(ww), int(hh), int(area)])
    d.sort(key=lambda c: (c[0] + c[2] / 2.0))
    par = list(range(len(d)))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i

    for i in range(len(d)):
        for j in range(i + 1, len(d)):
            gap = d[j][0] - (d[i][0] + d[i][2])
            if gap > 5:
                break
            if gap >= 0 and abs(d[i][1] - d[j][1]) <= 3 and abs(d[i][3] - d[j][3]) <= 4:
                a, b = find(i), find(j)
                if a != b:
                    par[a] = b
    grp = {}
    for i in range(len(d)):
        grp.setdefault(find(i), []).append(d[i])
    out = []
    for g in grp.values():
        if not (2 <= len(g) <= 3):
            continue
        x0 = min(c[0] for c in g)
        x1 = max(c[0] + c[2] for c in g)
        yb = min(c[1] for c in g)
        ye = max(c[1] + c[3] for c in g)
        if x1 - x0 > 40 or ye - yb > 20:
            continue
        clip = content is not None and (x0 <= content[0] + 1 or x1 >= content[1] - 1)
        v = _price_class(mask[yb - y0:ye - y0, x0:x1], clipped=clip)
        if v is not None:
            out.append(dict(x=x0, y=yb, w=x1 - x0, h=ye - yb, cls=v, n=len(g),
                            clip=clip))
    out.sort(key=lambda t: (t['y'], t['x']))
    return out


def icon_kind(win):
    """标签上方 32x24 白色掩膜窗口 -> 'ore'(矿) / 'barracks'(兵营头盔) / 'unknown'(问号) / None

    2026-09-03 全语料实测, 只看"最大白块"的高宽 + 块数, 三档零重叠:
        矿   = 白色多面矿石, 被黑色棱线切成 3 块 -> 最大块 h=10~11 w=11~13, 块数>=2
        头盔 = 一整块 17x16 的白色斯巴达头盔     -> 最大块 h=15~16 w>=15
        问号 = 钩 + 点两块                       -> 最大块 h=13~14 w=12~13
    旧 _is_rock 数"竖缝"的写法实测对头盔/问号恒给 True(235/240), 完全分不开, 已废弃。
    """
    import cv2
    if win is None or win.size == 0:
        return None
    n, lab, stats, _cents = cv2.connectedComponentsWithStats(win, 8)
    big = [stats[k] for k in range(1, n) if stats[k][4] >= 12]
    if not big:
        return None
    mx = max(big, key=lambda c: c[4])
    mh, mw = int(mx[3]), int(mx[2])
    if mh <= 12 and len(big) >= 2 and int(sum(c[4] for c in big)) >= 100:
        return 'ore'
    if mh >= 13 and mw >= 15:
        return 'barracks'
    return 'unknown'


def scan_battle_cells(img, board_frac=(0.46, 0.90)):
    """扫描战斗棋盘. 返回 [{x,y,w,h,white,mine,icon,clip,cls}] 按 y,x 排序. 纯 numpy/cv2."""
    if isinstance(img, np.ndarray):
        arr = img
    else:
        arr = np.asarray(img.convert('RGB'))
    h, w = arr.shape[:2]
    y0, y1 = int(board_frac[0] * h), int(board_frac[1] * h)
    board = arr[y0:y1]
    white = ((board[:, :, 0] > 205) & (board[:, :, 1] > 205) & (board[:, :, 2] > 205)).astype(np.uint8)
    red = ((board[:, :, 0] > 170) & (board[:, :, 1] < 95) & (board[:, :, 2] < 95)).astype(np.uint8)

    def icon_window(t):
        """标签正上方 32x24 窗口(按标签水平中心对齐), 返回 (白色掩膜, bbox) 或 None"""
        cx = t['x'] + t['w'] // 2
        wx0, wx1 = max(0, cx - 16), min(w, cx + 16)
        wy1 = t['y'] - 2
        wy0 = max(y0, wy1 - 24)
        if wy1 - wy0 < 16 or wx1 - wx0 < 16:
            return None
        return white[wy0 - y0:wy1 - y0, wx0:wx1], (wx0, wy0, wx1, wy1)

    # 截图 552 宽, 但游戏内容只画到 ~543(右边一条黑边). 贴着内容边界的标签末位数字被裁掉:
    # "50" 的 0 断了闭合孔 -> 孔签名 (0,0) -> 误判成 25(真机右边缘一列 4 格实际 50/50/50/25,
    # 全被读成 25)。_price_class 里改用"末位左边缘断档"把 0/5 分开; 三位数没法救 -> cls=3。
    bright = board.max(axis=2).max(axis=0)
    nz = np.where(bright > 40)[0]
    content = (int(nz[0]), int(nz[-1])) if nz.size else None
    wwords = scan_words(white, y0, content)
    rwords = scan_words(red, y0, content)

    out = []
    for t in wwords:
        # 同一格不会既白又红: 附近若有红标签, 这块白字是别的元素, 丢弃
        if any(abs(c['x'] + c['w'] // 2 - (t['x'] + t['w'] // 2)) < 20
               and abs(c['y'] + c['h'] // 2 - (t['y'] + t['h'] // 2)) < 16 for c in rwords):
            continue
        win = icon_window(t)
        kind = icon_kind(win[0]) if win else None
        out.append(dict(x=t['x'], y=t['y'], w=t['w'], h=t['h'], white=True,
                        mine=(kind == 'ore'), icon=kind, clip=t['clip'],
                        cls=t['cls']))
    for t in rwords:
        win = icon_window(t)
        out.append(dict(x=t['x'], y=t['y'], w=t['w'], h=t['h'], white=False,
                        mine=False, icon=icon_kind(win[0]) if win else None,
                        clip=t['clip'], cls='red'))
    out.sort(key=lambda t: (t['y'], t['x']))
    return out
