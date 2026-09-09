# -*- coding: utf-8 -*-
"""OCR + ScreenFeature 封装.

旧 `vision.py` 是全局模块, 提供 Vision 类 + ScreenFeature 数据类.
这里做轻量适配, 直接复用旧 Vision, 但导出 ScreenFeature 给 libs 用户。

用。

用法:
    vision = Vision(window)
    feature, ran_ocr = vision.ocr(img, region=None, scale=0.5, min_gap=10)
    # feature.boxes, feature.joined
"""
from vision import Vision, ScreenFeature  # 复用旧实现


# 重新导出, 让 libs 用户 from libs.vision import Vision, ScreenFeature
__all__ = ['Vision', 'ScreenFeature']