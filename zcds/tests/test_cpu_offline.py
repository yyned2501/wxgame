# -*- coding: utf-8 -*-
"""离线集成测试: 不依赖真实窗口. 验证"点色优先"后主循环行为

核心期望: 定页只看点色指纹(2ms/轮); 只有 act_needs_ocr=True 的页面才裁 ROI 跑 OCR,
          战斗/大厅/结算/开箱等纯点色页整轮零 OCR; 画面无大变化时复用上一帧 OCR 缓存。
          2026-09-03 定案后连 chest_info(价格护栏)也改成纯点色 —— 只剩 ad_popup/claim_popup
          两页还要读字, 而它们没有指纹(只能靠 OCR 认页, 走的是 force 全图那条路),
          所以"缓存复用 / reset() 作废"这两个护栏改成直接问 Vision(场景6b)。
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


def run(tag, fresh=False):
    """跑一轮并累计 OCR 次数; fresh=True 先把零命中水位清 0(场景之间要互相隔离 ——
    2b2 认出出口后会刻意停在 AFTER-1, 下一帧还零命中就继续出手, 不再白等)"""
    global OCR_STEPS
    if fresh:
        app._nohit_streak = 0
    page, acted, ocr_ran = app.step()
    OCR_STEPS += int(ocr_ran)
    return page, acted, ocr_ran


# ---------- 场景1: 大厅纯点色(2026-09-03 定案) -> 连动作层都不许读字, 两帧全零 OCR ----------
QUEUE[:] = ['shots/lobby_clean.png', 'shots/lobby_clean.png']
p1, a1, o1 = run('lobby1')
p2, a2, o2 = run('lobby2')
print(f'[1] 大厅帧1: page={p1.name} acted={a1} ocr={o1} / 帧2: page={p2.name} acted={a2} ocr={o2}')
check(p1.name == 'lobby' and a1 and not o1, '大厅帧1: 点色定页 + 点色认宝箱槽/对战按钮, 整轮零 OCR')
check(p2.name == 'lobby' and not o2, '大厅帧2: 依旧零 OCR(旧版这里每帧都要 ROI OCR 369ms)')

# ---------- 场景2: 宝箱面板(价格护栏)也纯点色了 —— 两帧都必须零 OCR ----------
QUEUE[:] = ['shots/chestinfo.png', 'shots/chestinfo.png']
p3, a3, o3 = run('chest')
p3b, a3b, o3b = run('chest2')
print(f'[2] 宝箱面板帧1/2: page={p3.name}/{p3b.name} acted={a3}/{a3b} ocr={o3}/{o3b}')
check(p3.name == 'chest_info' and a3 and not o3,
      '宝箱面板: 指纹定页 + 点色判免费按钮(旧版这里每帧一次 ROI OCR 369ms)')
check(p3b.name == 'chest_info' and not o3b, '宝箱面板帧2: 依旧零 OCR')

# ---------- 场景3: 战斗页整轮零 OCR(点色扫描) ----------
app._act_gap = 0
app.clicked_cells = {}
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
    app.clicked_cells = {}
    app.last_cell = 0
    p, a, o = run('loop')
    ocr_cnt += int(o)
print(f'[4] 战斗循环8次: OCR次数={ocr_cnt} (页面={p.name})')
check(p.name == 'battle' and ocr_cnt == 0, f'战斗循环 8 轮 OCR 次数 = 0 (实测 {ocr_cnt})')

# ---------- 场景5: 结算页(点击继续 容错) ----------
QUEUE[:] = ['shots/flow4_s0_result.png']
p7, a7, o7 = run('result')
print(f'[5] 结算页: page={p7.name} acted={a7} ocr={o7}')
check(p7.name == 'result' and a7 and not o7, '结算页: 指纹定页 + 点色认[继续]按钮, 整轮零 OCR')

# ---------- 先造一帧"点色全表零命中 + 没有返回箭头 + 没有引导气泡"的中性帧 ----------
# 2026-09-03 真机 03:54: 战斗页被爆炸动画盖住指纹 -> 那一帧零命中 -> 白烧 675ms 全图 OCR
# 还判成 unknown; 下一帧就恢复全中了。动画帧不会连着两帧长得一样, 所以第 1 帧只等不动。
import numpy as np
_b = Image.open(os.path.join(D, 'shots/battle_full.png')).convert('RGB')
_arr = cp.to_arr(_b).copy()
_arr[:, :] = 200                            # 整帧糊成一片亮灰: 谁都不像, 也没字可读
NEUTRAL = Image.fromarray(_arr)             # 底部导航栏一并糊掉 -> 连"兄弟页签"都推不出来

# ---------- 场景6: 中性零命中帧(什么出口特征都没有) -> 白等一帧, 第2帧才允许花一次全图 OCR ----------
QUEUE[:] = [NEUTRAL] * 2
app.vision.reset()
p8a, a8a, o8a = run('neutral_1', fresh=True)
p8, a8, o8 = run('neutral_2')
print(f'[6] 中性零命中帧: 帧1 page={p8a} ocr={o8a} / 帧2 page={p8.name} acted={a8} ocr={o8}')
check(p8a is None and not o8a,
      '零命中第1帧: 白等一轮(可能是动画帧), 不动作也不花 OCR')
check(p8.name == 'unknown' and o8,
      '连着第2帧仍零命中且无出口特征 -> 才是真没标指纹的页(改版), 走 OCR 兜底')

# ---------- 场景6a: 零命中但认出[侧页返回箭头] -> 交 unknown 退出, 一次 OCR 都不许花 ----------
# 侧页(竞技场/任务)内容随等级变, 标指纹等于标在文字上(lobby 刚踩过), 所以刻意不标;
# 但左下角那颗青色返回箭头本身就是点色可认的身份 + 出口。
QUEUE[:] = ['shots/other_quest_0022.png'] * 2
pa1, aa1, oa1 = run('arrow_1', fresh=True)
pa2, aa2, oa2 = run('arrow_2')
print(f'[6a] 带箭头侧页: 帧1 page={pa1} ocr={oa1} / 帧2 page={pa2.name} acted={aa2} ocr={oa2}')
check(pa1 is None and not oa1, '带箭头帧第1帧: 仍然只白等, 不动作不花 OCR')
check(pa2.name == 'unknown' and not oa2,
      '带箭头帧第2帧: 点色认出返回箭头 -> 直接交 unknown, 一次 OCR 都不花')

# ---------- 场景6b: 零命中但认出[新手引导模态] -> 同样零 OCR 交给 unknown ----------
# 引导气泡把整页压暗, 所以那帧连大厅指纹都不命中; 认它靠的是"大白气泡"这个颜色特征。
QUEUE[:] = ['shots/lobby_dim_live090000.png'] * 2
pg1, ag1, og1 = run('guide_1', fresh=True)
pg2, ag2, og2 = run('guide_2')
print(f'[6b] 引导模态帧: 帧1 page={pg1} ocr={og1} / 帧2 page={pg2.name} acted={ag2} ocr={og2}')
check(pg1 is None and not og1, '引导帧第1帧: 白等一轮, 不动作不花 OCR')
check(pg2.name == 'unknown' and not og2,
      '引导帧第2帧: 点色认出大白气泡 -> 交 unknown 照着落点表点, 一次 OCR 都不花')

# ---------- 场景6d: OCR 缓存复用 + reset() 作废(纯点色后 step() 走不到这条路, 直接问 Vision) ----------
one = Image.open(os.path.join(D, 'shots/other_quest_0022.png')).convert('RGB')
v = app.vision
ROI = (0.0, 0.1, 1.0, 0.9)
v.reset()
v.changed_big = False
_c0, r_cold = v.ocr(one, region=None, scale=0.5, min_gap=999)   # 冷启动 -> 必跑
_c1, r_cache = v.ocr(one, region=None, scale=0.5, min_gap=999)
_c2, r_roi = v.ocr(one, region=ROI, scale=0.5, min_gap=999)
v.reset()
_c3, r_reset = v.ocr(one, region=ROI, scale=0.5, min_gap=999)
print(f'[6d] 冷跑={r_cold} 复用={r_cache} 换ROI={r_roi} reset后={r_reset}')
check(r_cold and not r_cache, '未到 min_gap 且画面没变 -> 复用上轮文字坐标, 不重跑 OCR')
check(r_roi, '换 ROI 必须重跑 —— 旧坐标属于别的区域')
check(r_reset, 'reset() 后首帧重新 OCR —— 旧缓存不能跨窗口尺寸复用')

# ---------- 场景6c: 真机 03:54 那一帧的最小复现(中性帧单帧闪现, 第1帧就该白等): 爆炸动画把指纹点大面积盖掉 ----------
# 页面本身还是战斗页, 只是这一帧点色零命中。旧版当场烧一次全图 OCR; 现在只白等一帧。
blotted = NEUTRAL
_p, _sc, _src = route_prints(ALL_PAGES, cp.to_arr(blotted))
check(_p is None, f'造出来的动画帧确实点色零命中 (score={_sc:.3f})')
app._act_gap = 0
_ocr_before = OCR_STEPS
QUEUE[:] = ['shots/battle_full.png']          # fake_capture 只读 QUEUE[0], 所以一帧一换
r1 = run('anim1', fresh=True)
QUEUE[:] = [blotted]
r2 = run('anim2')
QUEUE[:] = ['shots/battle_full.png']
r3 = run('anim3')
check(r1[0].name == 'battle' and not r1[2], '动画前: 战斗页全中, 零 OCR')
check(r2[0] is None and not r2[2], '动画帧: 零命中 -> 白等一轮, 不烧全图 OCR')
check(r3[0].name == 'battle' and not r3[2], '动画后: 立刻恢复全中并照常出手')
check(OCR_STEPS == _ocr_before, f'场景6c 三帧额外 OCR 次数 = 0 (实测 {OCR_STEPS - _ocr_before})')

# ---------- 场景7: 软命中(动画遮住 1 个指纹点) -> 稳帧才动手, 全程零 OCR ----------
# 这是 2026-09-03 01:42 真机失效的最小复现: 那时代码一见差 1 点就整轮回退全图 OCR + 文字猜页
soft = make_soft('shots/battle_full.png', 'battle')
p, sc, src = route_prints(ALL_PAGES, soft)
print('[7] 软命中帧: %s %s %.3f (原图遮 1 点)' % (p.name, src, sc))
app._act_gap = 0
app.clicked_cells = {}
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

FRAMES = 2 + 2 + 3 + 8 + 1 + 2 + 3 + 4   # 八个场景一共喂了多少帧
print()
print(f'共 {FRAMES} 帧, OCR 只跑了 {OCR_STEPS} 次 (旧版: 每帧一次全图 OCR = {FRAMES} 次)')
if FAILS:
    print('FAILED %d 项' % len(FAILS))
    for m in FAILS:
        print('  - ' + m)
    sys.exit(1)
print('ALL DONE 全部通过 (离线, 只读 shots 截图, dry_run 不真点击)')
