# -*- coding: utf-8 -*-
"""弹窗 + 返回箭头 + 引导 + 转场封装.

旧逻辑在 `pages/base.py`:
    - find_close_badge(img, cell=8) -> (x, y) | None
    - back_arrow_pos(img) -> (x, y) | None
    - is_back_arrow(img) -> bool
    - guide_modal(img) -> (modal_type, targets)
    - hand_pos(img, box) -> (x, y) | None
    - guide_targets(img) -> [(x, y), ...]
    - is_transition(img) -> bool
    - frame_stats(img) -> (mean, std)
    - chest_slot_key(pos) -> (key, x, y)

封装成 ModalHelper 类. 内部 import pages.base 复用函数 (双轨).

用法:
    modal = ModalHelper()
    pos = modal.find_close_badge(img)   # 找弹窗右上角 [X]
    pos = modal.back_arrow_pos(img)      # 找侧页 [返回]箭头
    targets = modal.guide_targets(img)   # 新手引导落点
"""
from pages.base import (find_close_badge,
                         back_arrow_pos, is_back_arrow,
                         guide_modal, hand_pos, guide_targets,
                         is_transition, frame_stats,
                         chest_slot_key,
                         # 关联常量
                         CLOSE_RED_MIN_PX, CLOSE_RED_MAX_PX,
                         CLOSE_BOX_MIN, CLOSE_BOX_MAX,
                         CLOSE_WHITE_MIN,
                         CLOSE_RIGHT_MARGIN,
                         CLOSE_CENTER_WHITE_MIN,
                         BACK_ARROW_BOX,
                         BACK_ARROW_MIN_PX,
                         BACK_ARROW_MAX_PX,
                         COUNTDOWN_RE)


class ModalHelper:
    """弹窗 + 引导 + 转场辅助."""

    # ---- 关闭徽章 ----
    def find_close_badge(self, img, cell=8):
        """整帧找红底白叉关闭徽章 -> (x, y); 没有则 None.
        多个候选取最靠右的(关闭键都在右上)."""
        return find_close_badge(img, cell=cell)

    # ---- 侧页返回箭头 ----
    def back_arrow_pos(self, img):
        """侧页返回箭头 -> (x, y) 可点落点; 没有箭头 -> None."""
        return back_arrow_pos(img)

    def is_back_arrow(self, img):
        """这一帧是否有侧页返回箭头?"""
        return is_back_arrow(img)

    # ---- 新手引导 ----
    def guide_modal(self, img):
        """新手引导模态类型 + 落点."""
        return guide_modal(img)

    def hand_pos(self, img, box=None):
        """新手引导手形位置."""
        return hand_pos(img, box=box)

    def guide_targets(self, img):
        """新手引导所有落点 (新手手位置 + 文本按钮位置)."""
        return guide_targets(img)

    # ---- 转场 ----
    def is_transition(self, img):
        """这一帧是否转场帧?(白烟/黑屏)."""
        return is_transition(img)

    # ---- 帧统计 ----
    def frame_stats(self, img):
        """帧统计 (mean, std). 用于压暗/过场检测."""
        return frame_stats(img)

    # ---- 宝箱 key ----
    def chest_slot_key(self, pos):
        """宝箱槽位 (x, y) -> 跨页拉黑 key."""
        return chest_slot_key(pos)


__all__ = ['ModalHelper',
           # 函数
           'find_close_badge', 'back_arrow_pos', 'is_back_arrow',
           'guide_modal', 'hand_pos', 'guide_targets',
           'is_transition', 'frame_stats', 'chest_slot_key',
           # 常量
           'CLOSE_RED_MIN_PX', 'CLOSE_RED_MAX_PX',
           'CLOSE_BOX_MIN', 'CLOSE_BOX_MAX', 'CLOSE_WHITE_MIN',
           'CLOSE_RIGHT_MARGIN', 'CLOSE_CENTER_WHITE_MIN',
           'BACK_ARROW_BOX', 'BACK_ARROW_MIN_PX', 'BACK_ARROW_MAX_PX',
           'COUNTDOWN_RE']