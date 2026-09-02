# -*- coding: utf-8 -*-
"""特征提取层: 抓帧(零 OCR) + 按需 OCR -> ScreenFeature

设计铁律: 点色优先。定页面、点哪里, 能用颜色就绝不碰 OCR。
真机实测(帧 552x1006, scratch/scripts/bench_route.py 2026-09-03):
  点色全表 2.2ms | 全图 OCR 675ms | 本页 ROI OCR 369ms
  => 点色比全图 OCR 快 ~309 倍, 一轮最多省 673ms
OCR 只留给"动作层非读文字不可"的页面(宝箱价格护栏/按钮文案), 且只裁本页 ROI。

CPU 优化:
  - onnxruntime 线程数在 ocr_config.yaml 限制(intra=2/inter=1), 峰值封顶
  - grab() 零 OCR: 只做 PrintWindow + 缩略图对比(几 ms)
  - ocr() 按需才调: 没到 min_gap / 画面没大变化就直接复用上轮文字(0ms)
"""
import os, time
from dataclasses import dataclass

import numpy as np

import game_utils as g
from battle_scan import scan_battle_cells as _scan_battle_cells

ROOT = os.path.dirname(os.path.abspath(__file__))
OCR_CONFIG = os.path.join(ROOT, 'ocr_config.yaml')

FP_SIZE = (46, 83)          # 指纹缩略图尺寸
FP_SMALL = 2.5              # 小变化门限(均值绝对差)
FP_BIG = 6.0                # 大变化门限: 弹窗/跳页


@dataclass
class TBox:
    text: str
    x: int
    y: int
    w: int
    h: int

    @property
    def cx(self):
        return self.x + self.w // 2

    @property
    def cy(self):
        return self.y + self.h // 2

    @property
    def center(self):
        return (self.cx, self.cy)


@dataclass
class ScreenFeature:
    img: object          # PIL.Image (最新一帧, 调试/扫描用)
    boxes: list          # list[TBox]
    joined: str          # 全部识别文字(空格连接)

    def find(self, key):
        return [b.center for b in self.boxes if key in b.text]

    def find_boxes(self, key):
        return [b for b in self.boxes if key in b.text]

    def has(self, *keys):
        j = self.joined
        return any(k in j for k in keys)

    def near(self, x, y, r=45):
        return [b for b in self.boxes if abs(b.cx - x) < r and abs(b.cy - y) < r]


class Vision:
    """抓帧 + 按需 OCR 引擎.

    主循环每轮 grab() (零 OCR); 只有 act() 声明需要文字的页面才再调 ocr().
    """

    def __init__(self, hwnd, config_path=None):
        self.hwnd = hwnd
        self.config_path = config_path or OCR_CONFIG
        self._ocr = None
        self._prev_fp = None
        self._cached = None
        self._cache_key = None        # 当前缓存对应的 (region, scale)
        self._last_ocr = 0.0
        self.changed_small = True
        self.changed_big = True

    # ---- OCR ----
    def _ensure_ocr(self):
        if self._ocr is None:
            from rapidocr_onnxruntime import RapidOCR
            self._ocr = RapidOCR(self.config_path)   # 线程数在 yaml 里限定

    # ---- 指纹 ----
    @staticmethod
    def _fingerprint(img):
        small = img.resize(FP_SIZE).convert('L')
        return np.asarray(small, dtype=np.int16)

    def grab(self):
        """抓一帧并更新变化门限(零 OCR, 真机实测 ~31ms)"""
        img, _ = g.capture_window(self.hwnd)
        fp = self._fingerprint(img)
        if self._prev_fp is None:
            self.changed_small = self.changed_big = True
        else:
            d = float(np.abs(fp - self._prev_fp).mean())
            self.changed_small = d > FP_SMALL
            self.changed_big = d > FP_BIG
        self._prev_fp = fp
        return img

    def reset(self):
        """换句柄/窗口被缩放: 旧特征与缓存全部作废"""
        self._prev_fp = None
        self.changed_small = self.changed_big = True
        self._cached = None
        self._cache_key = None

    def refresh_hwnd(self, hwnd):
        self.hwnd = hwnd
        self.reset()

    # ---- 主入口: 按需 OCR ----
    def ocr(self, img, region=None, scale=0.5, force=False, min_gap=6.0):
        """按需 OCR. 返回 (ScreenFeature, ocr_ran: bool)

        img    : grab() 拿到的当前帧(点色定页用不着它, 动作层要读字才调)
        region : (fx0,fy0,fx1,fy1) 坐标比例; None=全图
        换 ROI/缩放、force、画面大变化(跳页·弹窗)、超过 min_gap 才真跑一次 OCR,
        否则直接复用上轮文字坐标(ocr_ran=False) —— 省 CPU 全靠这一步。
        """
        now = time.time()
        key = (None if region is None else tuple(round(v, 3) for v in region), scale)
        due = (force or key != self._cache_key or self.changed_big
               or (now - self._last_ocr) >= min_gap)
        if not due and self._cached is not None:
            self._cached.img = img        # 画面基本没变, 旧文字坐标仍有效
            return self._cached, False
        self._ensure_ocr()
        w, h = img.size
        if region is None:
            crop = img
            ox = oy = 0
        else:
            fx0, fy0, fx1, fy1 = region
            ox, oy = int(fx0 * w), int(fy0 * h)
            crop = img.crop((ox, oy, int(fx1 * w), int(fy1 * h)))
        tw = max(8, int(crop.size[0] * scale))
        th = max(8, int(crop.size[1] * scale))
        res, _ = self._ocr(crop.resize((tw, th)))
        boxes = []
        if res:
            inv = 1.0 / scale
            for box, text, score in res:
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                x0, y0 = int(min(xs) * inv) + ox, int(min(ys) * inv) + oy
                x1, y1 = int(max(xs) * inv) + ox, int(max(ys) * inv) + oy
                boxes.append(TBox(text, x0, y0, x1 - x0, y1 - y0))
        self._cached = ScreenFeature(img=img, boxes=boxes, joined=' '.join(b.text for b in boxes))
        self._cache_key = key
        self._last_ocr = now
        return self._cached, True

    def current(self, region=None, scale=0.5, force=False, min_gap=6.0):
        """兼容旧调用(取证/离线脚本): 自己抓一帧再按需 OCR"""
        return self.ocr(self.grab(), region, scale, force, min_gap)

    # ---- 战斗颜色扫描(无 OCR) ----
    @staticmethod
    def cells(img):
        return _scan_battle_cells(img)
