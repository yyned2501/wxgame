# -*- coding: utf-8 -*-
"""页面基类 + 路由(定页面只看点色; OCR 是最后兜底, 动作层读字另说)

三级路由(2026-09-03 定案: OCR 又慢又不准, 识别成功后一律用点色 —— 全表点色 2.2ms, 全图 OCR 675ms):
  1) 指纹全中      先查上一步声明的候选页(next_pages ~ mxdzz 的 link) -> src='print-prefer',
                   再按 ALL_PAGES 注册顺序(弹窗在前, unknown 在最后) -> src='print-order'
  2) 软命中        只差 <=1 个点且甩开第二名 >=0.20 -> src='print-*-soft';
                   仍然算点色定页, 依然不跑 OCR(主循环要求连续 2 帧同页才动手, 见 auto_bot)
  3) 全图 OCR      前两级一点收据都没有(新页面/被别的窗口挡住/改版)才花这份钱 -> src='ocr',
                   同分时再用点色部分命中率 tie-break, 再不行 unknown
门限常量与推导见本文件"软命中"一节 + COLORPRINT.md §6.1; 回归锁在
test_print_route.py[10] / test_zero_ocr.py / test_cpu_offline.py 场景7。
"""
import logging
import re

from colorprint import (DEFAULT_DEGREE, DEFAULT_POS_TOL, color_bbox, color_count,
                        is_multi_color, print_score, to_arr)


class Page:
    """所有页面的基类.

    子类需要实现/声明:
      name        页面名
      points      点色指纹 [(x, y, 0xRRGGBB), ...]  —— 页面身份的唯一判据
      prints      可选: 同页多形态的多组指纹(任一全中即算本页)
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
    degree = DEFAULT_DEGREE
    pos_tol = DEFAULT_POS_TOL
    act_needs_ocr = True       # False=动作层纯点色, 主循环就别为本页跑 OCR

    @classmethod
    def fingerprints(cls):
        """本页的全部指纹组"""
        if cls.prints:
            return tuple(tuple(fp) for fp in cls.prints if fp)
        return (tuple(cls.points),) if cls.points else ()

    # ---- 点色指纹 ----
    def print_score(self, img) -> float:
        """最佳指纹组的命中比例(0~1, 全中=1)"""
        best = 0.0
        for fp in self.fingerprints():
            s = print_score(img, fp, self.degree, self.pos_tol)
            if s > best:
                best = s
        return best

    def print_match(self, img) -> bool:
        """指纹是否全中(= 确认是当前页)"""
        return any(is_multi_color(img, fp, self.degree, self.pos_tol)
                   for fp in self.fingerprints())

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


def best_print(page, arr):
    """本页最强指纹 -> (命中比例, 该指纹点数); 没指纹的页返回 (0.0, 0)"""
    best, n = 0.0, 0
    for fp in page.fingerprints():
        if not fp:
            continue
        s = print_score(arr, fp, page.degree, page.pos_tol)
        if s > best:
            best, n = s, len(fp)
    return best, n


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
    src: 'prefer'/'order' = 指纹全中; '<src>-soft' = 只差<=1 点的软命中;
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
#   角标 "0时19分55秒" / 加速按钮 "[AD] -30分钟"(点它就是看广告, WATCH_ADS=False 时绝不点)
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
    a = np.asarray(img.convert('RGB'), dtype=np.int16)
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


# ---- 侧页"返回箭头"判据(真机 2026-09-03 00:22 定案) ----
# 坑: 任务/商店/英雄这类侧页左下角有个青色返回箭头, 页面本身没进指纹表 -> 判成 unknown,
#     而 unknown 只会瞎点遮罩, 挂机就此卡死(用户手动停在任务页时必现)。
# 判据: 量左下角小框里的青色像素数 —— 任务页 463 / 大厅·结算·宝箱面板 0 / 战场页 1860。
#     战场页虽然也青但它是已知页(轮不到兜底), 而且远超上限, 双重保险。
BACK_ARROW_POS = (63, 970)                 # 箭头中心(真机实测)
BACK_ARROW_BOX = (38, 950, 90, 992)        # 取样框 x0,y0,x1,y1
BACK_ARROW_MIN_PX = 150
BACK_ARROW_MAX_PX = 1000


def is_back_arrow(img):
    """左下角像"返回箭头"(而不是整片青色背景) -> True"""
    import numpy as np
    x0, y0, x1, y1 = BACK_ARROW_BOX
    a = np.asarray(img.convert('RGB'), dtype=np.int16)[y0:y1, x0:x1]
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    n = int(((b > 170) & (g > 140) & (r < 150)).sum())
    return BACK_ARROW_MIN_PX <= n <= BACK_ARROW_MAX_PX


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
