# -*- coding: utf-8 -*-
"""离线集成测试: 不依赖真实窗口. 验证"点色优先"后主循环行为

核心期望: 定页只看点色指纹(2ms/轮); 只有 act_needs_ocr=True 的页面才裁 ROI 跑 OCR,
          战斗/匹配等纯点色页整轮零 OCR; 画面无大变化时复用上一帧 OCR 缓存。
"""
import logging, os, sys
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image

import game_utils as g

D = os.path.dirname(os.path.abspath(__file__))
QUEUE = []

def fake_capture(hwnd):
    # QUEUE 里的元素可以是 shots 路径, 也可以是测试现造的 PIL 图(软命中场景用)
    item = QUEUE[0]
    if isinstance(item, Image.Image):
        return item, 1
    im = Image.open(os.path.join(D, item)).convert('RGB')
    return im, 1

def fake_find_window():
    return 12345

g.capture_window = fake_capture
g.find_game_window = fake_find_window
try:
    g.u32.IsWindow = lambda h: True
except Exception:
    pass

import colorprint as cp
from pages import ALL_PAGES
from pages.base import is_soft, route_prints, select_page
from auto_bot import App


def blotch(img, pt, color=(0, 0, 0), r=1):
    # 遮住单个判色点(只涂该点自己的 3x3): 复现战斗页动画盖住指纹那一瞬
    x, y = pt[0], pt[1]
    a = cp.to_arr(img).copy()
    a[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1] = color
    return Image.fromarray(a)


def make_soft(base, page_name):
    # 语料帧 -> 遮掉该页最强指纹的 1 个点 -> 「差 1 点」的软命中帧
    img = Image.open(os.path.join(D, base)).convert('RGB')
    pg = [q for q in ALL_PAGES if q.name == page_name][0]
    arr = cp.to_arr(img)
    fp = max(pg.fingerprints(), key=lambda f: cp.print_score(arr, f, pg.degree, pg.pos_tol))
    for xy in fp:
        v = blotch(img, xy)
        p2, _sc, src2 = route_prints(ALL_PAGES, v)
        if p2 is pg and is_soft(src2):
            return v
    raise AssertionError('遮 1 点造不出软命中: %s/%s' % (base, page_name))

app = App(dry_run=True, low_cpu=False)
app.ensure_window()
app.vision.refresh_hwnd(12345)

# ---------- 断言小工具 ----------
FAILS = []


def check(cond, msg):
    print(('  ok    ' if cond else '  FAIL  ') + msg)
    if not cond:
        FAILS.append(msg)


OCR_STEPS = 0        # 全程 OCR 次数统计


def run(tag):
    """跑一轮并累计 OCR 次数"""
    global OCR_STEPS
    page, acted, ocr_ran = app.step()
    OCR_STEPS += int(ocr_ran)
    return page, acted, ocr_ran


# ---------- 场景1: 大厅连续两帧 -> 第二帧复用 OCR 缓存 ----------
QUEUE[:] = ['shots/lobby_clean.png', 'shots/lobby_clean.png']
p1, a1, o1 = run('lobby1')
p2, a2, o2 = run('lobby2')
print(f'[1] 大厅帧1: page={p1.name} acted={a1} ocr={o1} / 帧2: page={p2.name} acted={a2} ocr={o2}')
check(p1.name == 'lobby' and o1, '大厅帧1: 点色定页, 只为动作读一次本页 ROI')
check(p2.name == 'lobby' and not o2, '大厅帧2: 画面没大变化也没到 ocr_gap -> 复用缓存不 OCR')

# ---------- 场景2: 大厅 -> 宝箱弹窗(价格护栏必须读字) ----------
QUEUE[:] = ['shots/chestinfo.png']
p3, a3, o3 = run('chest')
print(f'[2] 变到宝箱面板: page={p3.name} acted={a3} ocr={o3}')
check(p3.name == 'chest_info' and o3, '宝箱面板: 指纹定页 + 读价格(护栏依赖 OCR)')

# ---------- 场景3: 战斗页整轮零 OCR(点色扫描) ----------
app._act_gap = 0
app.clicked_cells = set()
app.last_cell = 0
QUEUE[:] = ['shots/battle_full.png'] * 3
p4, a4, o4 = run('b1')
p5, a5, o5 = run('b2')
p6, a6, o6 = run('b3')
print(f'[3] 战斗帧1/2/3: acted={a4}/{a5}/{a6} ocr={o4}/{o5}/{o6}')
check(p4.name == 'battle' and a4 and not o4, '战斗帧1: 点色定页当场出手, 整轮零 OCR')
check(p5.name == 'battle' and not a5 and not o5, '战斗帧2: CELL_COOLDOWN 拦住, 仍然零 OCR')
check(p6.name == 'battle' and not o6, '战斗帧3: 依旧零 OCR')

# ---------- 场景4: 战斗循环 8 次, OCR 次数必须为 0 ----------
QUEUE[:] = ['shots/flow2_m0.png'] * 8
ocr_cnt = 0
for _ in range(8):
    app.clicked_cells = set()
    app.last_cell = 0
    p, a, o = run('loop')
    ocr_cnt += int(o)
print(f'[4] 战斗循环8次: OCR次数={ocr_cnt} (页面={p.name})')
check(p.name == 'battle' and ocr_cnt == 0, f'战斗循环 8 轮 OCR 次数 = 0 (实测 {ocr_cnt})')

# ---------- 场景5: 结算页(点击继续 容错) ----------
QUEUE[:] = ['shots/flow4_s0_result.png']
p7, a7, o7 = run('result')
print(f'[5] 结算页: page={p7.name} acted={a7} ocr={o7}')
check(p7.name == 'result' and o7, '结算页: 指纹定页 + 读按钮文案')

# ---------- 场景6: vision.reset() 后缓存必须作废 ----------
QUEUE[:] = ['shots/flow_0_lobby.png']
app.vision.reset()
p8, a8, o8 = run('lobby_again')
print(f'[6] 大厅2: page={p8.name} acted={a8} ocr={o8}')
check(p8.name == 'lobby' and o8, 'reset() 后首帧重新 OCR —— 旧缓存不能跨窗口尺寸复用')

# ---------- 场景7: 软命中(动画遮住 1 个指纹点) -> 稳帧才动手, 全程零 OCR ----------
# 这是 2026-09-03 01:42 真机失效的最小复现: 那时代码一见差 1 点就整轮回退全图 OCR + 文字猜页
soft = make_soft('shots/battle_full.png', 'battle')
p, sc, src = route_prints(ALL_PAGES, soft)
print('[7] 软命中帧: %s %s %.3f (原图遮 1 点)' % (p.name, src, sc))
app._act_gap = 0
app.clicked_cells = set()
app.last_cell = 0
QUEUE[:] = [soft] * 3
s1 = run('soft1')
s2 = run('soft2')
s3 = run('soft3')
check(s1[0].name == 'battle' and not s1[1] and not s1[2],
      '软命中第1帧: 认页但不敢动手 -> 本轮不动作, 也不跑全图 OCR')
check(s2[1] and not s2[2],
      '软命中第2帧: 连续同页=画面稳了 -> 照常出手, 依然零 OCR')
check(s3[0].name == 'battle' and not s3[2], '软命中第3帧: 页面判定仍然只靠点色')
# 恢复: 全中帧必须立刻把软命中计数清零, 不能一路"软"下去
QUEUE[:] = ['shots/battle_full.png']
f4 = run('back_to_full')
check(f4[2] is False, '回到全中帧: 点色直接定页, 不受刚才软命中影响')

FRAMES = 2 + 1 + 3 + 8 + 1 + 1 + 4   # 七个场景一共喂了多少帧
print()
print(f'共 {FRAMES} 帧, OCR 只跑了 {OCR_STEPS} 次 (旧版: 每帧一次全图 OCR = {FRAMES} 次)')
if FAILS:
    print('FAILED %d 项' % len(FAILS))
    for m in FAILS:
        print('  - ' + m)
    sys.exit(1)
print('ALL DONE 全部通过 (离线, 只读 shots 截图, dry_run 不真点击)')
