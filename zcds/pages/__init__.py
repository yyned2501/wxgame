# -*- coding: utf-8 -*-
"""页面包: 每个页面独立模块(特征提取/动作/转移声明)"""
from .base import Page, select_page
from .lobby import LobbyPage
from .matching import MatchingPage
from .battle import BattlePage
from .result import ResultPage
from .claim_popup import ClaimPopupPage
from .chest_info import ChestInfoPage
from .diamond_popup import DiamondPopupPage
from .vip_popup import VipPopupPage
from .unknown import UnknownPage

ALL_PAGES = [
    ClaimPopupPage(),
    ChestInfoPage(),
    DiamondPopupPage(),
    VipPopupPage(),
    ResultPage(),
    BattlePage(),
    MatchingPage(),
    LobbyPage(),
    UnknownPage(),
]