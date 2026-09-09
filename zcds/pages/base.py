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



# ==========================================================================
# 业务 re-export (兼容老 from pages.base import XXX)
# 实现已抽到 business/ 子模块 (2026-09-09 拆分)
# ==========================================================================
from business.ad import *  # noqa: F401, F403  广告业务
from business.nav import *  # noqa: F401, F403  导航业务
from business.modal import *  # noqa: F401, F403  弹窗/引导/转场/返回箭头
from business.chest import *  # noqa: F401, F403  跨页宝箱 key
from libs.color import color_button, color_pixels  # noqa: F401  颜色工具 (libs/color)
from business.chest import CHEST_BLOCK_ALL, CHEST_PAID_BLOCK, FLIP_BLOCK  # 拉黑常量 (在 business/chest 集中管)
