# -*- coding: utf-8 -*-
"""底部导航栏辅助 (兄弟页签点[战斗]回大厅).

旧逻辑在 `pages/base.py`:
    - nav_hits(img) -> int                 # 16 个静态像素命中数
    - nav_present(img) -> bool             # 是否有底部一级导航栏
    - nav_tab_cx(img) -> int | None        # 当前选中页签中心 x

封装成 NavigationHelper 类. 内部 import pages.base 复用函数 (双轨).

用法:
    nav = NavigationHelper()
    if nav.present(img):              # 当前是 5 个一级页之一
        cx = nav.tab_cx(img)          # 点[战斗] cx 回大厅
"""
from pages.base import (
    nav_hits, nav_present, nav_tab_cx, _is_cyan,
    NAV_POINTS, NAV_DEGREE, NAV_MIN_HIT, NAV_TABS,
)


class NavigationHelper:
    """底部一级导航栏辅助 (5 个页签)."""

    def hits(self, img):
        """导航栏 16 个静态像素里命中了几个."""
        return nav_hits(img)

    def present(self, img):
        """这帧底下有没有那条一级导航栏(= 这是 5 个一级页之一)."""
        return nav_present(img)

    def tab_cx(self, img):
        """当前选中的是哪个页签 -> 它的中心 x; 认不出返回 None."""
        return nav_tab_cx(img)

    # 暴露给页面作为内部工具
    @staticmethod
    def is_cyan(px):
        """高亮板那种亮青描边: 0x94DDFB / 0x66C8FE / 0x6CCBFF / 0x93DDFC 都算."""
        return _is_cyan(px)


__all__ = ['NavigationHelper',
           'nav_hits', 'nav_present', 'nav_tab_cx', '_is_cyan',
           'NAV_POINTS', 'NAV_DEGREE', 'NAV_MIN_HIT', 'NAV_TABS']