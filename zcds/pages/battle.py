# -*- coding: utf-8 -*-
"""战斗页: 自动点格子. 用颜色扫描做识别(无 OCR, ~10ms/次)

策略(用户 2026-09-03 指定):
  1) 只点白色价格标签(钱够可点), 红色=钱不够跳过
  2) 先开 50 的矿, 再开 50 的兵营, 再考虑 25 的, 都没有就开 100 的
  3) 第一名点过就换第二名(不是整轮不动手); 拉黑只保持 CELL_RETRY 秒
"""
import logging, time, collections

try:
    from ..battle_scan import scan_battle_cells
except ImportError:
    from battle_scan import scan_battle_cells
from .base import Page

TOWER = (276, 800)
# 两次点格子的最小间隔. battle 页 poll=3.0s(config.py), 旧的 5s 等于每两轮才出手一次
CELL_COOLDOWN = 2.5
# 点过的格子拉黑多久. 到期后允许回头再点(同一格升级/开新的);
# 镜头平移后同一格会落在新坐标 -> 自然就是新 key, 不受旧条目影响
CELL_RETRY = 25.0


# 用户指定顺序: 50矿 > 50兵营 > 50问号 > 25 > 100 > 250 > 认不出价钱的
# (旧版是 "矿 > 50 > 2d > 25", 而 2d 这个桶几乎装下了所有格子 -> 真机上等于只按 y 点, 25 先被点光)
PRICE_TIER = {25: 3, 100: 4, 250: 5}

TIER_NAMES = ['50矿', '50兵', '50问', '25', '100', '250', '分不清']
TIER_NAME = {i: n for i, n in enumerate(TIER_NAMES)}


def cell_key(c):
    """格子的冷却 key = 标签中心按 16px 取整(镜头平移后同一格会算成新 key, 这是故意的)"""
    return ((c['x'] + c['w'] // 2) // 16, (c['y'] + c['h'] // 2) // 16)


def tier_census(clickable, clicked):
    """本帧白色格子的档位盘点, 直接拼进日志, 给真机复盘用。

    为什么需要: 用户最初的诉求是「战斗中只会开 25 的」, 但旧日志只报**点中的那一个**,
    事后没法回答「点 25 的时候棋盘上还有没有没点过的 50」—— 只能靠「跳过已点 N 格」猜。
    现在一行同时给出 `在架`(本帧全部白色格子) / `可点`(扣掉冷却中的) / 分档计数,
    只统计**还能点**的档, 因为冷却里的格子本来就不该再点一次。
    """
    free = [c for c in clickable if cell_key(c) not in clicked]
    cnt = collections.Counter(TIER_NAMES[rank_cell(c)[0]] for c in free)
    parts = ' '.join('%s:%d' % (n, cnt[n]) for n in TIER_NAMES if n in cnt)
    return '在架%d 可点%d%s' % (len(clickable), len(free), ' ' + parts if parts else '')


def rank_cell(c):
    """点击优先级(越小越先点). cls 是 int: 25/50/100/250/3(认不出)"""
    if c['cls'] == 50:
        tier = {'ore': 0, 'barracks': 1}.get(c['icon'], 2)
    else:
        tier = PRICE_TIER.get(c['cls'], 6)
    # 同档内: 靠塔那一侧(右上, 兵线来的方向)先开, 再按行从下往上
    near_tower = 1 if (c['x'] + c['w'] // 2 >= TOWER[0] and c['y'] <= TOWER[1]) else 0
    return (tier, -near_tower, -c['y'])


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
        # 颜色扫描兜底: 需 >=2 行标签 且 至少 2 个格子带图标, 才算棋盘
        # (旧版要求"看到矿", 但全语料 1488 个白色标签里矿只占 14%, 大多数战斗帧根本看不到矿 ->
        #  兜底形同虚设; 大厅横幅/礼包弹窗的数字上方没有图标, 换成数图标仍然挡得住)
        try:
            cells = scan_battle_cells(f.img)
            rows = {c['y'] // 16 for c in cells}
            if len(rows) >= 2 and sum(1 for c in cells if c['icon']) >= 2:
                return 0.8
        except Exception:
            pass
        return 0.0

    def act(self, ctx):
        cells = scan_battle_cells(ctx.f.img)
        # 防护: 点色指纹已全中 = 确认在战斗页, 直接放行(不为此跑 OCR, 省 ~315ms);
        #       只有靠颜色扫描兜底定页时, 才要求看到 >=2 个格子图标, 防止点到大厅横幅数字
        if (not ctx.print_confirmed and not ctx.f.has('时间', '时间剩余')
                and sum(1 for c in cells if c['icon']) < 2):
            return False
        # cls=3 = 认不出价钱的三位数块(实测是左下角"镜头复位"按钮的中文), 绝不点
        clickable = [c for c in cells if c['white'] and c['cls'] != 3]
        if not clickable:
            return False
        now = time.time()
        if now - ctx.last_cell < CELL_COOLDOWN:
            return False
        # clicked_cells 是 {格子key: 点击时刻}: 先清掉过期条目, 再按档位找能点的格子
        expired = [k for k, t in ctx.clicked_cells.items() if now - t > CELL_RETRY]
        for k in expired:
            del ctx.clicked_cells[k]
        clickable.sort(key=rank_cell)
        # 必须逐个往后找. 旧版只看第一名, 第一名点过一次就整轮 return False ->
        # 真机 12:11:07~12:12:42 连续 95s 一次手都没出, 而当时棋盘上还有 14 个白色格子
        skipped = 0
        for c in clickable:
            cx, cy = c['x'] + c['w'] // 2, c['y'] + c['h'] // 2
            key = cell_key(c)
            if key in ctx.clicked_cells:
                skipped += 1
                continue
            # 盘点要在写冷却表**之前**算, 这样「可点」里含本帧要点的那一格
            census = tier_census(clickable, ctx.clicked_cells)
            ctx.clicked_cells[key] = now
            ctx.last_cell = now
            extra = ''
            if skipped:
                extra += ' 跳过已点%d格' % skipped
            if expired:
                extra += ' 解禁%d格' % len(expired)
            logging.info(f'[战斗] 点格子 ({cx},{cy}) {c["icon"]} cls={c["cls"]} '
                         f'clip={c["clip"]}{extra} | {census}')
            ctx.click(cx, cy)
            return True
        logging.debug('[战斗] 全部白色格子都在冷却中')
        return False
