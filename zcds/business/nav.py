# -*- coding: utf-8)'
"""底部一级导航栏业务 (从 pages/base.py L755-805 抽出).

含 4 个常量 + 3 个函数:
- nav_hits(img): 导航栏 16 个静态像素里命中了几个
- nav_present(img): 这帧底下有没有那条一级导航栏
- nav_tab_cx(img): 当前选中页签中心 x
- _is_cyan(px): 高亮板亮青描边判据

调用: from business.nav import nav_present, nav_tab_cx
旧代码兼容: from pages.base import nav_present (pages/base.py re-export)
"""
from colorprint import is_color, scale_points, to_arr


# ---- 底部一级导航栏 5 个页签 ----
NAV_TABS = [(50, 'shop'), (163, 'cards'), (276, 'battle'), (389, 'castle'), (502, 'rank')]
NAV_LOBBY_TAB = (276, 950)     # 中间页签 = 战斗 = 大厅
NAV_POINTS = [
    [156, 934, 0xFFB511], [144, 940, 0x2485FC], [192, 940, 0xA748FC], [166, 944, 0xFDA613],
    [172, 946, 0xFDA613], [194, 946, 0xA647FA], [182, 948, 0xC05F0D], [476, 952, 0xAC6411],
    [296, 930, 0xC1C8D8], [262, 932, 0xD8DCE4], [374, 936, 0xD6D6D6], [396, 934, 0xC1BEB7],
    [144, 942, 0x2787FC], [168, 942, 0xFDA813], [72, 942, 0x4153C6], [382, 936, 0xACADB3],
]
NAV_DEGREE = 92               # ±10, 比页面指纹(85)更严: 只用来判"导航栏在不在"
NAV_MIN_HIT = 12              # 语料 799 张实测: 带栏帧最低 14, 不带栏帧最高 9
NAV_SOFT_HIT = 9              # 供测试断言分界用: 低于这个数一律当"没有导航栏"
NAV_BAND = (905, 996)         # 选中页签高亮板的纵向范围


def _is_cyan(px):
    """高亮板那种亮青描边: 0x94DDFB / 0x66C8FE / 0x6CCBFF / 0x93DDFC 都算"""
    r, g, b = int(px[0]), int(px[1]), int(px[2])
    return b > 220 and g >= 160 and r < 190 and (g - r) > 30


def nav_hits(img):
    """导航栏 16 个静态像素里命中了几个"""
    arr = to_arr(img)
    pts = scale_points(NAV_POINTS, (arr.shape[1], arr.shape[0]))
    return sum(1 for x, y, c in pts if is_color(arr, x, y, c, NAV_DEGREE))


def nav_present(img):
    """这帧底下有没有那条一级导航栏(= 这是 5 个一级页之一)"""
    return nav_hits(img) >= NAV_MIN_HIT


def nav_tab_cx(img):
    """当前选中的是哪个页签 -> 它的中心 x; 认不出返回 None。
    只有被选中的页签背后有一块亮青描边的高亮板, 板边框正好穿过页签中心那一列
    (实测: 选中列 20~50 个青像素, 未选中列一律 0)。"""
    arr = to_arr(img)
    w, h = arr.shape[1], arr.shape[0]
    for cx, _name in NAV_TABS:
        if not 0 <= cx < w:
            continue
        n = sum(1 for y in range(NAV_BAND[0], min(NAV_BAND[1], h)) if _is_cyan(arr[y, cx]))
        if n >= 8:
            return cx
    return None


__all__ = ['nav_hits', 'nav_present', 'nav_tab_cx', '_is_cyan',
           'NAV_TABS', 'NAV_LOBBY_TAB', 'NAV_POINTS',
           'NAV_DEGREE', 'NAV_MIN_HIT', 'NAV_SOFT_HIT', 'NAV_BAND']