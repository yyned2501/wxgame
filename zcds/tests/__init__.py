# -*- coding: utf-8 -*-
"""zcds 测试脚本 __init__.

把 zcds/ 根目录加到 sys.path, 让测试脚本能用相对路径:
    from pages import ALL_PAGES
    import game_utils as g
    import auto_bot
不需要改测试脚本的 import.

同时 chdir 到 zcds/ 根目录, 让测试脚本里硬编码的 'shots/xxx.png' 相对路径仍可工作.
"""
import os
import sys

# 把 zcds/ 根目录加到 sys.path (tests/ 的父目录)
ZCDS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ZCDS_ROOT not in sys.path:
    sys.path.insert(0, ZCDS_ROOT)

# 切到 zcds/ 根目录, 让 'shots/...' 相对路径生效
os.chdir(ZCDS_ROOT)