# -*- coding: utf-8 -*-
"""路由 + 软命中封装.

旧逻辑在 `pages/base.py`:
    - route_prints(prints, fimg, degree, pos_tol) -> (page_name, score, src)
    - is_soft(score, fallback_threshold) -> bool
    - is_countdown(text) -> bool

封装成 Router 类. 内部直接 import 旧 base 模块的函数, 等所有页面迁完再删旧实现.

用法:
    router = Router(color=Color())
    page_name, score, src = router.route(prints, fimg)
"""
from pages.base import (route_prints, is_soft, is_countdown,
                         CHEST_BLOCK_ALL, CHEST_PAID_BLOCK)


class Router:
    """页面路由 + 软命中 + 倒计时识别."""

    def __init__(self, color=None):
        self.color = color  # 可选, 未来路由可能需要

    def route(self, prints, fimg, degree=90, pos_tol=2):
        """点色指纹路由 -> (page_name, score, src='print'/'ocr')."""
        return route_prints(prints, fimg, degree=degree, pos_tol=pos_tol)

    def is_soft(self, score, fallback_threshold=0.5):
        """软命中: score >= threshold 且 < 1.0 (硬命中)."""
        return is_soft(score, fallback_threshold=fallback_threshold)

    def is_countdown_text(self, text):
        """OCR 文本是倒计时? (e.g. '30秒' '1分20秒')."""
        return is_countdown(text)


# 重新导出供 libs 用户
__all__ = ['Router', 'route_prints', 'is_soft', 'is_countdown',
           'CHEST_BLOCK_ALL', 'CHEST_PAID_BLOCK']