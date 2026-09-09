# -*- coding: utf-8 -*-
"""路由 + 软命中封装.

旧逻辑在 `pages/base.py`:
    - route_prints(prints, fimg, degree, pos_tol) -> (page_name, score, src)
    - is_soft(score, fallback_threshold) -> bool
    - is_countdown(text) -> bool
    - match_print(pages, img, prefer) -> (page, score, src)
    - detect_ocr(pages, f, arr) -> (ocr_page, ocr_score)
    - route(pages, f, prefer) -> (page, score, src)
    - select_page(pages, f, prefer) -> page

封装成 Router 类. 内部直接 import 旧 base 模块的函数, 等所有 caller 迁完再删旧实现.

用法:
    router = Router()
    page, score, src = router.route(pages, feature, prefer=())
"""
from pages.base import (route_prints, is_soft, is_countdown,
                         match_print, detect_ocr, route, select_page,
                         CHEST_BLOCK_ALL, CHEST_PAID_BLOCK)


class Router:
    """页面路由 + 软命中 + 倒计时识别."""

    def __init__(self, color=None):
        self.color = color  # 可选, 未来路由可能需要

    def route_prints(self, pages, img, prefer=(), degree=90, pos_tol=2):
        """点色指纹路由 -> (page, score, src in {'order','prefer'})."""
        return route_prints(pages, img, prefer=prefer, degree=degree, pos_tol=pos_tol)

    def is_soft(self, score, fallback_threshold=0.5):
        """软命中: score >= threshold 且 < 1.0 (硬命中)."""
        return is_soft(score, fallback_threshold=fallback_threshold)

    def is_countdown_text(self, text):
        """OCR 文本是倒计时? (e.g. '30秒' '1分20秒')."""
        return is_countdown(text)

    def match_print(self, pages, img, prefer=()):
        """匹配点色指纹返回 (page, score, src)."""
        return match_print(pages, img, prefer=prefer)

    def detect_ocr(self, pages, f, arr=None):
        """OCR 兜底: 按 detect 分数选页面. 返回 (page, score)."""
        return detect_ocr(pages, f, arr=arr)

    def route(self, pages, f, prefer=()):
        """完整路由. 返回 (page, score, src)  src in {'print-prefer','print-order','ocr','unknown'}.
        完整流程: 1) match_print; 2) 失败时 detect_ocr; 3) 都失败回 unknown.
        """
        return route(pages, f, prefer=prefer)

    def select_page(self, pages, f, prefer=()):
        """兼容旧调用: 只要页面对象 (route()[0])."""
        return select_page(pages, f, prefer=prefer)


# 重新导出供 libs 用户
__all__ = ['Router',
           'route_prints', 'is_soft', 'is_countdown',
           'match_print', 'detect_ocr', 'route', 'select_page',
           'CHEST_BLOCK_ALL', 'CHEST_PAID_BLOCK']