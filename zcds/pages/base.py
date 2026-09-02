# -*- coding: utf-8 -*-
"""页面基类 + 路由(点色指纹定页面, OCR 文字只做兜底/动作层)

路由规则借鉴 mxdzz/ctrl.py:
  1) 页面身份 = 点色指纹全中(pages/*.py 的 points), 不再靠 OCR 文字猜
  2) 上一步动作声明的候选页(next_pages ~ mxdzz 的 link)优先查, 命中即用
  3) 按 ALL_PAGES 注册顺序查其余(弹窗在前, unknown 在最后)
  4) 全都没全中 -> 退回 OCR detect 打分(应对窗口被遮挡/新页面), 再不行 unknown
"""
import logging

from colorprint import (DEFAULT_DEGREE, DEFAULT_POS_TOL, is_multi_color, print_score,
                        to_arr)


class Page:
    """所有页面的基类.

    子类需要实现/声明:
      name        页面名
      points      点色指纹 [(x, y, 0xRRGGBB), ...]  —— 页面身份的唯一判据
      prints      可选: 同页多形态的多组指纹(任一全中即算本页)
      degree      颜色相似度(默认 85 => 每通道 ±19)
      pos_tol     坐标容差像素(默认 1, 吸收窗口缩放取整)
      next_pages  执行动作后可能跳转的页面名(= mxdzz 的 link)
      act(ctx)    干本页的事, 返回是否执行了动作
      detect(f)   文字特征兜底分(动作层也常用它判断按钮/文案)
    """
    name = 'base'
    next_pages = ()
    detail = ''
    points = ()
    prints = ()
    degree = DEFAULT_DEGREE
    pos_tol = DEFAULT_POS_TOL

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


def match_print(pages, img, prefer=()):
    """点色指纹匹配. 返回 (page|None, score, src)
    src: 'prefer'=转移候选内命中 / 'order'=注册顺序命中 / None=没全中
    """
    arr = to_arr(img)
    preferred = [p for p in pages if p.name in prefer]
    rest = [p for p in pages if p.name not in prefer]
    best, best_s = None, -1.0
    for group, src in ((preferred, 'prefer'), (rest, 'order')):
        for p in group:
            s = p.print_score(arr)
            if s >= 1.0:
                return p, s, src
            if s > best_s:
                best, best_s = p, s
    return None, max(best_s, 0.0), None


def detect_ocr(pages, f):
    """OCR 文字兜底: 按 detect 分数选页面"""
    best, best_score = None, -1.0
    for p in pages:
        try:
            s = p.detect(f)
        except Exception:
            logging.exception('页面 %s detect 异常', p.name)
            continue
        if s > best_score:
            best, best_score = p, s
    if best is None or best_score < 0.3:
        return pages[-1], 0.0
    return best, best_score


def route(pages, f, prefer=()):
    """完整路由. 返回 (page, score, src)  src in {'print-prefer','print-order','ocr','unknown'}"""
    page, score, src = match_print(pages, f.img, prefer)
    if page is not None:
        return page, score, 'print-' + src
    ocr_page, ocr_score = detect_ocr(pages, f)
    if ocr_page.name != pages[-1].name:
        return ocr_page, ocr_score, 'ocr'
    return ocr_page, 0.0, 'unknown'


def select_page(pages, f, prefer=()):
    """兼容旧调用: 只要页面对象"""
    return route(pages, f, prefer)[0]