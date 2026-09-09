# -*- coding: utf-8 -*-
"""全局常量封装.

旧 `config.py` 提供 PAGE_CFG / WATCH_ADS / AD_FOCUS / ROOT / SHOTS_DIR.
封装成 Config 类 (暂保持 module-level 常量, 类留作未来扩展).

注意: `pages/lobby.py` 里的 CHEST_* / PVP_* 常量**不在这里**,** 它们是 lobby 页面专属,
封装到 libs/lobby_constants.py 之后,等下一步做.

用法:
    from libs.config import PAGE_CFG, WATCH_ADS, AD_FOCUS
"""
from config import ROOT, SHOTS_DIR, PAGE_CFG, WATCH_ADS, AD_FOCUS


class Config:
    """全局配置封装 (暂只读)."""

    def __init__(self):
        self.ROOT = ROOT
        self.SHOTS_DIR = SHOTS_DIR
        self.PAGE_CFG = PAGE_CFG
        self.WATCH_ADS = WATCH_ADS
        self.AD_FOCUS = AD_FOCUS


__all__ = ['Config', 'ROOT', 'SHOTS_DIR', 'PAGE_CFG', 'WATCH_ADS', 'AD_FOCUS']