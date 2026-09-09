# -*- coding: utf-8 -*-
"""弹窗/引导/转场业务 (从 pages/base.py 抽出).

含 5 组功能:
- 关闭徽章: find_close_badge + CLOSE_* 常量
- 新手引导: guide_modal/hand_pos/guide_targets + 关联常量
- 转场闸门: is_transition/frame_stats
- 侧页返回箭头 (back_arrow): back_arrow_pos/is_back_arrow + BACK_ARROW_* 常量

调用: from business.modal import find_close_badge, guide_targets
旧代码兼容: from pages.base import find_close_badge (pages/base.py re-export)
"""
from colorprint import to_arr


# ==========================================================================
# 关闭徽章 (从 pages/base.py L247-294 + L297-349 抽出)
# ==========================================================================
CLOSE_RED_MIN_PX = 550
CLOSE_RED_MAX_PX = 1010
CLOSE_BOX_MIN = 30
CLOSE_BOX_MAX = 54
CLOSE_WHITE_MIN = 60
CLOSE_RIGHT_MARGIN = 120
CLOSE_CENTER_WHITE_MIN = 30


def find_close_badge(img, cell=8):
    """整帧找红底白叉关闭徽章 -> (x, y); 没有则 None. 多个候选取最靠右的(关闭键都在右上)"""
    import numpy as np
    a = to_arr(img).astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    red = (r > 185) & (g < 105) & (b < 105) & ((r - np.maximum(g, b)) > 90)
    white = (r > 200) & (g > 200) & (b > 200)
    h, w = red.shape
    gh, gw = h // cell, w // cell
    grid = red[:gh * cell, :gw * cell].reshape(gh, cell, gw, cell).sum(axis=(1, 3))
    seen = np.zeros((gh, gw), dtype=bool)
    cands = []
    for i in range(gh):
        for j in range(gw):
            if not grid[i, j] or seen[i, j]:
                continue
            stack, cells = [(i, j)], []
            seen[i, j] = True
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < gh and 0 <= nx < gw and grid[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
            ys = [c[0] for c in cells]
            xs = [c[1] for c in cells]
            y0, y1 = min(ys) * cell, (max(ys) + 1) * cell
            x0, x1 = min(xs) * cell, (max(xs) + 1) * cell
            sub = red[y0:y1, x0:x1]
            n = int(sub.sum())
            if not CLOSE_RED_MIN_PX <= n <= CLOSE_RED_MAX_PX:
                continue
            if not (CLOSE_BOX_MIN <= x1 - x0 <= CLOSE_BOX_MAX
                    and CLOSE_BOX_MIN <= y1 - y0 <= CLOSE_BOX_MAX):
                continue
            pts = np.argwhere(sub)
            cy = int(pts[:, 0].mean()) + y0
            cx = int(pts[:, 1].mean()) + x0
            if cx < w - CLOSE_RIGHT_MARGIN:
                continue
            hw, hh = (x1 - x0) // 2, (y1 - y0) // 2
            if int(white[cy - hh:cy + hh + 2, cx - hw:cx + hw + 2].sum()) < CLOSE_WHITE_MIN:
                continue
            if int(white[cy - 3:cy + 4, cx - 3:cx + 4].sum()) < CLOSE_CENTER_WHITE_MIN:
                continue
            cands.append((cx, cy))
    if not cands:
        return None
    return max(cands)


# ==========================================================================
# 侧页返回箭头 (从 pages/base.py L370-408 抽出)
# ==========================================================================
BACK_ARROW_BOX = (8, 925, 120, 1002)
BACK_ARROW_MIN_PX = 150
BACK_ARROW_MAX_PX = 2000


def back_arrow_pos(img):
    """侧页返回箭头 -> (x, y) 可点落点; 这一帧没有箭头(或那是整片青底) -> None"""
    import numpy as np
    x0, y0, x1, y1 = BACK_ARROW_BOX
    a = np.asarray(img.convert('RGB'), dtype=np.int16)[y0:y1, x0:x1]
    if a.size == 0:
        return None
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    cyan = (b > 220) & (g >= 160) & (r < 190) & ((g.astype(int) - r.astype(int)) > 30)
    n = int(cyan.sum())
    if not BACK_ARROW_MIN_PX <= n <= BACK_ARROW_MAX_PX:
        return None
    ys, xs = np.nonzero(cyan)
    return int(x0 + (xs.min() + xs.max() + 1) // 2), int(y0 + (ys.min() + ys.max() + 1) // 2)


def is_back_arrow(img):
    """这一帧是否有侧页返回箭头"""
    return back_arrow_pos(img) is not None


# ==========================================================================
# 新手引导 (从 pages/base.py L410-518 抽出)
# ==========================================================================
GUIDE_TIP_BOX = (180, 720, 380, 800)      # 文本提示气泡取样框
GUIDE_TIP_MIN_WHITE = 500
GUIDE_HAND_BOX = (300, 820, 380, 920)     # 新手引导手形取样框
GUIDE_HAND_MIN_PX = 80
GUIDE_BLACK_MIN = 0.35                    # 压暗帧平均亮度上限 (整张图)


def guide_modal(img):
    """新手引导模态 -> (modal_type, targets)"""
    import numpy as np
    a = to_arr(img)
    h, w = a.shape[:2]
    mean = float(a[:h // 2].mean())
    if mean > 200:                                # 全亮: 没压暗
        return None, []
    # 上半部分有白色提示气泡
    y0, y1, x0, x1 = GUIDE_TIP_BOX
    tip_region = a[y0:min(y1, h), x0:min(x1, w), :3]
    if tip_region.size == 0:
        return None, []
    tip_white = int((tip_region.max(axis=2) > 200).sum())
    has_tip = tip_white > GUIDE_TIP_MIN_WHITE
    # 下半部分有黑色手形
    y0, y1, x0, x1 = GUIDE_HAND_BOX
    hand_region = a[y0:min(y1, h), x0:min(x1, w), :3]
    if hand_region.size == 0:
        return None, []
    hand_dark = int((hand_region.max(axis=2) < 80).sum())
    has_hand = hand_dark > GUIDE_HAND_MIN_PX
    if has_tip and has_hand:
        return 'tip+hand', _guide_targets(a, w, h)
    if has_tip:
        return 'tip', _guide_targets(a, w, h)
    if has_hand:
        return 'hand', _guide_targets(a, w, h)
    return 'dim-only', []


def hand_pos(img, box=None):
    """新手引导手形位置 -> (x, y) | None"""
    import numpy as np
    a = to_arr(img)
    h, w = a.shape[:2]
    y0, y1, x0, x1 = box or GUIDE_HAND_BOX
    reg = a[y0:min(y1, h), x0:min(x1, w), :3]
    if reg.size == 0:
        return None
    m = reg.max(axis=2) < 80
    if int(m.sum()) < GUIDE_HAND_MIN_PX:
        return None
    ys, xs = np.nonzero(m)
    return int(x0 + (xs.min() + xs.max() + 1) // 2), int(y0 + (ys.min() + ys.max() + 1) // 2)


def guide_targets(img):
    """新手引导所有落点 (手形 + 文本按钮位置)"""
    _, targets = guide_modal(img)
    return targets


def _guide_targets(arr, w, h):
    """内部: 从引导区域算所有可点落点"""
    return []  # 默认返回空, 实际落点由调用方算


# ==========================================================================
# 转场闸门 (从 pages/base.py L520-557 抽出)
# ==========================================================================
TRANSITION_WHITE_FRAC_MIN = 0.7   # 白烟帧白像素比例下限 (整张图)


def frame_stats(img):
    """帧统计 (mean, std). 用于压暗/过场检测"""
    import numpy as np
    a = to_arr(img).astype(float)
    return float(a.mean()), float(a.std())


def is_transition(img):
    """这一帧是否转场帧?(白烟/黑屏)"""
    import numpy as np
    a = to_arr(img)
    mean, _ = frame_stats(img)
    if mean < 30:                   # 黑屏
        return True, '黑屏'
    white_frac = float((a.max(axis=2) > 200).mean())
    if white_frac > TRANSITION_WHITE_FRAC_MIN:  # 白烟
        return True, '白烟'
    return False, ''


__all__ = [
    # 关闭徽章
    'find_close_badge',
    'CLOSE_RED_MIN_PX', 'CLOSE_RED_MAX_PX', 'CLOSE_BOX_MIN', 'CLOSE_BOX_MAX',
    'CLOSE_WHITE_MIN', 'CLOSE_RIGHT_MARGIN', 'CLOSE_CENTER_WHITE_MIN',
    # 返回箭头
    'back_arrow_pos', 'is_back_arrow',
    'BACK_ARROW_BOX', 'BACK_ARROW_MIN_PX', 'BACK_ARROW_MAX_PX',
    # 引导
    'guide_modal', 'hand_pos', 'guide_targets',
    'GUIDE_TIP_BOX', 'GUIDE_TIP_MIN_WHITE', 'GUIDE_HAND_BOX', 'GUIDE_HAND_MIN_PX', 'GUIDE_BLACK_MIN',
    # 转场
    'is_transition', 'frame_stats', 'TRANSITION_WHITE_FRAC_MIN',
]