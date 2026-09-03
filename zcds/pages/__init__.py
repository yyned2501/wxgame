# -*- coding: utf-8 -*-
"""页面包: 每个页面独立模块(特征提取/动作/转移声明)"""
from .base import Page, select_page
from .lobby import LobbyPage
from .matching import MatchingPage
from .battle import BattlePage
from .result import ResultPage
from .ad_popup import AdPopupPage
from .claim_popup import ClaimPopupPage
from .chest_info import ChestInfoPage
from .chest_open import ChestOpenPage
from .diamond_popup import DiamondPopupPage
from .vip_popup import VipPopupPage
from .levelup import LevelUpPage
from .hero_level import HeroLevelPage
from .versus import VersusPage
from .tab_other import TabOtherPage
from .unknown import UnknownPage

ALL_PAGES = [
    AdPopupPage(),
    ClaimPopupPage(),
    HeroLevelPage(),
    ChestInfoPage(),
    ChestOpenPage(),
    DiamondPopupPage(),
    VipPopupPage(),
    ResultPage(),
    LevelUpPage(),
    BattlePage(),
    MatchingPage(),
    LobbyPage(),
    VersusPage(),
    TabOtherPage(),      # 必须在 UnknownPage 之前: 主循环用 pages[-1] 当 unknown
    UnknownPage(),
]