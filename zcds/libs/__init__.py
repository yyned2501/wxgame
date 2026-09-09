# -*- coding: utf-8 -*-
"""zcds 共享库.

包装层 (双轨运行, 旧模块仍可 import):
- window.py     封装 game_utils (Window 类)
- color.py      封装 colorprint (Color 类)
- vision.py     封装 vision (Vision, ScreenFeature)
- routing.py    封装 pages/base 路由 (Router 类)
- modal.py      封装 pages/base 弹窗/引导/转场 (ModalHelper 类)
- ad.py         封装 pages/base 广告 (AdHelper 类)
- navigation.py 封装 pages/base 底部导航 (NavigationHelper 类)
- config.py     封装 config 全局常量 + PAGE_CFG/WATCH_ADS/AD_FOCUS

新代码用 `from libs.window import Window` 等; 旧代码继续 `import game_utils as g` 等.
"""
from .window import Window
from .color import Color
from .vision import Vision, ScreenFeature
from .routing import Router, route_prints, is_soft, is_countdown
from .modal import ModalHelper, find_close_badge, back_arrow_pos, is_back_arrow
from .ad import AdHelper, ad_close_pos, ad_claim_pos, ad_pill_state, is_ad_black
from .navigation import NavigationHelper, nav_present, nav_tab_cx
from .config import PAGE_CFG, WATCH_ADS, AD_FOCUS

__all__ = [
    # 包装类
    'Window', 'Color', 'Vision', 'ScreenFeature', 'Router',
    'ModalHelper', 'AdHelper', 'NavigationHelper',
    # 路由
    'route_prints', 'is_soft', 'is_countdown',
    # 弹窗/引导
    'find_close_badge', 'back_arrow_pos', 'is_back_arrow',
    # 广告
    'ad_close_pos', 'ad_claim_pos', 'ad_pill_state', 'is_ad_black',
    # 导航
    'nav_present', 'nav_tab_cx',
    # 配置
    'PAGE_CFG', 'WATCH_ADS', 'AD_FOCUS',
]