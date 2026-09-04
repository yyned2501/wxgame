# -*- coding: utf-8 -*-
"""页面包: 每个页面独立模块(特征提取/动作/转移声明)"""
from .base import Page, select_page
from .lobby import LobbyPage
from .matching import MatchingPage
from .newcard import NewCardPage
from .battle import BattlePage
from .result import ResultPage
from .ad_popup import AdPopupPage
from .claim_popup import ClaimPopupPage
from .chest_info import ChestInfoPage
from .chest_open import ChestOpenPage
from .diamond_popup import DiamondPopupPage
from .vip_popup import VipPopupPage
from .fps_popup import FpsPopupPage
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
    FpsPopupPage(),   # 2026-09-04 08:26: 帧率自适应弹窗盖在结算页上, 必须排在 ResultPage 前面
    ResultPage(),
    NewCardPage(),     # 结算/升级后弹的新卡页(真机 16:03 卡死 60s 那一张)
    LevelUpPage(),
    BattlePage(),
    MatchingPage(),
    LobbyPage(),
    VersusPage(),
    TabOtherPage(),      # 必须在 UnknownPage 之前: 主循环用 pages[-1] 当 unknown
    UnknownPage(),
]