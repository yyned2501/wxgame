# -*- coding: utf-8 -*-
"""离线集成测试: 不依赖真实窗口. 验证 CPU 优化后主循环行为"""
import logging, os, sys
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image

import game_utils as g

D = os.path.dirname(os.path.abspath(__file__))
QUEUE = []

def fake_capture(hwnd):
    fn = QUEUE[0]
    im = Image.open(os.path.join(D, fn)).convert('RGB')
    return im, 1

def fake_find_window():
    return 12345

g.capture_window = fake_capture
g.find_game_window = fake_find_window
try:
    g.u32.IsWindow = lambda h: True
except Exception:
    pass

from auto_bot import App
from pages.base import select_page

app = App(dry_run=True, low_cpu=False)
app.ensure_window()
app.vision.refresh_hwnd(12345)

# ---------- 场景1: 连续两帧相同大厅 -> 第二次不 OCR ----------
QUEUE[:] = ['shots/lobby_clean.png', 'shots/lobby_clean.png']
p1, a1, o1 = app.step()
p2, a2, o2 = app.step()
print(f'[1] 大厅帧1: page={p1.name} acted={a1} ocr={o1}')
print(f'[1] 大厅帧2: page={p2.name} acted={a2} ocr={o2}  (期望 ocr=False, 指纹门控生效)')

# ---------- 场景2: 大厅 -> 宝箱弹窗 -> 应全图OCR识别 chest_info ----------
QUEUE[:] = ['shots/chestinfo.png']
p3, a3, o3 = app.step()
print(f'[2] 变到宝箱面板: page={p3.name} acted={a3} ocr={o3}  (期望 chest_info)')

# ---------- 场景3: 战斗: 用颜色扫描, 零OCR点击矿 ----------
app._act_gap = 0
app.clicked_cells = set()
app.last_cell = 0
QUEUE[:] = ['shots/battle_full.png', 'shots/battle_full.png', 'shots/battle_full.png']
p4, a4, o4 = app.step()
print(f'[3] 战斗帧1: page={p4.name} acted={a4} ocr={o4}  (期望 battle, 可能无OCR)')
p5, a5, o5 = app.step()
print(f'[3] 战斗帧2: page={p5.name} acted={a5} ocr={o5}  (期望 ocr=False)')
p6, a6, o6 = app.step()
print(f'[3] 战斗帧3: page={p6.name} acted={a6} ocr={o6}')

# ---------- 场景4: 战斗帧循环8次统计OCR次数 ----------
QUEUE[:] = ['shots/flow2_m0.png'] * 8
ocr_cnt = 0
for i in range(8):
    app.clicked_cells = set()
    app.last_cell = 0
    p, a, o = app.step()
    ocr_cnt += int(o)
print(f'[4] 战斗循环8次: OCR次数={ocr_cnt} (期望 0, 页面={p.name})')

# ---------- 场景5: 结算页(点击维续 容错) ----------
QUEUE[:] = ['shots/flow4_s0_result.png']
p7, a7, o7 = app.step()
print(f'[5] 结算页: page={p7.name} acted={a7} ocr={o7}  (期望 result)')

# ---------- 场景6: 沼泽: unknown页 ----------
QUEUE[:] = ['shots/flow_0_lobby.png']
app.vision.reset()
p8, a8, o8 = app.step()
print(f'[6] 大厅2: page={p8.name} acted={a8} ocr={o8}')
print('ALL DONE')
