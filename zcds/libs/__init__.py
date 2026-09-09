# -*- coding: utf-8 -*-
"""zcds 共享库.

包装层:
- window.py  封装 game_utils
- color.py   封装 colorprint
- vision.py  封装 vision
- routing.py 封装 pages/base.py 的路由
- config.py  封装 config.py

新代码用 `from libs.window import Window` 等, 旧代码可继续 `import game_utils as g`.
"""
from .window import Window
from .color import Color
from .vision import Vision, ScreenFeature
from .routing import Router, route_prints, is_soft
from .config import PAGE_CFG, WATCH_ADS, AD_FOCUS

__all__ = [
    'Window',
    'Color',
    'Vision',
    'ScreenFeature',
    'Router',
    'route_prints',
    'is_soft',
    'PAGE_CFG',
    'WATCH_ADS',
    'AD_FOCUS',
]