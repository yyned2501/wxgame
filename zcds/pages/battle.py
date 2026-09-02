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
    # 2 种形态 x 5 个十字单元(每单元 5 点, 共 25 判色点/形态), 任一形态全中即判为 battle; 语料 70/70 全中 / 异页误中 0 / margin 0.16(异页最高只中 4/25 点) / 各形态覆盖 [13, 57] 帧
    prints = (
        (   # 形态: shots/battle_full/shots/exp_battle0/shots/exp_click50...
            [68, 194, 0xFFFFFF], [70, 194, 0x852326], [66, 194, 0x8C4D4E],
            [68, 196, 0xFDFDFD], [68, 192, 0xFFFFFF], [504, 210, 0xFFFFFF],
            [506, 210, 0xFFFFFF], [502, 210, 0xFFFFFF], [504, 212, 0xFFFFFF],
            [504, 208, 0x979797], [212, 774, 0xFFFFFF], [214, 774, 0xFFFFFF],
            [210, 774, 0xFFFFFF], [212, 776, 0xFFFFFF], [212, 772, 0xFFFFFF],
            [276, 814, 0xFFFFFF], [278, 814, 0xFFFFFF], [274, 814, 0xEEEEEE],
            [276, 816, 0xFFFFFF], [276, 812, 0xFFFFFF], [40, 866, 0xFFFFFF],
            [42, 866, 0x9B9B9B], [38, 866, 0x6C6C6C], [40, 868, 0xB1B1B1],
            [40, 864, 0xB6B6B6],
        ),
        (   # 形态: shots/battle_live_004258/shots/battle_live_004301/shots/battle_live_004305...
            [48, 214, 0xFFFFFF], [50, 214, 0xFFFFFF], [46, 214, 0xFFFFFF],
            [48, 216, 0xFFFFFF], [48, 212, 0xFFFFFF], [500, 214, 0xFFFFFF],
            [502, 214, 0xFFFFFF], [498, 214, 0xD2D2D2], [500, 216, 0xFFFFFF],
            [500, 212, 0xF9F9F9], [52, 870, 0xFFFFFF], [54, 870, 0xFFFFFF],
            [50, 870, 0xFFFFFF], [52, 872, 0x959595], [52, 868, 0xF5F5F5],
            [48, 822, 0xFEFEFE], [50, 822, 0xFEFEFE], [46, 822, 0xFEFEFF],
            [48, 824, 0xF9F9FA], [48, 820, 0x767683], [464, 814, 0xF9FEFE],
            [466, 814, 0xF9FEFE], [462, 814, 0xC5CACA], [464, 816, 0xF9FEFE],
            [464, 812, 0xB4B7B7],
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
