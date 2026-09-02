# -*- coding: utf-8 -*-
"""战斗页: 自动点格子. 用颜色扫描做识别(无 OCR, ~10ms/次)

策略(用户确认):
  1) 只点白色价格标签(钱够可点), 红色=钱不够跳过
  2) 白色团+3条直线 = 矿(产钱) 优先
  3) 再点 50 兵营, 再 25 问号, 最后其他可点的
"""
import logging, time

try:
    from ..battle_scan import scan_battle_cells
except ImportError:
    from battle_scan import scan_battle_cells
from .base import Page

TOWER = (276, 800)
CELL_COOLDOWN = 5


def rank_cell(c):
    """点击优先级: 矿 > 50 > 2d(二位数分不清) > 25 > 3d"""
    if c['mine']:
        mine_zone = 1 if (c['x'] + c['w'] // 2 >= TOWER[0] and c['y'] <= TOWER[1]) else 0
        return (0, -mine_zone, -c['y'])
    if c['cls'] == '50':
        return (1, 0, -c['y'])
    if c['cls'] == '2d':
        return (2, 0, -c['y'])
    if c['cls'] == '25':
        return (3, 0, -c['y'])
    return (4, 0, -c['y'])


class BattlePage(Page):
    name = 'battle'
    next_pages = ('result',)
    act_needs_ocr = False     # 战斗页纯点色(颜色扫描 + 指纹), 一轮都不该碰 OCR
    # 点色指纹: 由 tools/pick_print.py pick --label battle 自动标定(勿手改)
    # 2 种形态 x 5 个十字单元(每单元 5 点, 共 25 判色点/形态), 任一形态全中即判为 battle; 语料 40/40 全中 / 异页误中 0 / margin 0.12 / 各形态覆盖 [13, 27] 帧
    prints = (
        (   # 形态: shots/battle_full/shots/exp_battle0/shots/exp_click50...
            [68, 192, 0xFFFFFF], [70, 192, 0x682F30], [66, 192, 0x904042],
            [68, 194, 0xFFFFFF], [68, 190, 0xCAC9C9], [500, 212, 0xFFFFFF],
            [502, 212, 0xFFFFFF], [498, 212, 0xB7B6B6], [500, 214, 0xFFFFFF],
            [500, 210, 0xCDCDCD], [212, 772, 0xFFFFFF], [214, 772, 0xFFFFFF],
            [210, 772, 0xFFFFFF], [212, 774, 0xFFFFFF], [212, 770, 0xFFFFFF],
            [80, 868, 0xFFFFFF], [82, 868, 0x6B6C6B], [78, 868, 0x667756],
            [80, 870, 0xF3F3F3], [80, 866, 0xDDDDDD], [60, 820, 0xFEFEFE],
            [62, 820, 0xFEFEFE], [58, 820, 0xEFEFEF], [60, 822, 0xFEFEFE],
            [60, 818, 0x587937],
        ),
        (   # 形态: shots/battle_live_004258/shots/battle_live_004301/shots/battle_live_004305...
            [72, 196, 0xFFFFFF], [74, 196, 0x7A749E], [70, 196, 0x595185],
            [72, 198, 0xEFEFF0], [72, 194, 0xFFFFFF], [504, 212, 0xFFFFFF],
            [506, 212, 0xFFFFFF], [502, 212, 0xFFFFFF], [504, 214, 0xFFFFFF],
            [504, 210, 0xFEFEFE], [456, 216, 0xFFFFFF], [458, 216, 0x686096],
            [454, 216, 0xE7E7E7], [456, 218, 0xFFFFFF], [456, 214, 0x716A98],
            [80, 868, 0xFFFFFF], [82, 868, 0x626262], [78, 868, 0xBCB8B5],
            [80, 870, 0xD9D9D9], [80, 866, 0xFCFCFC], [60, 820, 0xFEFEFE],
            [62, 820, 0xFEFEFE], [58, 820, 0xFBFBFB], [60, 822, 0xE7E7E7],
            [60, 818, 0xE9E9E9],
        ),
    )
    def detect(self, f):
        if f.has('时间', '时间剩余'):
            return 0.9
        # 大厅横幅/弹窗(购买礼包等)会有一排数字, 绝不能误判成战斗
        if f.has('购买礼包', '月卡', '特权', '超值', '七日'):
            return 0.0
        # 颜色扫描兜底: 需 >=2 行标签 且 识别到矿图标, 才算棋盘
        try:
            cells = scan_battle_cells(f.img)
            rows = {c['y'] // 16 for c in cells}
            if len(rows) >= 2 and any(c['mine'] for c in cells):
                return 0.8
        except Exception:
            pass
        return 0.0

    def act(self, ctx):
        cells = scan_battle_cells(ctx.f.img)
        # 防护: 点色指纹已全中 = 确认在战斗页, 直接放行(不为此跑 OCR, 省 ~315ms);
        #       只有靠颜色扫描兜底定页时, 才要求至少看到矿, 防止点到大厅横幅数字
        if (not ctx.print_confirmed and not ctx.f.has('时间', '时间剩余')
                and not any(c['mine'] for c in cells)):
            return False
        clickable = [c for c in cells if c['white']]
        if not clickable:
            return False
        if time.time() - ctx.last_cell < CELL_COOLDOWN:
            return False
        clickable.sort(key=rank_cell)
        c = clickable[0]
        cx, cy = c['x'] + c['w'] // 2, c['y'] + c['h'] // 2
        if (cx // 16, cy // 16) in ctx.clicked_cells:
            return False
        ctx.clicked_cells.add((cx // 16, cy // 16))
        ctx.last_cell = time.time()
        logging.info(f'[战斗] 点格子 ({cx},{cy}) mine={c["mine"]} cls={c["cls"]}')
        ctx.click(cx, cy)
        return True