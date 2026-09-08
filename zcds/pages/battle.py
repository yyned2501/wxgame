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
# 单帧最多点几格. 2026-09-07 真机: per-cell 冷却下 20 格白棋盘仍 1.1s/格, 钱溢出;
# 改 2 后理论每步 2 格, 20 格一圈 11s。改 3/4 需真机验证游戏是否接受瞬时多点。
CELLS_PER_STEP = 2
# 技能自动释放(2026-09-07 用户定案): 左下角技能图标亮起 -> 拖到屏幕中间释放。
SKILL_ICON = (493, 937)                # 技能图标中心(右下角按钮, 实测 2026-09-08)
SKILL_TARGET = (276, 500)              # 释放目标(屏幕中央, 窗口 552x1006)
SKILL_BRIGHT_THRESHOLD = 145           # 旧版灰度阈值, 弃用
SKILL_BRIGHT_POINTS = [(35, 720), (45, 720), (55, 720), (45, 730)]  # 旧版 4 点, 弃用
# 2026-09-08 用户定案: 技能图标在右下角, 右上角有数字时可释放. 多次修正位置/颜色:
#   - 第一版: 红像素 (R>200 G<80 B<80) → 实际是血条/伤害数字, 不是徽章
#   - 第二版: 橙色 (R>200 G 100-200 B<80) → 位置错 (扫 (405,879) 不是徽章)
#   - 最终: 宽白像素 (R>180 G>180 B>180) >= 50, 区域 (500..545, 870..910)
#   实测: A("1")=72 / B("1")=71 / C("0")=22, 阈值 50 留安全余量
# 技能释放按点格子累计次数(2026-09-08 用户定案: 开了 8/20/50 个格子后释放).
SKILL_MILESTONES = (8, 20, 50)         # 三次释放时机: 累计点格子达 8/20/50 时各放一次
BATTLE_CLICKS = [0]                    # 本场战斗累计点格子数(模块级, _BLIND_STREAK 同款)
_LAST_SKILL_MILESTONE = [0]            # 已触发的最大里程碑(防重复触发)


def reset_battle_clicks():
    """进战斗页时清零(由 auto_bot 调用). 同步清技能释放计数."""
    BATTLE_CLICKS[0] = 0
    _LAST_SKILL_MILESTONE[0] = 0
SKILL_DRAG_STEPS = 10                  # 拖动步数
# 「本帧一个可点格子都没有」这条日志的最小间隔: 同一局每隔 3s 就会扫到一次, 不节流会刷屏
EMPTY_NOTE_EVERY = 20.0
# 上一条「无可点」日志的时刻(模块级 = 页面实例怎么建都不影响节流)
_LAST_EMPTY_NOTE = [0.0]
# 连续「整帧一个价签都没扫到」(白=0 且红=0) 的帧数。真机 R41 实测这种形状两次都出现在
# **刚进战斗场的第一帧**(14:21:25 / 14:29:13, 3s 后就扫到 4~5 个格子) = 棋盘还没翻开,
# 不是判据瞎 => 报警要连续 >= BLIND_ALARM_AFTER 帧才许响, 别把发牌帧误报成 bug
_BLIND_STREAK = [0]
BLIND_ALARM_AFTER = 2


def reset_blind_streak():
    """进入战斗页时清零(auto_bot 调用)。streak 的语义 = "同一场连续零价签帧":
    真机 R42 实测上一局收场动画压住棋盘 2 帧(21:20:52/55) + 新一局发牌帧 1 帧(21:21:21)
    跨场累到 3 -> 误报"判据又瞎了"(其实下一帧就扫到 5 格)。收场帧与发牌帧都是设计内盲区,
    不该跨场次记账; 真瞎的判据在同一场内 3s 一轮必然连续复发, 清零不会把它藏掉。"""
    _BLIND_STREAK[0] = 0

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
        r"""本帧一个可点格子都没有 -> 记进日志, 并说清是「买不起」还是「看不见」。

        为什么非记不可: 这两种形状以前在日志里长得一模一样(什么都不留, 整局安静几十秒)。
        2026-09-04 为回答用户「战斗中都不会点格子了」到底是哪种, 只能把整轮 269 张 battle
        语料逐帧重扫(见 COLORPRINT.md §34.7)。红标签本来就扫得到, 顺手记下来即可。
        尾巴复用 tier_census 的格式(`在架0 可点0 红N`), 按 `在架(\d+)` 抓日志的工具不用改。

        R41(1200 步 / 687 次点格子)实测这一条报了 60 次: 58 次「钱不够」+ 2 次整盘零价签,
        而那 2 次都在刚进场的第一帧 => 零价签先按「棋盘还没翻开」提示, 连续 >=2 帧才升级成
        「判据可能又瞎了」的报警。
        """
        red = sum(1 for c in cells if c['cls'] == 'red')
        # 先记账再看节流: 被节流吃掉的那些帧同样证明"这一帧还是啥都没扫到"
        _BLIND_STREAK[0] = 0 if red else _BLIND_STREAK[0] + 1
        if now - _LAST_EMPTY_NOTE[0] < EMPTY_NOTE_EVERY:
            return
        _LAST_EMPTY_NOTE[0] = now
        if red:
            tail = '钱不够, 正常(等金币攒出来)'
        elif _BLIND_STREAK[0] >= BLIND_ALARM_AFTER:
            tail = ('连红标签都没有(连续%d帧整盘零价签): 判据可能又瞎了, '
                    '查 battle_scan.white_mask' % _BLIND_STREAK[0])
        else:
            tail = '整盘零价签(多半刚进场棋盘还没翻开, 连续%d帧, 下一帧再看)' % _BLIND_STREAK[0]
        logging.info('[战斗] 无可点 | %s -> %s',
                     tier_census([], ctx.clicked_cells, red), tail)

    def _skill_ready(self, ctx):
        """用 ctx.clicked_cells 长度(被点过且未解禁的格子key)作为成功开格数(2026-09-08 用户定案).
        每场战斗最多 3 次 (8/20/50), _LAST_SKILL_MILESTONE 防重.
        """
        success = len(ctx.clicked_cells)
        next_milestone = None
        for m in SKILL_MILESTONES:
            if success >= m and _LAST_SKILL_MILESTONE[0] < m:
                next_milestone = m
                break
        if next_milestone is None:
            return False, success
        return True, success

    def _cast_skill(self, ctx):
        """成功开格数达 8/20/50 时释放技能(2026-09-08 用户定案). 按计数判据自然节流, 每场最多 3 次."""
        ready, success = self._skill_ready(ctx)
        if not ready:
            return False
        # 找下一个未触发的里程碑
        next_m = next(m for m in SKILL_MILESTONES
                      if success >= m and _LAST_SKILL_MILESTONE[0] < m)
        x1, y1 = SKILL_ICON
        x2, y2 = SKILL_TARGET
        ctx.drag(x1, y1, x2, y2, steps=SKILL_DRAG_STEPS, hold_each=0.02)
        _LAST_SKILL_MILESTONE[0] = next_m
        logging.info('[技能] 释放! 成功开格数=%d 触发里程碑=%d, 拖 (%d,%d)->(%d,%d) 步数=%d',
                     success, next_m, x1, y1, x2, y2, SKILL_DRAG_STEPS)
        return True

    def act(self, ctx):
        cells = scan_battle_cells(ctx.f.img)
        # 防护: 点色指纹已全中 = 确认在战斗页, 直接放行(不为此跑 OCR, 省 ~315ms);
        #       只有靠颜色扫描兜底定页时, 才要求看到 >=2 个格子图标, 防止点到大厅横幅数字
        if (not ctx.print_confirmed and not ctx.f.has('时间', '时间剩余')
                and sum(1 for c in cells if c['icon']) < 2):
            return False
        # 技能释放 暂停 (<< 2026-09-08 用户定案“先关掉”)
        # 5 轮徽章数字识别都失败, 格子数 8/20/50 不等于技能能量槽, 拖动无效现象严重
        # 代码保留在 _skill_ready/_cast_skill, 不调用. 重启时只要去掉这块注释即可.
        # self._cast_skill(ctx)
        # cls=3 = 认不出价钱的三位数块(实测是左下角"镜头复位"按钮的中文), 绝不点
        clickable = [c for c in cells if c['white'] and c['cls'] != 3]
        now = time.time()
        if not clickable:
            self._note_no_cell(ctx, cells, now)
            return False
        _BLIND_STREAK[0] = 0   # 这帧扫到了可点格子 = 眼睛没问题
        # 注: 旧版这里有 `if now - ctx.last_cell < CELL_COOLDOWN: return False` 的全局 2.5s 冷却,
        # 导致 20 格白棋盘也 2.5s 才出 1 手, 钱溢出。真机 2026-09-07 验证: 删掉之后 per-cell 由
        # `clicked_cells` 字典 + 下面 `if key in ctx.clicked_cells: continue` 自然处理 (25s 解禁),
        # 不同格可以连点, 同一格要等 25s 才能回头重试 —— 比全局冷却还更安全。
        # clicked_cells 是 {格子key: 点击时刻}: 先清掉过期条目, 再按档位找能点的格子
        expired = [k for k, t in ctx.clicked_cells.items() if now - t > CELL_RETRY]
        for k in expired:
            del ctx.clicked_cells[k]
        clickable.sort(key=rank_cell)
        # 必须逐个往后找. 旧版只看第一名, 第一名点过一次就整轮 return False ->
        # 真机 12:11:07~12:12:42 连续 95s 一次手都没出, 而当时棋盘上还有 14 个白色格子
        # 2026-09-07 改造: 单帧收集 CELLS_PER_STEP 格后再统一 click + log, 让一帧多吃几格消化钱
        skipped = 0
        to_click = []   # [(cx, cy, key, cell), ...] 按档位排序, 最多 CELLS_PER_STEP 个
        for c in clickable:
            cx, cy = c['x'] + c['w'] // 2, c['y'] + c['h'] // 2
            key = cell_key(c)
            if key in ctx.clicked_cells:
                skipped += 1
                continue
            to_click.append((cx, cy, key, c))
            if len(to_click) >= CELLS_PER_STEP:
                break
        if not to_click:
            logging.debug('[战斗] 全部白色格子都在冷却中')
            return False
        # 盘点要在写冷却表**之前**算, 这样「可点」里含本帧要点的所有格
        census = tier_census(clickable, ctx.clicked_cells,
                             sum(1 for c in cells if c['cls'] == 'red'))
        extra = ''
        if skipped:
            extra += ' 跳过已点%d格' % skipped
        if expired:
            extra += ' 解禁%d格' % len(expired)
        # 写冷却表 + 一次性多点 + 逐行 log (census 只在最后一行, 避免刷屏)
        # 真机 2026-09-07: 两次 click 间没停顿, 游戏触摸层把 cursor A→B+立即 DOWN 识别成 swipe/drag。
        # 加 150ms 间隙让 UP 后有明显停顿 (>cursor move 的 5ms), 触摸事件独立。460ms 仍远 < poll=1.0s。
        for i, (cx, cy, key, c) in enumerate(to_click):
            ctx.clicked_cells[key] = now
            ctx.click(cx, cy)
            BATTLE_CLICKS[0] += 1                   # 累计本场点格子数(给技能释放判据用)
            if i < len(to_click) - 1:
                time.sleep(0.15)
            tail = census if i == len(to_click) - 1 else ''
            tag = f'连点{i+1}/{len(to_click)}' if len(to_click) > 1 else '点格子'
            logging.info(f'[战斗] {tag} ({cx},{cy}) {c["icon"]} cls={c["cls"]} '
                         f'clip={c["clip"]}{extra} | {tail}')
        return True


