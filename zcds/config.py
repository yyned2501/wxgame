# -*- coding: utf-8 -*-
"""页面轮询/OCR 配置 (CPU 优化核心)

roi:     (fx0, fy0, fx1, fy1) 窗口坐标比例, None=全图
scale:   ROI 缩放比例(喂给 OCR)
poll:    主循环 sleep 间隔(秒)
ocr_gap: 两次 OCR 最小间隔(秒); 战斗用颜色扫描所以给超大值
"""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
SHOTS_DIR = os.path.join(ROOT, 'shots')      # 截图输出目录(兜底截图也写这里)

PAGE_CFG = {
    'lobby':        dict(roi=(0.0, 0.55, 1.0, 0.90), scale=0.6, poll=3.0, ocr_gap=10.0),
    'battle':       dict(roi=(0.0, 0.46, 1.0, 0.90), scale=0.5, poll=3.0, ocr_gap=600.0),
    'matching':     dict(roi=(0.0, 0.15, 1.0, 0.90), scale=0.5, poll=4.0, ocr_gap=8.0),
    'result':       dict(roi=None, scale=0.5, poll=3.0, ocr_gap=6.0),
    'chest_info':   dict(roi=(0.0, 0.10, 1.0, 0.90), scale=0.5, poll=3.0, ocr_gap=6.0),
    'claim_popup':  dict(roi=None, scale=0.5, poll=3.0, ocr_gap=6.0),
    'diamond_popup': dict(roi=None, scale=0.5, poll=3.0, ocr_gap=6.0),
    'vip_popup':    dict(roi=None, scale=0.5, poll=3.0, ocr_gap=6.0),
    'unknown':      dict(roi=None, scale=0.5, poll=8.0, ocr_gap=15.0),
}
