# -*- coding: utf-8 -*-
"""zcds 通用库.

只放**通用工具**(无业务), **业务**逻辑放 pages/base.py 或 business/:
- window.py     窗口/截图/click/drag (封装 game_utils)
- color.py      点色指纹 (封装 colorprint)
- vision.py     OCR + ScreenFeature (封装 vision)
- config.py     全局常量: PAGE_CFG / WATCH_ADS / AD_FOCUS

业务函数 (按 2026-09-09 用户反馈"libs 不应操作业务"):
- 广告 (ad_close_pos/ad_claim_pos/ad_pill_state/ad_black_frac) -> business/ad.py
- 弹窗/引导/转场/返回箭头 -> business/modal.py
- 导航 (nav_present/nav_tab_cx) -> business/nav.py
- 宝箱 key (chest_slot_key) + 拉黑常量 -> business/chest.py
- 路由 (route_prints/match_print/detect_ocr/route/select_page) -> pages/base.py
  (因为路由依赖 Page.detect, 是业务)

新代码可从 `from libs.window import Window` 等; 旧代码继续 `import game_utils as g`.
"""
from .window import Window
from .color import Color
from .vision import Vision, ScreenFeature
from .config import PAGE_CFG, WATCH_ADS, AD_FOCUS

__all__ = [
    # 通用工具类
    'Window', 'Color', 'Vision', 'ScreenFeature',
    # 配置
    'PAGE_CFG', 'WATCH_ADS', 'AD_FOCUS',
]