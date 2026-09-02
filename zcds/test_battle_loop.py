# -*- coding: utf-8 -*-
"""离线回归: 连续两场战斗之间必须清空 clicked_cells (不开窗口 / 不真点击)

缺陷(2026-08-31 实测出来的):
  ctx.clicked_cells 只在 auto_bot.py __init__ 里初始化一次, 全项目没有任何一处清空它,
  而 pages/battle.py 用 "if (cx//16, cy//16) in ctx.clicked_cells: return False" 跳过点过的格子.
  格子 key 是固定窗口坐标, 每场战斗复用同一批 key
  -> 打上几场之后整张棋盘被永久拉黑, 战斗页再也点不出手.
修复位置: auto_bot.py 主循环, 进入 battle 页时 clicked_cells.clear() + last_cell = 0

用法(项目根目录): python -X utf8 test_battle_loop.py     退出码 0 = 通过
"""
import logging, os, sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
from PIL import Image

import game_utils as g

QUEUE = []
CLICKS = []


def fake_capture(hwnd):
    im = Image.open(os.path.join(D, QUEUE[0])).convert('RGB')
    return im, 1


def fake_find_window():
    return 12345


g.capture_window = fake_capture
g.find_game_window = fake_find_window
try:
    g.u32.IsWindow = lambda h: True
except Exception:
    pass

from auto_bot import App            # noqa: E402

FAILS = []


def check(cond, msg):
    if cond:
        print('  ok    ' + msg)
    else:
        FAILS.append(msg)
        print('  FAIL  ' + msg)


def play(app, shot, n=1):
    """喂 n 轮同一帧, 返回 [(acted, 已点格子数, 本轮点击)]"""
    out = []
    QUEUE[:] = [shot]
    for _ in range(n):
        before = len(CLICKS)
        page, acted, ocr = app.step()
        out.append((page.name, acted, len(app.clicked_cells), CLICKS[before:]))
    return out


def main():
    app = App(dry_run=True, low_cpu=False)
    app.ensure_window()
    app.vision.refresh_hwnd(12345)
    orig_click = app.click

    def click(x, y):
        CLICKS.append((int(x), int(y)))
        orig_click(x, y)
    app.click = click

    print('--- 第 1 场战斗 ---')
    r1 = play(app, 'shots/battle_full.png', 2)
    for row in r1:
        print('   ', row)
    entered, first = r1[0], r1[1]
    check(entered[0] == 'battle' and not entered[1], '进战斗页第一帧不动作(等特征补齐)')
    check(first[0] == 'battle' and first[1] and first[3], '第 1 场战斗点了格子')
    if not first[3]:
        print('  前置条件就挂了, 后面不测')
        return 1
    cell1 = first[3][0]
    n_cells1 = first[2]
    check(n_cells1 == 1, '第 1 场后 clicked_cells 大小 = 1 (实测 %d)' % n_cells1)

    print('--- 战斗 -> 结算 -> 大厅 ---')
    r2 = play(app, 'shots/flow4_s0_result.png', 1)
    r3 = play(app, 'shots/lobby_clean.png', 1)
    print('   ', r2[0][:2], r3[0][:2])
    check(r2[0][0] == 'result', '结算页识别为 result')
    check(r3[0][0] == 'lobby', '回到大厅识别为 lobby')
    check(len(app.clicked_cells) == n_cells1,
          '还没开新一场时, 上一场的 clicked_cells 依然保留 (实测 %d)' % len(app.clicked_cells))

    print('--- 第 2 场战斗(关键: 同一张棋盘) ---')
    r4 = play(app, 'shots/battle_full.png', 2)
    for row in r4:
        print('   ', row)
    reenter, second = r4[0], r4[1]
    check(reenter[0] == 'battle', '再次进战斗页')
    check(reenter[2] == 0, '进战斗页时 clicked_cells 已被清空 (实测 %d)' % reenter[2])
    check(reenter[3] == [], '重进的那一帧没有动作')
    check(second[1] and second[3], '第 2 场战斗仍然点了格子 —— 修复前这里必然 acted=False')
    if second[3]:
        check(second[3][0] == cell1,
              '点的正是第 1 场已经点过的同一个格子 %s -> 证明确实靠清空才放行' % (cell1,))

    print('--- 第 3 场(再验一次幂等) ---')
    play(app, 'shots/flow4_s0_result.png', 1)
    play(app, 'shots/lobby_clean.png', 1)
    r5 = play(app, 'shots/battle_full.png', 2)
    check(len(app.clicked_cells) == 1, '第 3 场进场又清空 -> 只留本场 1 格 (实测 %d)' % len(app.clicked_cells))
    check(r5[1][1], '第 3 场依然能出手')

    print()
    if FAILS:
        print('FAILED %d 项' % len(FAILS))
        for m in FAILS:
            print('  - ' + m)
        return 1
    print('全部通过 (离线, 只读 shots 截图, dry_run 不真点击)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
