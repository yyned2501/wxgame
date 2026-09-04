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
# 「本帧一个可点格子都没有」这条日志的最小间隔: 同一局每隔 3s 就会扫到一次, 不节流会刷屏
EMPTY_NOTE_EVERY = 20.0
# 上一条「无可点」日志的时刻(模块级 = 页面实例怎么建都不影响节流)
_LAST_EMPTY_NOTE = [0.0]
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


def tier_census(clickable, clicked, red=0):
    """本帧白色格子的档位盘点, 直接拼进日志, 给真机复盘用。

    为什么需要: 用户最初的诉求是「战斗中只会开 25 的」, 但旧日志只报**点中的那一个**,
    事后没法回答「点 25 的时候棋盘上还有没有没点过的 50」—— 只能靠「跳过已点 N 格」猜。
    现在一行同时给出 `在架`(本帧全部白色格子) / `可点`(扣掉冷却中的) / `红` / 分档计数,
    只统计**还能点**的档, 因为冷却里的格子本来就不该再点一次。

    `红` = 本帧红色标签(钱不够, 点不了)的个数 —— 2026-09-04 修白标签判据那一轮,
    「判据瞎了看不见格子」和「看得见但买不起」在日志里长得一模一样(都是 在架 从 6 掉到 1),
    只能靠逐帧复核分清, 花了两小时。多这一列, 是眼睛的问题还是钱包的问题一眼可分。
    """
    free = [c for c in clickable if cell_key(c) not in clicked]
    cnt = collections.Counter(TIER_NAMES[rank_cell(c)[0]] for c in free)
    parts = ' '.join('%s:%d' % (n, cnt[n]) for n in TIER_NAMES if n in cnt)
    return '在架%d 可点%d 红%d%s' % (len(clickable), len(free), red,
                                     ' ' + parts if parts else '')


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
    # 点色指纹 2026-09-04 手工标定, 取代 tools/pick_print.py 自动版。
    # 为什么不用自动版: 它给的 5 个十字单元全落在 HUD 文字/数字上(奖杯数 (68,194)、
    #   倒计时 (268,66)、玩家名 (152,106)), 语料里恰好没变过所以报"70/70 全中",
    #   真机上一换对手/一变分数就整帧失效 -> 09-04 02:18 日志里 battle 仍然 100%
    #   走全图 OCR(0.90), 点一个格子要 ~16s。
    # 标定口径(own 74 帧 = shots/battle*.png 58 + shots_live/ocr_battle_*.png 16;
    #   异页 528 帧零误中):
    #   1) 跨帧逐通道极差<=19 的像素只占全帧 4%: 战斗页除了 y=131..140 这一行推条填充,
    #      其余(岩浆地图/六角格/单位/金币胶囊/头像/倒计时)全在动 [battle_diag.py, rows.py]
    #   2) 活下来的单元再过 ±2px 整帧平移: 74 帧各 roll 到 8 个偏移上, 要求 9 份数据全部
    #      74/74 命中 [z1.py]。金币图标在这关全灭 —— 胶囊宽度随数字位数变(61/525/685),
    #      整枚币左右平移 ~5px; 头像/奖杯数/倒计时是变化文字, 按语义人工否决
    #   3) 蓝红分界自己会左右扫(74 帧里蓝方右边界 188..408 [bnd.py]), 单形态必在逆风帧
    #      掉光 -> 两种形态并存, best_print 取两形最强分, 只要分界不同时越过 194 与 392
    #      就必有一形全中: 形A 吃顺风(蓝条), 形B 吃逆风(红条), 两形都带右下聊天气泡
    prints = (
        (   # 形A: 蓝条填充 x=138,190 @y=135 + 聊天气泡 x=482 @y=820
            [138, 135, 0x1D8BD2], [140, 135, 0x1D8BD2], [136, 135, 0x1D8BD2], [138, 137, 0x198AD3],
            [138, 133, 0x208BCE], [190, 135, 0x1D8BD2], [192, 135, 0x1D8BD2], [188, 135, 0x1D8BD2],
            [190, 137, 0x198AD3], [190, 133, 0x218CCF], [482, 820, 0xF9FEFE], [484, 820, 0xF9FEFE],
            [480, 820, 0xF9FEFE], [482, 822, 0xF9FEFE], [482, 818, 0xF9FEFE],
        ),
        (   # 形B: 红条填充 x=396,416 @y=135 + 聊天气泡 x=482 @y=820
            [396, 135, 0xC61F25], [398, 135, 0xC61F25], [394, 135, 0xC61F25], [396, 137, 0xC51D23],
            [396, 133, 0xC62026], [416, 135, 0xC61F25], [418, 135, 0xC61F25], [414, 135, 0xC61F25],
            [416, 137, 0xC51D23], [416, 133, 0xC62026], [482, 820, 0xF9FEFE], [484, 820, 0xF9FEFE],
            [480, 820, 0xF9FEFE], [482, 822, 0xF9FEFE], [482, 818, 0xF9FEFE],
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

    def _note_no_cell(self, ctx, cells, now):
        """本帧一个可点格子都没有 -> 记进日志, 并说清是「买不起」还是「看不见」。

        为什么非记不可: 这两种形状以前在日志里长得一模一样(什么都不留, 整局安静几十秒)。
        2026-09-04 为回答用户「战斗中都不会点格子了」到底是哪种, 只能把整轮 269 张 battle
        语料逐帧重扫(见 COLORPRINT.md §34.7)。红标签本来就扫得到, 顺手记下来即可。
        尾巴复用 tier_census 的格式(`在架0 可点0 红N`), 按 `在架(\d+)` 抓日志的工具不用改。
        """
        red = sum(1 for c in cells if c['cls'] == 'red')
        if now - _LAST_EMPTY_NOTE[0] < EMPTY_NOTE_EVERY:
            return
        _LAST_EMPTY_NOTE[0] = now
        logging.info('[战斗] 无可点 | %s -> %s',
                     tier_census([], ctx.clicked_cells, red),
                     '钱不够, 正常(等金币攒出来)' if red
                     else '连红标签都没有: 判据可能又瞎了, 查 battle_scan.white_mask')

    def act(self, ctx):
        cells = scan_battle_cells(ctx.f.img)
        # 防护: 点色指纹已全中 = 确认在战斗页, 直接放行(不为此跑 OCR, 省 ~315ms);
        #       只有靠颜色扫描兜底定页时, 才要求看到 >=2 个格子图标, 防止点到大厅横幅数字
        if (not ctx.print_confirmed and not ctx.f.has('时间', '时间剩余')
                and sum(1 for c in cells if c['icon']) < 2):
            return False
        # cls=3 = 认不出价钱的三位数块(实测是左下角"镜头复位"按钮的中文), 绝不点
        clickable = [c for c in cells if c['white'] and c['cls'] != 3]
        now = time.time()
        if not clickable:
            self._note_no_cell(ctx, cells, now)
            return False
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
            census = tier_census(clickable, ctx.clicked_cells,
                                 sum(1 for c in cells if c['cls'] == 'red'))
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
