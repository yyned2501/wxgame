# -*- coding: utf-8 -*-
"""点色指纹封装.

旧 `colorprint.py` 提供 rgb2c/print_score/tolerance/is_color/color_count/color_bbox 等函数.
这里封装成 Color 类. 内部 import colorprint 复用函数, 双轨运行.

注意: color_pixels/color_button 历史上在 pages/base.py (color_count/颜色的别名封装),
但底层 color_count/color_bbox 在 colorprint.py, 这里直接 re-export.

用法:
    color = Color()
    color.pixels(img, (x0, y0, x1, y1), 0xFDCA33)         # 数色块像素
    color.button(img, box, color, min_px)                 # 找按钮中心
    score = color.score(img, stamp, 90)                   # 点色打分
    ok = color.is_color(img, x, y, target_rgb, degree=90)  # 单点判色
"""
import colorprint as _cp  # 复用旧实现


class Color:
    """点色指纹封装."""

    REF_SIZE = _cp.REF_SIZE  # (W, H) 基准尺寸 552x1006

    def pixels(self, img, box, target_rgb, degree=90):
        """框内数 target_rgb 色像素数 (color_count 的别名, 与 pages/base 兼容)."""
        return _cp.color_count(img, box, target_rgb, degree=degree)

    def button(self, img, box, target_rgb, min_px=1, degree=90):
        """框内找一块足够大的目标色色块 -> (x, y) 点击点; 没找到返回 None."""
        r = _cp.color_bbox(img, box, target_rgb, degree, min_px)
        return None if r is None else (r[0], r[1])

    def bbox(self, img, box, target_rgb, degree=90, min_px=1):
        """框内找一块足够大的目标色色块 -> (x0, y0, x1, y1) 外接框; 没找到返回 None."""
        return _cp.color_bbox(img, box, target_rgb, degree, min_px)

    def mask(self, img, box, target_rgb, degree=90):
        """框内 RGB 容差内 True/False mask (numpy array)."""
        return _cp.color_mask(img, box, target_rgb, degree=degree)

    def count(self, img, box, target_rgb, degree=90):
        """框内 target_rgb 色像素数 (与 .pixels 同义, 更接近 color_count 原名)."""
        return _cp.color_count(img, box, target_rgb, degree=degree)

    def score(self, img, stamp, degree=90):
        """点色打分 (img 与 stamp 越接近分越高)."""
        return _cp.print_score(img, stamp, degree=degree)

    def is_match(self, img, stamp, degree=90, pos_tol=2):
        """点色指纹整体匹配 (十字 5 点模板)."""
        return _cp.is_multi_color(img, stamp, degree=degree, pos_tol=pos_tol)

    def is_color(self, img, x, y, target_rgb, degree=90):
        """单点 (x, y) 是否 target_rgb 色."""
        return _cp.is_color(img, x, y, target_rgb, degree=degree)

    def rgb_to_tuple(self, rgb_int):
        """24-bit RGB int -> (r, g, b) tuple."""
        return _cp.rgb2c(rgb_int)


# 模块级别名 (兼容 pages/base.py 老 import)
color_pixels = _cp.color_count
color_button = _cp.color_bbox