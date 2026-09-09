# -*- coding: utf-8 -*-
"""跨页宝箱业务 (从 pages/base.py L553-556 抽出).

含 1 个函数 + 2 个拉黑常量:
- chest_slot_key: 宝箱格子拉黑键
- CHEST_BLOCK_ALL: 整行别碰 (用户手动开的面板判过付费但说不清是哪一格)
- CHEST_PAID_BLOCK: 单格付费冷却
"""
# 拉黑常量 (lobby / chest_info 共享)
CHEST_BLOCK_ALL = '__chest_block_all__'
CHEST_PAID_BLOCK = 300     # 单格付费冷却 300 秒 (见 lobby.py)
FLIP_BLOCK = 30             # 翻页卡死 30 秒


def chest_slot_key(pos):
    """宝箱格子的拉黑键(坐标即身份: 四格中心 x=109/220/331/441)"""
    return 'chest@%d,%d' % (int(pos[0]), int(pos[1]))


__all__ = ['chest_slot_key', 'CHEST_BLOCK_ALL', 'CHEST_PAID_BLOCK', 'FLIP_BLOCK']