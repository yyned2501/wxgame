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

    # 点色指纹: 由 tools/pick_print.py pick --label battle 自动标定(勿手改)
    # 3 种形态 x 3 个十字单元(每单元 5 点, 共 15 判色点/形态), 任一形态全中即判为 battle; 语料 13/13 全中 / 异页误中 0 / margin 0.20(异页最高只中 3/15 点) / 各形态覆盖 [13, 2, 1] 帧
    prints = (
        (   # 形态: battle_full/exp_battle0/exp_click50...
            [292, 60, 0xFFFFFF], [294, 60, 0xCCCBCB], [290, 60, 0xF0F0F0],
            [292, 62, 0x919090], [292, 58, 0xB5A5A5], [152, 108, 0xFFFFFF],
            [154, 108, 0xFDFDFD], [150, 108, 0x979A9C], [152, 110, 0xCFCFCF],
            [152, 106, 0xFFFFFF], [96, 112, 0xFFFFFF], [98, 112, 0xF4F4F4],
            [94, 112, 0xFCFCFC], [96, 114, 0x669BB4], [96, 110, 0x658DA0],
        ),
        (   # 形态: watch_124607/watch_124633
            [292, 60, 0xFFFFFF], [294, 60, 0xCCCBCB], [290, 60, 0xF0F0F0],
            [292, 62, 0x919090], [292, 58, 0xB5A5A5], [396, 104, 0xFFFFFF],
            [398, 104, 0xFDFDFD], [394, 104, 0xFFFFFF], [396, 106, 0x782629],
            [396, 102, 0xBABABA], [152, 108, 0xFFFFFF], [154, 108, 0xFDFDFD],
            [150, 108, 0x979A9C], [152, 110, 0xCFCFCF], [152, 106, 0xFFFFFF],
        ),
        (   # 形态: sample4
            [292, 60, 0xFFFFFF], [294, 60, 0xCCCBCB], [290, 60, 0xF0F0F0],
            [292, 62, 0x919090], [292, 58, 0xB5A5A5], [456, 104, 0xFFFFFF],
            [458, 104, 0x825C5D], [454, 104, 0xAAAAAA], [456, 106, 0xFFFFFF],
            [456, 102, 0x978080], [152, 108, 0xFFFFFF], [154, 108, 0xFDFDFD],
            [150, 108, 0x979A9C], [152, 110, 0xCFCFCF], [152, 106, 0xFFFFFF],
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
        # 防护: 扫描兜底路径下(没有"时间"文字)至少要能看到矿, 防止点到大厅横幅数字
        if not ctx.f.has('时间', '时间剩余') and not any(c['mine'] for c in cells):
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