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
CLOSE_RED_MIN_PX = 550      # 红底像素数(实测 716~818)
CLOSE_RED_MAX_PX = 950
CLOSE_BOX_MIN = 30          # 外接框边长(实测 36~48)
CLOSE_BOX_MAX = 60
CLOSE_WHITE_MIN = 60        # 框内白像素=那个叉(实测 142~163)


def find_close_badge(img, cell=12):
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
            hw, hh = (x1 - x0) // 2, (y1 - y0) // 2
            if int(white[cy - hh:cy + hh + 2, cx - hw:cx + hw + 2].sum()) < CLOSE_WHITE_MIN:
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
AD_BODY_Y0 = 150                # 这一行往下算页面主体(顶栏之下)
AD_BODY_MEAN_MAX = 30.0         # 主体平均亮度上限: 实拍广告页 0.1, 最暗的正常页 68.6
AD_BODY_WHITE_MAX = 0.03        # 主体白像素占比上限: 实拍 0.00, 正常页最低 6.7%


def ad_close_pos(img):
    """黑屏广告页右上角[关闭]药丸的中心 -> (x, y); 认不出返回 None. 纯点色, ~1ms"""
    import numpy as np
    a = to_arr(img)
    h, w = a.shape[:2]
    # 前置: 主体必须是黑的。正常页的顶栏同样有白字(大厅/商店/行会实测全部误命中),
    # 而这张页除了顶栏整片是纯黑 —— 这条既是身份判据, 也是防误点的保险。
    body = a[AD_BODY_Y0:min(AD_BODY_Y0 + 700, h), :]
    if float(body.mean()) > AD_BODY_MEAN_MAX or float((body.max(axis=2) > 190).mean()) > AD_BODY_WHITE_MAX:
        return None
    y0, y1 = AD_CLOSE_BAND
    x0 = min(AD_CLOSE_X0, w - 1)
    reg = a[y0:min(y1, h), x0:w]
    m = (reg[..., 0] > 190) & (reg[..., 1] > 190) & (reg[..., 2] > 190)
    if int(m.sum()) < AD_CLOSE_WHITE_MIN:
        return None
    ys, xs = np.nonzero(m)
    bw, bh = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
    (w_lo, w_hi), (h_lo, h_hi) = AD_CLOSE_BOX
    if not (w_lo <= bw <= w_hi and h_lo <= bh <= h_hi):
        return None
    return int(x0 + (xs.min() + xs.max() + 1) // 2), int(y0 + (ys.min() + ys.max() + 1) // 2)


# ---- 结算页[失败礼包]/[胜利礼包]横幅右侧的黄色[领取](看广告)按钮-------------------------------
# (用户 2026-09-03 12:47 指定: "点击黄色的看广告领取, 可以看广告的地方就自动看完")
# 长什么样: 结算页底部一条紫色横幅, 左边一张卡牌、中间两堆资源(金币/木材),
#           右边一颗黄色药丸[领取], 上面压着 AD 场记板图标 + 白字。
# 两种横幅同一颗药丸: [失败礼包]和[胜利礼包]用的是同一颗黄色[领取], 位置/形状一字不差
#   (全语料 38 张命中帧 = 33 张失败 + 5 张胜利, 中心恒 (412,781)~(413,782), 见 COLORPRINT.md §22.3)。
# 额度用完横幅整条消失: 横幅右下角写着"可用 N/8" = 每日激励视频额度; N=0 时游戏不再画这条横幅,
#   所以返回 None 是**正确行为**而不是漏检 —— 探针帧里整个下带 0 个黄色像素(容差放到 ±120 也是 0),
#   不是"按钮变灰没认出来"那种漏检。逐帧取证开 --ad-probe(见 auto_bot.App.ad_probe_shot)。
# 判据 = 点色 + 外接框宽高。只看颜色分不开: 这颗和[宝箱立即开箱]是同一个黄 0xFDCA33,
#       但形状完全不同 —— 领取是"扁宽胶囊"(实测 w 124~126 / h 32~38),
#       开箱那颗被面板挤成"窄高块"(实测 w 58 / h 63, 左边缘还被取样框切在 x=300)。
# 全语料实测(2026-09-03 中午, 552x1006 共 828 帧 = shots 252 + shots_live 576):
#   命中 38 帧, 全部是 result 页; 中心 (412,779)~(413,782)(旧注释写的 (412,781) 是取了子集, 已按全语料重扫修正);
#   其余 790 帧 0 误命中(lobby 28 / battle 19 / chest_info 13 / chest_open 3 /
#   vip_popup 4 / vip_month 2 / matching 1 / other 12 全不中)。
AD_CLAIM_BOX = (300, 700, 552, 880)     # 只扫横幅右半: 左边那两堆金币/木材也是黄的, 必须挡在外面
AD_CLAIM_COLOR = 0xFDCA33
AD_CLAIM_DEGREE = 90                    # 每通道 ±13(和动作层其它颜色尺子同口径)
AD_CLAIM_MIN_PX = 2200                  # 实测 3187~3236, 下限留 1/3 余量
AD_CLAIM_W = (108, 145)                 # 外接框宽: 实测 124~126
AD_CLAIM_H = (26, 50)                   # 外接框高: 实测 32~38


def ad_claim_pos(img):
    """黄色[领取](看广告)按钮中心 -> (x, y); 这一帧没有横幅/按钮已灰掉 -> None. 纯点色 ~1ms"""
    import numpy as np
    b = _clip_box(img, AD_CLAIM_BOX)
    if b is None:
        return None
    x0, y0 = b[0], b[1]
    m = color_mask(img, AD_CLAIM_BOX, AD_CLAIM_COLOR, AD_CLAIM_DEGREE)
    if int(m.sum()) < AD_CLAIM_MIN_PX:
        return None
    ys, xs = np.nonzero(m)
    bw, bh = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
    if not (AD_CLAIM_W[0] <= bw <= AD_CLAIM_W[1] and AD_CLAIM_H[0] <= bh <= AD_CLAIM_H[1]):
        return None
    return int(x0 + (xs.min() + xs.max() + 1) // 2), int(y0 + (ys.min() + ys.max() + 1) // 2)


# ---- 广告页左上角那颗状态药丸: 判"广告放完了没有"(零 OCR) ------------------------------
# 同一颗药丸, 两种文案(实拍 2026-09-02 12:47 连拍 5 帧):
#   播放中  "广告 | 27 秒后可获得奖励"  -> 右边界 x=211
#   播放中  "广告 |  8 秒后可获得奖励"  -> 右边界 x=204   (数字掉一位, 边框跟着缩)
#   放完了  "广告 | 已获得奖励"        -> 右边界 x=164   (整条文案短一截)
# 为什么用"本场相对缩窄"而不是绝对阈值: 药丸宽度是**各家广告 SDK 自己的 chrome**,
#   另一路广告(shots/ad_popup_live122400)同一句"已获得奖励"的右边界是 **209** ——
#   绝对阈值一换广告源就翻车。所以记本场见过的最大宽度, 缩掉 >=AD_PILL_SHRINK 才算放完。
#   实测同一场内倒计时态与放奖态差 47px, 而倒计时自身抖动只有 7px(211->204) -> 阈值取 28 稳。
AD_PILL_BAND = (55, 118, 0, 330)        # (y0, y1, x0, x1): 顶栏左半, 右半是[关闭]药丸, 不混进来
AD_PILL_MIN_COLS = 2                    # 单列白像素 >=2 才算数(滤掉抗锯齿毛刺)
AD_PILL_SHRINK = 28                     # 相对本场最宽缩掉这么多像素 = 文案换成"已获得奖励"
# ---- 第二把尺子(2026-09-03 14:50 实测, scratch/scripts/pillwhite_0903.py) ----
# 右边界只量"最右那根竖线在哪": 万一某家 SDK 把倒计时和放奖两句渲染成同一个宽度,
# 第一把尺子永远不响 -> 只能干等 AD_WATCH_MAX=40s。带内**白像素总数**量的是"有几个字",
# 跟边框位置无关, 是同一件事的第二种量法。实拍连拍(同一场广告, 单位 px):
#   watch_124711 倒计时27s 827 / 124723 倒计时27s 830 / 124735 倒计时8s 794
#   watch_124746 已获得奖励 606 / 124758 已获得奖励 606
# 倒计时自身抖动(数字掉一位)只有 4.3%, 换成"已获得奖励"少 27% -> 门限取 15% 两头都留余量。
# 另一路 SDK 的放奖帧(ad_popup_live122400)白像素是 914, 比上面那场的倒计时还多
#   -> 和右边界一样, 只能跟"本场峰值"比, 不能定绝对阈值。
AD_PILL_SHRINK_PCT = 0.15               # 带内白像素比本场峰值少这么多 = 文案变短了
AD_PILL_LOW_HOLD = 4.0                  # 而且要连续这么多秒都少才算(见下)
# 门闩阈值: 左边界漂移超过这么多 px 才算顶栏被广告画面盖住。
#   不能取太小 —— 实测两家广告 SDK 的药丸左边界天然差 7px(32 / 39, 见
#   scratch/scripts/pillwhite_0903.py), 取 6 会把换了个广告源误判成盖顶栏
#   (test_ad_escape 第[4]段就是这么炸的); 真被盖住(watch_124707)是 32->222,
#   差 190px -> 取 20: 7px 放过, 190px 拦住。
AD_PILL_LEFT_TOL = 20


def ad_pill_state(img):
    """广告页左上状态药丸 -> (右边界 x, 带内白像素数, 左边界 x); 这一帧没有顶栏 -> None

    右边界 = 第一把尺子(文案越短越靠左), 白像素数 = 第二把尺子(字数越少像素越少),
    左边界 = 门闩: 广告画面糊上顶栏时实拍只剩 157 个白像素、左边界从 32 跳到 222
    (shots/watch_124707), 那种帧两把尺子都不许作数, 否则会被误判成文案变短 -> 提前关广告;
    左边界只是这一帧量得准不准的锚, 漂移门限见 AD_PILL_LEFT_TOL(两家 SDK 天然差 7px)。
    """
    import numpy as np
    y0, y1, x0, x1 = AD_PILL_BAND
    a = to_arr(img)
    h, w = a.shape[:2]
    reg = a[y0:min(y1, h), x0:min(x1, w), :3].astype(np.int16)
    if reg.size == 0:
        return None
    m = (reg.max(axis=2) > 170)
    cols = m.sum(axis=0)
    nz = np.nonzero(cols >= AD_PILL_MIN_COLS)[0]
    if not len(nz):
        return None
    return int(nz.max()) + x0, int(m.sum()), int(nz.min()) + x0


def ad_pill_right(img):
    """药丸右边界(第一把尺子); 这一帧没有顶栏(不是广告页) -> None"""
    st = ad_pill_state(img)
    return st[0] if st else None


# ==================== 底部一级导航栏(5 个页签) ====================
# 2026-09-03 真机教训: 走完新手引导人落在[商店]页, 是用户手动点了最中间的页签才回到大厅的。
# 这 5 个一级页(商店/卡牌/战斗/城堡/排名)内容全随账号+等级变, 标指纹等于标在文字上
# (lobby 刚踩过这个坑), 所以不逐页标身份 —— 只标[导航栏在不在]:
#   导航栏在 + 大厅指纹没中  =>  我在某个兄弟页签上  =>  点最中间那个(战斗)回大厅。
NAV_TABS = [(50, 'shop'), (163, 'cards'), (276, 'battle'), (389, 'castle'), (502, 'rank')]
NAV_LOBBY_TAB = (276, 950)     # 中间页签 = 战斗 = 大厅(lobby 指纹就标在它的高亮板上)
# 16 个跨 5 页完全一致的静态图标像素(实测每页 16/16, 同一逐帧通道极差 <=6)
NAV_POINTS = [
    [156, 934, 0xFFB511], [144, 940, 0x2485FC], [192, 940, 0xA748FC], [166, 944, 0xFDA613],
    [172, 946, 0xFDA613], [194, 946, 0xA647FA], [182, 948, 0xC05F0D], [476, 952, 0xAC6411],
    [296, 930, 0xC1C8D8], [262, 932, 0xD8DCE4], [374, 936, 0xD6D6D6], [396, 934, 0xC1BEB7],
    [144, 942, 0x2787FC], [168, 942, 0xFDA813], [72, 942, 0x4153C6], [382, 936, 0xACADB3],
]
NAV_DEGREE = 92               # ±10, 比页面指纹(85)更严: 只用来判"导航栏在不在"
NAV_MIN_HIT = 12              # 语料 799 张实测: 带栏帧最低 14, 不带栏帧最高 9(全是压暗的引导帧)
NAV_SOFT_HIT = 9            # 供测试断言分界用: 低于这个数一律当"没有导航栏"
NAV_BAND = (905, 996)         # 选中页签高亮板的纵向范围


def _is_cyan(px):
    """高亮板那种亮青描边: 0x94DDFB / 0x66C8FE / 0x6CCBFF / 0x93DDFC 都算"""
    r, g, b = int(px[0]), int(px[1]), int(px[2])
    return b > 220 and g >= 160 and r < 190 and (g - r) > 30


def nav_hits(img):
    """导航栏 16 个静态像素里命中了几个"""
    arr = to_arr(img)
    pts = scale_points(NAV_POINTS, (arr.shape[1], arr.shape[0]))
    return sum(1 for x, y, c in pts if is_color(arr, x, y, c, NAV_DEGREE))


def nav_present(img):
    """这帧底下有没有那条一级导航栏(= 这是 5 个一级页之一)"""
    return nav_hits(img) >= NAV_MIN_HIT


def nav_tab_cx(img):
    """当前选中的是哪个页签 -> 它的中心 x; 认不出返回 None。
    只有被选中的页签背后有一块亮青描边的高亮板, 板边框正好穿过页签中心那一列
    (实测: 选中列 20~50 个青像素, 未选中列一律 0)。"""
    arr = to_arr(img)
    w, h = arr.shape[1], arr.shape[0]
    for cx, _name in NAV_TABS:
        if not 0 <= cx < w:
            continue
        n = sum(1 for y in range(NAV_BAND[0], min(NAV_BAND[1], h)) if _is_cyan(arr[y, cx]))
        if n >= 8:
            return cx
    return None
