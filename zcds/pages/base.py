# -*- coding: utf-8 -*-
"""页面基类 + 路由(定页面只看点色; OCR 是最后兜底, 动作层读字另说)

四级路由(2026-09-03 定案: OCR 又慢又不准, 识别成功后一律用点色 —— 全表点色 2.2ms, 全图 OCR 675ms):
  1) 指纹全中      先查上一步声明的候选页(next_pages ~ mxdzz 的 link) -> src='print-prefer',
                   再按 ALL_PAGES 注册顺序(弹窗在前, unknown 在最后) -> src='print-order'
  2) 锚点相对指纹  绝对坐标全中失败(弹窗带入场动画/面板位置随内容浮动)时, 先用颜色
                   现量一个锚点(= 红底白叉关闭徽章), 按偏移再试一轮 -> src='print-anchor'
  3) 软命中        只差 <=1 个点且甩开第二名 >=0.20 -> src='print-*-soft';
                   仍然算点色定页, 依然不跑 OCR(主循环要求连续 2 帧同页才动手, 见 auto_bot)
  4) 全图 OCR      前三级一点收据都没有(新页面/被别的窗口挡住/改版)才花这份钱 -> src='ocr',
                   同分时再用点色部分命中率 tie-break, 再不行 unknown
门限常量与推导见本文件"软命中"一节 + COLORPRINT.md §6.1; 回归锁在
test_print_route.py[10] / test_zero_ocr.py / test_cpu_offline.py 场景7。
"""
import logging
import re

from colorprint import (DEFAULT_DEGREE, DEFAULT_POS_TOL, REF_SIZE, _clip_box,
                        color_bbox, color_count, color_mask, is_color, is_multi_color,
                        print_score, scale_points, to_arr)


def anchor_points(fp, anchor):
    """锚点相对点色 -> 绝对点色(锚点 = 本帧现量出来的 (x, y))"""
    ax, ay = anchor
    return [(ax + dx, ay + dy, c) for dx, dy, c in fp]


class Page:
    """所有页面的基类.

    子类需要实现/声明:
      name        页面名
      points      点色指纹 [(x, y, 0xRRGGBB), ...]  —— 页面身份的唯一判据
      prints      可选: 同页多形态的多组指纹(任一全中即算本页)
      anchor_prints 可选: 相对锚点的指纹组(锚点由页面自己用颜色现算)
      degree      颜色相似度(默认 85 => 每通道 ±19)
      pos_tol     坐标容差像素(默认 1, 吸收窗口缩放取整)
      next_pages     执行动作后可能跳转的页面名(= mxdzz 的 link)
      act_needs_ocr  本页动作层是否真的需要读文字(默认 True; 纯点色页设 False)
      act(ctx)       干本页的事, 返回是否执行了动作
      detect(f)      文字特征兜底分(动作层也常用它判断按钮/文案)

    点色优先: 定页面和点哪里一律先用颜色, OCR 又慢又不准。
    真机实测一轮: 点色全表 2.2ms / 全图 OCR 675ms / 本页 ROI OCR 369ms。
    所以 act_needs_ocr=False 的页面主循环干脆不跑 OCR, 只有指纹没全中、
    或动作层非读文字不可(价格护栏/按钮文案)时才花这份钱。
    """
    name = 'base'
    next_pages = ()
    detail = ''
    points = ()
    prints = ()
    anchor_prints = ()     # 坐标是相对锚点的 (dx, dy), 见 _prints()
    degree = DEFAULT_DEGREE
    pos_tol = DEFAULT_POS_TOL
    act_needs_ocr = True       # False=动作层纯点色, 主循环就别为本页跑 OCR

    @classmethod
    def fingerprints(cls):
        """本页的全部指纹组"""
        if cls.prints:
            return tuple(tuple(fp) for fp in cls.prints if fp)
        return (tuple(cls.points),) if cls.points else ()

    @classmethod
    def anchor_fingerprints(cls):
        """锚点相对指纹组(坐标 = 相对锚点的偏移)"""
        return tuple(tuple(fp) for fp in cls.anchor_prints if fp)

    # ---- 点色指纹 ----
    def print_score(self, img, anchor=None) -> float:
        """最佳指纹组的命中比例(0~1, 全中=1)"""
        best = 0.0
        for _n, pts, size in self._prints(anchor):
            s = print_score(img, pts, self.degree, self.pos_tol, size=size)
            if s > best:
                best = s
        return best

    def print_match(self, img, anchor=None) -> bool:
        """指纹是否全中(= 确认是当前页)"""
        return any(is_multi_color(img, pts, self.degree, self.pos_tol, size=size)
                   for _n, pts, size in self._prints(anchor))

    def _prints(self, anchor=None):
        """参评指纹 -> (点数, 绝对坐标点列, 换算目标尺寸)

        anchor_prints 的坐标是【锚点偏移】, 而锚点(find_close_badge)是在本帧实际
        像素上现量出来的, 再按 REF_SIZE 缩放一次就会错位 -> 传 size=REF_SIZE 原样用。
        """
        for fp in self.fingerprints():
            yield len(fp), fp, None
        if anchor is not None:
            for fp in self.anchor_fingerprints():
                yield len(fp), anchor_points(fp, anchor), REF_SIZE

    # ---- 兜底/动作 ----
    def detect(self, f) -> float:
        raise NotImplementedError

    def act(self, ctx) -> bool:
        raise NotImplementedError

    def __repr__(self):
        return f'<Page {self.name}>'


# ---- 软命中: 点色没全中但"只差一个点"时的放行门限 ------------------
# 坑(真机 2026-09-03 01:42 日志): 战斗页满屏都在动, 指纹里只要有一个点被动画遮住
#     就不算"全中" -> 旧版整轮回退到全图 OCR(675ms)+靠文字猜页, 又慢又不准。
# 规则(三条同时成立才算软命中, 少一条就老实退回 OCR 兜底):
#   1) 参评指纹至少 SOFT_MIN_PTS 个点 —— 否则"1 个点没中"也满足"差<=1 点", 白送给弹窗页
#   2) 最多缺 SOFT_MAX_MISS 个点(按该指纹自身点数换算成分数门限)
#   3) 甩开第二名至少 SOFT_MIN_MARGIN —— 防两张相似页在半途中转帧上互相冒充
SOFT_MIN_PTS = 8
SOFT_MAX_MISS = 1
SOFT_MIN_MARGIN = 0.20


def best_print(page, arr, anchor=None):
    """本页最强指纹 -> (命中比例, 该指纹点数); 没指纹的页返回 (0.0, 0)

    anchor 不为 None 时才把该页的锚点相对指纹一起参评。
    """
    best, bn = 0.0, 0
    for n, pts, size in page._prints(anchor):
        s = print_score(arr, pts, page.degree, page.pos_tol, size=size)
        if s > best:
            best, bn = s, n
    return best, bn


def soft_hit(scored):
    """从"没全中"的各页分数里挑软命中 -> (page|None, score, src)"""
    cand = [(s, n, p, src) for s, n, p, src in scored
            if n >= SOFT_MIN_PTS and s >= 1.0 - SOFT_MAX_MISS / n]
    if not cand:
        return None, 0.0, None
    cand.sort(key=lambda r: -r[0])
    s0, _n, p0, src = cand[0]
    runner = max([s for s, _n2, p2, _src in scored if p2 is not p0] + [0.0])
    return (p0, s0, src) if s0 - runner >= SOFT_MIN_MARGIN else (None, 0.0, None)


def match_print(pages, img, prefer=()):
    """点色指纹匹配. 返回 (page|None, score, src)
    src: 'prefer'/'order' = 绝对指纹全中; 'anchor' = 锚点相对指纹全中;
         None = 点色没收据, 才允许花 OCR 兜底
    """
    arr = to_arr(img)
    preferred = [p for p in pages if p.name in prefer]
    rest = [p for p in pages if p.name not in prefer]
    scored = []
    for group, src in ((preferred, 'prefer'), (rest, 'order')):
        for p in group:
            s, n = best_print(p, arr)
            if s >= 1.0:
                return p, s, src
            scored.append((s, n, p, src))
    # 绝对坐标没全中才找锚点: 只有声明了 anchor_prints 的页面才量一次关闭徽章(~20ms)
    anchor = find_close_badge(arr) if any(p.anchor_fingerprints() for p in pages) else None
    if anchor is not None:
        for p in pages:
            for fp in p.anchor_fingerprints():
                pts = anchor_points(fp, anchor)
                if print_score(arr, pts, p.degree, p.pos_tol, size=REF_SIZE) >= 1.0:
                    return p, 1.0, 'anchor'
    page, score, src = soft_hit(scored)
    if page is not None:
        return page, score, src + '-soft'
    return None, max([s for s, _n, _p, _src in scored] + [0.0]), None


def route_prints(pages, img, prefer=()):
    """纯点色定页(绝不碰 OCR). 返回 (page|None, score, src)

    主循环每轮先调它: 只有返回 None(全中和软命中都没有)才允许花 OCR 去兜底。
    """
    return match_print(pages, img, prefer)


def is_soft(src):
    """定页结果是否来自软命中"""
    return bool(src) and src.endswith('-soft')


def detect_ocr(pages, f, arr=None):
    """OCR 文字兜底: 按 detect 分数选页面.

    并列最高分时用"点色指纹部分命中率"做 tie-break: 常驻文案会串页
    (大厅右上角一直挂着"月卡", 和 vip_popup 的关键词一模一样),
    但页面专属色块不会. 没有指纹的页(弹窗类)自然得 0, 让位给有指纹的页.
    """
    scored = []
    for p in pages:
        try:
            s = p.detect(f)
        except Exception:
            logging.exception('页面 %s detect 异常', p.name)
            continue
        scored.append((p, s))
    if not scored:
        return pages[-1], 0.0
    best_score = max(s for _, s in scored)
    if best_score < 0.3:
        return pages[-1], 0.0
    tied = [p for p, s in scored if s >= best_score - 1e-9]
    if len(tied) > 1:
        if arr is None:
            arr = getattr(f, 'img', None)
        if arr is not None:
            tied.sort(key=lambda p: p.print_score(arr), reverse=True)
    return tied[0], best_score


def route(pages, f, prefer=()):
    """完整路由. 返回 (page, score, src)  src in {'print-prefer','print-order','ocr','unknown'}"""
    arr = to_arr(f.img) if getattr(f, 'img', None) is not None else None
    page, score, src = match_print(pages, f.img, prefer)
    if page is not None:
        return page, score, 'print-' + src
    ocr_page, ocr_score = detect_ocr(pages, f, arr)
    if ocr_page.name != pages[-1].name:
        return ocr_page, ocr_score, 'ocr'
    return ocr_page, 0.0, 'unknown'


def select_page(pages, f, prefer=()):
    """兼容旧调用: 只要页面对象"""
    return route(pages, f, prefer)[0]

# ---- 宝箱"真在倒计时"判据(真机 2026-09-02 23:35 定案; lobby 与 chest_info 共用) ----
# 坑: 卡片角标上的"5分/10分/20分"是**开箱所需时长**, 不是剩余倒计时, 拿它判冷却会把
#     所有"可以免费开始开箱"的槽位一律误判成忙, 而且解锁后角标"0时19分55秒"还会被
#     OCR 读成"1+$5"这种乱码 -> 旧版靠它判冷却两头都错。
# 真在倒计时的只有这两种形态(都是解锁之后才出现的):
#   角标 "0时19分55秒" / 加速按钮 "[AD] -30分钟"(点它就是看广告 -> 大厅 a 格刻意不点, 见 pages/lobby.py)
COUNTDOWN_RE = re.compile(r'\d+\s*时\s*\d+\s*分|\d+\s*分\s*\d+\s*秒|-\s*\d+\s*分')


def is_countdown(text):
    """text 里出现"真在倒计时"的形态 -> True; 光秃秃的"20分"(所需时长)不算"""
    return bool(COUNTDOWN_RE.search(text or ''))

# ---- 红底白叉"关闭"徽章定位(真机 2026-09-03 00:03 定案) ----
# 坑: 弹窗右上角的关闭键是**图形**, 不是文字 -> OCR 永远读不到它。
#     旧版 vip_popup 只找 'X'/'关闭' 关键字, 找不到就点遮罩, 而且每次都点同一个遮罩点,
#     真机 dry-run 复现: 月卡弹窗 8 轮全在重复点 (270,860), 弹窗根本关不掉。
# 判据: 红底 + 白叉的小方块, 颜色/尺寸极稳 —— 77 张语料 + 17 张真机帧里
#     只有"弹窗关闭键"这一种元素满足(0 误报), 且与手工标定的
#     chest_info.CLOSE_POS=(470,167) 只差 2px。实测单帧 7~11ms。
# 2026-09-04 真机第 28 轮血案(两道闸的尺寸都因此改过, 证据链写在下面):
#   游戏开屏弹出一张没标指纹的日常活动弹窗[秘境大冒险], 右上角红底白叉 X 实测
#   n=973 / 外接框 48x48 / 框内白像素 193 —— 其余判据全过, 只差 n 一条:
#   旧上限 950 把它卡在门外 -> 出口链(引导/徽章/页签/箭头)全空 -> 掉全图 OCR
#   -> 误判成 versus(它的 act 永远 return False) -> 每轮都在"白等一帧 + 烧 675ms OCR"
#   里原地转, 4 分钟零动作一条日志警报都没有。
#   但只抬上限不安全 —— 全语料 842 帧对账(scratch/scripts/badge_cands.py):
#   抬到 1200 新增 44 帧候选, 只有 13 帧是真 X, 其余 31 帧是 battle 页左上那坨红色装饰。
#   两簇在 n 上几乎挨着(真 X 973 vs battle 装饰 1071~1096), 真正的分界是**外接框边长**:
#   所有真徽章(chest_info/vip_popup/hero_level/这张弹窗)外接框恒为 48x36~48x48,
#   battle 那两坨是 60x60 / 72x60 / 60x72。边框按 cell=12 量化 -> 边长只可能是 12 的倍数,
#   所以 CLOSE_BOX_MAX 60 -> 54 就等于"只允许 <=48", 一刀切开且对既有命中零回归;
#   n 上限同时抬到 1010 收下这张真 X(973), battle 那几坨仍被两道闸各自挡住。
CLOSE_RED_MIN_PX = 550      # 红底像素数(实测真 X: 697~973)
CLOSE_RED_MAX_PX = 1010
CLOSE_BOX_MIN = 30          # 外接框边长(cell 的倍数; 真 X 在 cell=8 下恒为 32~48)
CLOSE_BOX_MAX = 54
CLOSE_WHITE_MIN = 60        # 框内白像素=那个叉(实测 142~193)
# 2026-09-04 第 30 轮加第三道闸 = **位置先验**: 关闭键永远在弹窗右上角。
#   全语料 882 帧重扫(scratch/scripts/badge_scan_all.py): find_close_badge 命中 123 帧,
#   其中 122 帧 cx >= 432(= 宽 552 - 120), 全是人眼核对过的真 X(chest_info 22 / vip 10 /
#   hero_level 5 / other 6 / 未标注真机帧 79); 唯一 cx < 432 的是 battle 页左上那坨红装饰
#   (shots_live/dbg_009_battle_035400 -> (156,347))。同日真机又新增一坨: 战斗中反复弹到
#   (31,459)/(32,460), 每场战斗白烧 2 轮(点色零命中 -> 出口链认出"徽章" -> 点空气 -> 回战斗)。
#   尺寸/像素数两道闸都拦不住它(n/框/白全在真 X 带内), 只有 x 坐标能分清 => 直接拒右半边之外的一切候选。
CLOSE_RIGHT_MARGIN = 120      # 真徽章 cx 实测 452~477, 留 20px 余量 -> 只接受 cx >= 宽-120
# 2026-09-04 第 31 轮: cell 12 -> 8 + 第四道闸"中心必是白叉"。
#   血案: 竞技场4礼包弹窗的真 X 在 (453,369), n=738/白=147/cx=453 全过,
#   但它和右边那一列红图标(新手礼包/基金/月卡)在 cell=12 的粗格网下**共边连通**,
#   合并成一坨 48x60 -> 被 CLOSE_BOX_MAX=54 拒掉 -> 出口链徽章找不到 -> 掉全图 OCR
#   -> unknown 0.00 -> 最后靠 [未知] 试探遮罩瞎点才脱身, 白烧 2 分钟。
#   4 邻域改造救不了(全语料 884 帧 8conn/4conn 命中数完全相同 122, changed 0),
#   因为那一列红图标本来就上下相挨, 不是斜角粘连 [scratch/tmp/nbr.py]。
#   真修法 = 把格子做细: cell=8 下 X 与右列图标断开, 实测 40x48(n=738/白=147) -> 过关。
#   但格子变细会把以前"被合并成超大框而误拒"的东西放进候选池, 所以需要一条**语义闸**:
#   关闭徽章是红底 + 居中的白叉, 叉的两笔在正中心交叉 => 中心 7x7 必是白。
#   全语料 cell=8 下过 n/框/位置 三道闸的候选共 127 个: 126 个是人眼核对过的真徽章
#   (中心 7x7 白像素 40~49, 红 0), 唯一 cw=0/cr=49 的那个是 battle 页右下的生气表情气泡
#   (469,258) —— 它在 cell=8 下变成 48x40, 前三道闸全拦不住, 只有中心白叉能分清。
#   真徽章中心实测 42~49, 取 30 留足余量 [scratch/tmp/cellprobe.py, cwx.py]。
CLOSE_CENTER_WHITE_MIN = 30   # 中心 7x7 白像素下限(真徽章 42~49; 表情气泡 0)


def find_close_badge(img, cell=8):
    """整帧找红底白叉关闭徽章 -> (x, y); 没有则 None. 多个候选取最靠右的(关闭键都在右上)"""
    import numpy as np
    a = to_arr(img).astype(np.int16)   # PIL 截图和语料 ndarray 都要能吃
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    red = (r > 185) & (g < 105) & (b < 105) & ((r - np.maximum(g, b)) > 90)
    white = (r > 200) & (g > 200) & (b > 200)
    h, w = red.shape
    gh, gw = h // cell, w // cell
    grid = red[:gh * cell, :gw * cell].reshape(gh, cell, gw, cell).sum(axis=(1, 3))
    seen = np.zeros((gh, gw), dtype=bool)
    cands = []
    for i in range(gh):
        for j in range(gw):
            if not grid[i, j] or seen[i, j]:
                continue
            stack, cells = [(i, j)], []
            seen[i, j] = True
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < gh and 0 <= nx < gw and grid[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
            ys = [c[0] for c in cells]
            xs = [c[1] for c in cells]
            y0, y1 = min(ys) * cell, (max(ys) + 1) * cell
            x0, x1 = min(xs) * cell, (max(xs) + 1) * cell
            sub = red[y0:y1, x0:x1]
            n = int(sub.sum())
            if not CLOSE_RED_MIN_PX <= n <= CLOSE_RED_MAX_PX:
                continue
            if not (CLOSE_BOX_MIN <= x1 - x0 <= CLOSE_BOX_MAX
                    and CLOSE_BOX_MIN <= y1 - y0 <= CLOSE_BOX_MAX):
                continue
            pts = np.argwhere(sub)
            cy = int(pts[:, 0].mean()) + y0
            cx = int(pts[:, 1].mean()) + x0
            if cx < w - CLOSE_RIGHT_MARGIN:
                continue        # 左半边/中间的红块 = 页面装饰, 不是关闭键
            hw, hh = (x1 - x0) // 2, (y1 - y0) // 2
            if int(white[cy - hh:cy + hh + 2, cx - hw:cx + hw + 2].sum()) < CLOSE_WHITE_MIN:
                continue
            # 第四道闸: 中心 7x7 必须是白叉交点(表情/装饰是红心, 见上面第 31 轮注释)
            if int(white[cy - 3:cy + 4, cx - 3:cx + 4].sum()) < CLOSE_CENTER_WHITE_MIN:
                continue
            cands.append((cx, cy))
    if not cands:
        return None
    return max(cands)

# ---- 动作层点色工具(2026-09-03 定案: 点哪里也优先看颜色) ----------------
# 铁律: 页面身份由指纹确认之后, 动作层就不要再依赖 OCR 文字。
# 用法: 在标定截图上量出按钮的绝对像素框(窗口已钉死成 REF_SIZE), 数框内目标色像素。
# degree 用 90(每通道 ±13)而不是指纹的 85: 按钮是高饱和纯色, 收紧容差才能把
# "有按钮"和"按钮上面的白字/旁边同款色装饰"分清(实测阈值见各页常量注释)。
BTN_DEGREE = 90


def color_pixels(img, box, color, degree=BTN_DEGREE):
    """box 内某色像素个数(0 = 该色块不在这里)"""
    return color_count(img, box, color, degree)


def color_button(img, box, color, min_px=1, degree=BTN_DEGREE):
    """box 内找一块足够大的目标色色块 -> (x, y) 点击点; 没找到返回 None"""
    r = color_bbox(img, box, color, degree, min_px)
    return None if r is None else (r[0], r[1])


# ---- 侧页"返回箭头"判据(真机 2026-09-03 00:22 定案 / 08:36 修死循环) ----
# 坑1: 任务/商店/英雄这类侧页左下角有个青色返回箭头, 页面本身没进指纹表 -> 判成 unknown,
#      而 unknown 只会瞎点遮罩, 挂机就此卡死(用户手动停在任务页时必现)。
# 坑2(真机 08:36 死循环 3 分钟): 竞技场晋级页的箭头在 y=930..968, 任务页在 y=934..972 ——
#      旧版把落点写死成 (63,970), 在竞技场页上正好落在箭头**下方 2px 的空白**里,
#      于是"看到箭头 -> 点空处 -> 画面不变 -> 又看到箭头"每 8s 一圈, 永远出不来。
# 现在: 判据和落点都由青色外接框现算(点色优先, 不写死坐标), 取样框也加宽到能罩住两种高度。
# 实测(语料 217 张, 框内青色像素数):
#   竞技场晋级页 916 / 任务页 933  -> 真箭头
#   战场页(整片青底) 5187~5194      -> 超上限拒掉
#   其余 200 张全部 <=44            -> 低于下限拒掉
#   => MIN/MAX 之间隔着 5 倍空隙, 阈值怎么挪都不会翻车。
BACK_ARROW_BOX = (8, 925, 120, 1002)        # 取样框 x0,y0,x1,y1(底部左角)
BACK_ARROW_MIN_PX = 150
BACK_ARROW_MAX_PX = 2000


def back_arrow_pos(img):
    """侧页返回箭头 -> (x, y) 可点落点; 这一帧没有箭头(或那是整片青底) -> None

    落点取外接框中点(和 color_bbox 同一口径): 箭头是"←"形, 中点正落在箭杆上, 是实心可点区。
    """
    import numpy as np
    x0, y0, x1, y1 = BACK_ARROW_BOX
    a = np.asarray(img.convert('RGB'), dtype=np.int16)[y0:y1, x0:x1]
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    m = (b > 170) & (g > 140) & (r < 150)
    n = int(m.sum())
    if not BACK_ARROW_MIN_PX <= n <= BACK_ARROW_MAX_PX:
        return None
    ys, xs = np.nonzero(m)
    return (x0 + (int(xs.min()) + int(xs.max())) // 2,
            y0 + (int(ys.min()) + int(ys.max())) // 2)


def is_back_arrow(img):
    """左下角像"返回箭头"(而不是整片青色背景) -> True"""
    return back_arrow_pos(img) is not None


# ---- 新手引导模态(2026-09-03 10:20 定案: 压暗帧既不是新页面, 也不许花 OCR) ----------
# 长什么样: 游戏弹出一段教学, 把整屏盖一层 ~x0.30 的黑遮罩, 只留
#   [一个圆形高亮切窗(= 这一步要点的地方) + 一块大白气泡 + 一只白色手套手型 + 引导角色立绘]。
# 为什么要单独判: 遮罩把全页颜色压成近黑, 任何页面的点色指纹都不该中(中了就是假指纹),
#   所以路由结果必然是 None -> 旧版接着白烧 675ms 全图 OCR 再判 unknown。
#   实测语料 238 帧: 11 张 lobby_dim + 2 张 other_live10100{5,6} 是这种帧, 其余全不是。
# 判据(纯 numpy 行游程, 实测 1.8ms; cv2 连通块在这台机器上 3.4s/帧, 已弃用):
#   气泡是一整块白圆角矩形 => 有几十行"单行近白像素 >= 150", 且最长行 ~344(气泡宽)。
#   实测分界: 引导帧 rows=83~92 / maxrow=344; 非引导帧最高 rows=2 / maxrow=178。差 40 倍。
GUIDE_WHITE_ROW_MIN = 150      # 单行近白像素数下限
GUIDE_ROWS_MIN = 40            # 满足上一行的行数下限(实测 83 vs 2)
GUIDE_ROW_WHITE_MAX = 250      # 最长行下限(气泡宽度, 实测 344 vs 178)
GUIDE_LUM_MAX = 120.0          # 整帧平均亮度上限(引导帧 50~56, 正常页最低 33.7 但 rows 不过关)


def guide_modal(img):
    """整屏压暗 + 大白气泡(新手引导模态) -> (True, 气泡外接框 x0,y0,x1,y1); 否则 (False, None)"""
    import numpy as np
    a = to_arr(img)
    if a.shape[0] < 300:
        return False, None
    ai = a.astype(np.int16)
    m = (ai[..., 0] > 235) & (ai[..., 1] > 235) & (ai[..., 2] > 235)
    m[:64] = False                       # 微信标题栏是白的, 排除
    pr = m.sum(1)
    rows = np.flatnonzero(pr >= GUIDE_WHITE_ROW_MIN)
    if len(rows) < GUIDE_ROWS_MIN or int(pr.max()) < GUIDE_ROW_WHITE_MAX:
        return False, None
    if float(ai.mean(2).mean()) > GUIDE_LUM_MAX:
        return False, None
    band = m[rows[0]:rows[-1] + 1]
    cols = np.flatnonzero(band.sum(0) > 0)
    return True, (int(cols[0]), int(rows[0]), int(cols[-1]), int(rows[-1]))


HAND_WIN = 15               # 手套掌心是实心白块: 15x15 窗口全白(=225)才算看见手
HAND_MIN_DENSE = 200
# 实测两处手型: lobby_dim 掌心(200,974) 对目标[卡牌页签](163,950);
#             召唤页 掌心(92,986)  对目标[左下返回箭头](58,960)
#   -> 食指在掌心左上 (-37,-24)。掌心正上方 (0,-35) 是上一版真机跑通的落点, 留作第二候选。
HAND_TIP = (-37, -24)


def hand_pos(img, box=None):
    """引导手型(白色手套) -> (指尖x, 指尖y, 掌心x, 掌心y); 认不出来 -> None

    先把气泡外接框(外扩 8px)从白像素里挖掉, 再用积分图找 15x15 全白窗口 ——
    气泡是唯一更大的白块, 不挖掉的话"最白的地方"永远是气泡。
    """
    import numpy as np
    a = to_arr(img).astype(np.int16)
    m = ((a[..., 0] > 235) & (a[..., 1] > 235) & (a[..., 2] > 235)).astype(np.int32)
    m[:64] = 0
    if box:
        x0, y0, x1, y1 = box
        m[max(0, y0 - 8):min(m.shape[0], y1 + 9), max(0, x0 - 8):min(m.shape[1], x1 + 9)] = 0
    H, W = m.shape
    k = HAND_WIN
    if H <= k or W <= k:
        return None
    c = np.zeros((H + 1, W + 1), np.int32)
    c[1:, 1:] = m.cumsum(0).cumsum(1)
    yh, xh = H - k, W - k
    dens = (c[k:k + yh + 1, k:k + xh + 1] - c[0:yh + 1, k:k + xh + 1]
            - c[k:k + yh + 1, 0:xh + 1] + c[0:yh + 1, 0:xh + 1])
    j = int(dens.argmax())
    if dens.ravel()[j] < HAND_MIN_DENSE:
        return None
    cy, cx = divmod(j, xh + 1)
    px, py = cx + k // 2, cy + k // 2
    return (px + HAND_TIP[0], py + HAND_TIP[1], px, py)


GUIDE_NEXT_DX = -56          # [下一步] 画在气泡右下角外侧(实测框(101,397,531,495) -> (475,505))
GUIDE_NEXT_DY = 10


def guide_targets(img):
    """引导模态这一帧可以点的落点(按可信度排序, 纯点色零 OCR) -> [ (x, y), ...]

    调用方负责"点了没反应就换下一个候选"(见 pages/unknown.py 的画面签名升级表):
    引导有 N 步, 每一步的高亮目标都不一样, 任何单一判据都不可能一次点到底。
    """
    # 🔴 2026-09-05 R49/R50 真机: 挽留框「暂未获得奖励 是否继续观看视频」(黑底白面板)
    #   上的"继续"被引导手检测器误识别为新手手 -> 点 (369,629) 反而把广告"续"回播放 ->
    #   下一帧弹回挽留框, 循环。修法: 全黑帧(整屏 max<25)直接返回空, 让 ad_popup/OCR 接力。
    import numpy as np
    arr = np.asarray(img) if not isinstance(img, np.ndarray) else img
    if arr.size:
        # 取整帧亮度均值: 挽留框约 32.7(白色面板 + 大面积黑色), 正常页 > 80
        if float(arr.mean()) < 35.0:
            return []
    ok, box = guide_modal(img)
    if not ok:
        return []
    pts = []
    cb = find_close_badge(img)
    if cb:
        pts.append(cb)
    h = hand_pos(img, box)
    if h:
        pts.append((h[0], h[1]))
    x0, y0, x1, y1 = box
    pts.append((x1 + GUIDE_NEXT_DX, y1 + GUIDE_NEXT_DY))       # [下一步]
    pts.append(((x0 + x1) // 2, (y0 + y1) // 2))               # 气泡正中(多数引导点哪儿都算过)
    if h:
        pts.append((h[2], h[3] - 35))                          # 掌心正上方(上一版真机跑通的落点)
    return pts


# ---- 转场闸门(2026-09-03 定案: 转场帧也要零 OCR) --------------------------------
# 坑(真机 00:42 / 01:42 / 03:12 三处复现): 进战斗前有一道"白烟"转场, 烟雾盖满整屏
#     -> 点色全表一张都不中 -> 旧版每帧白烧一次全图 OCR(675ms), 然后判成 unknown,
#     unknown 又去点遮罩。转场期间唯一正确的动作就是"什么都不做"。
# 判据(实测区间见下, 语料 159 + 真机留出 71 帧里"转场帧"与"正常页"之间零重叠):
#   白烟帧   近白像素 12.1~17.8% / 平均饱和度 15.6~37.6 / 平均亮度 193~216
#   正常页   近白像素 <=5.6%(大厅最高) / 平均饱和度 >=56(宝箱动画页最低 57.1)
#   黑屏帧   平均亮度 <=11.9 / 饱和度 <=0.4(截图失败、微信还在加载)
# 两条门限都留了一倍以上余量, 而且只在"点色全表没收据"时才会被调用 —— 拦不住任何已知页。
TRANS_WHITE_MIN = 9.0      # 近白像素占比%: 白烟帧最低 12.1, 正常页最高 5.6
TRANS_SAT_MAX = 45.0       # 平均饱和度: 白烟帧最高 37.6, 正常页最低 56.0
TRANS_LUM_MIN = 120.0      # 平均亮度: 白烟帧最低 193, 正常页最高 161(战斗)
BLANK_LUM_MAX = 25.0       # 黑屏帧亮度上限(实测 0~11.9; 正常页最低 33.7)
BLANK_SAT_MAX = 25.0       # 黑屏帧饱和度上限(实测 <=0.4)


def frame_stats(img):
    """(平均亮度, 平均饱和度=max-min, 近白像素占比%) 一次 numpy 扫完全帧, ~2ms"""
    import numpy as np
    a = to_arr(img).astype(np.int16)
    mx, mn, lum = a.max(2), a.min(2), a.mean(2)
    white = ((a[..., 0] > 225) & (a[..., 1] > 225) & (a[..., 2] > 225)).mean() * 100.0
    return float(lum.mean()), float((mx - mn).mean()), float(white)


# ---- 跨页协作: "这格宝箱要花钱" 拉黑(真机 2026-09-03 03:54 死循环教训) --------
# 坑: 大厅那一格点下去 -> 面板判出"要花钱" -> 关面板回大厅 -> 那一格颜色没变,
#     还是"可开" -> 再点 -> 再关 ... 6 秒一圈, 实测连刷 16 圈, 一局都没打到。
# 规则: 面板判出付费就把**那一格**拉黑 CHEST_PAID_BLOCK 秒, 期间大厅只点别的格或去对战;
#       到期再探一次(宝箱会随时间转免费), 花钱的口子始终由颜色判据守着。
CHEST_PAID_BLOCK = 300            # 秒; 一场战斗 ~90s, 5 分钟 = 3~4 场之后才回头再试
CHEST_BLOCK_ALL = 'chest@all'     # 不知道是哪一格时(用户手动开的面板)拉黑整行


def chest_slot_key(pos):
    """宝箱格子的拉黑键(坐标即身份: 四格中心 x=109/220/331/441)"""
    return 'chest@%d,%d' % (int(pos[0]), int(pos[1]))


def is_transition(img):
    """白烟/黑屏等转场帧 -> (True, 原因): 本轮既不动作也不跑 OCR"""
    lum, sat, white = frame_stats(img)
    if lum <= BLANK_LUM_MAX and sat <= BLANK_SAT_MAX:
        return True, '黑屏'
    if white >= TRANS_WHITE_MIN and sat <= TRANS_SAT_MAX and lum >= TRANS_LUM_MIN:
        return True, '白烟'
    return False, ''


# ---- 激励视频广告页右上角的[关闭]药丸 (真机 2026-09-03 12:18 卡死 4 分钟教训) ----
# 坑: 广告放完之后整页是黑的, 只剩顶栏"广告 | 已获得奖励"和右上角"关闭"。
#     is_transition 把它当成转场黑屏 -> 每轮"既不动作也不跑 OCR" -> 永久卡在这一页;
#     而 ad_popup 页是靠 OCR 关键词('放弃'/'秒后可获得奖励')定页的, 放完之后这两个词都没了。
# 判据: 黑屏帧里顶栏右半边那团白色像素就是[关闭]按钮(微信广告 SDK 的固定 chrome),
#       纯点色 + 几何, 零 OCR。只在"连续多帧黑屏"时才调用, 转场帧本身不会命中。
AD_CLOSE_BAND = (55, 118)     # 顶栏所在行(实测白色文字 y=79~101, 药丸边框 y=62~104)
AD_CLOSE_X0 = 380             # 只看右半边: 左半边是"广告 | 已获得奖励"标签
AD_CLOSE_WHITE_MIN = 60       # 白色像素数下限(实测这一帧 270)
AD_CLOSE_BOX = ((40, 170), (14, 60))   # 团块外接框 (宽范围, 高范围)

# ==========================================================================
# 业务 re-export (兼容老 from pages.base import ad_close_pos)
# 实际实现在 business/ad.py + business/nav.py (2026-09-09 抽出)
# ==========================================================================
from business.ad import *  # noqa: F401, F403
from business.nav import *  # noqa: F401, F403
