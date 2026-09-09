# -*- coding: utf-8 -*-
"""zcds 业务模块 (有游戏知识的工具, 不是 libs 库).

按 2026-09-09 用户反馈: libs 只是库, 业务放这里或 pages/:
- ad.py     激励视频广告: ad_close_pos / ad_pill_state / is_ad_black / ...
- modal.py  弹窗/引导/转场: find_close_badge / guide_modal / is_transition
- nav.py    底部一级导航: nav_present / nav_tab_cx
- chest.py  跨页宝箱 key: chest_slot_key
- print_.py 锚点/路由辅助: anchor_points / best_print / soft_hit

页面层调用: from business.ad import ad_close_pos
旧代码兼容: from pages.base import ad_close_pos (pages/base.py re-export)
"""
