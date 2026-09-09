# -*- coding: utf-8 -*-
"""zcds 通用库.

只放**通用工具**(无业务), **业务**逻辑放 pages/base.py 或 pages/*:
- window.py     窗口/截图/click/drag (封装 game_utils)
- color.py      点色指纹 (封装 colorprint)
- vision.py     OCR + ScreenFeature (封装 vision)
- routing.py    路由框架: route_prints/is_soft/match_print/detect_ocr/route/select_page
- config.py     全局常量: PAGE_CFG / WATCH_ADS / AD_FOCUS

业务函数 (按用户 2026-09-09 反馈: libs 不操作业务):
- 广告相关 (ad_close_pos/ad_claim_pos/ad_pill_state/ad_black_frac) -> pages/base.py
- 弹窗/引导/转场 (find_close_badge/guide_modal/is_transition/back_arrow_pos) -> pages/base.py
- 导航 (nav_present/nav_tab_cx) -> pages/base.py

新代码可从 `from libs.window import Window` 等; 旧代码继续 `import game_utils as g`.
"""
from .window import Window
from .color import Color
from .vision import Vision, ScreenFeature
from .routing import Router, route_prints, is_soft, is_countdown
from .config import PAGE_CFG, WATCH_ADS, AD_FOCUS

__all__ = [
    # 通用工具类
    'Window', 'Color', 'Vision', 'ScreenFeature', 'Router',
    # 路由
    'route_prints', 'is_soft', 'is_countdown',
    # 配置
    'PAGE_CFG', 'WATCH_ADS', 'AD_FOCUS',
]