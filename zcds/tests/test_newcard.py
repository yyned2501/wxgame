# -*- coding: utf-8 -*-
"""新卡展示页回归锁: 点色认出[新卡]页 + 卡页检测器不再被 2b 防抖打断

真机 2026-09-03 16:03 的现场(日志 5564 行之后, 10 条 "result ocr"):
  升级领完奖励 -> 弹一张新卡 -> 这一页没标指纹 -> 点色全表零命中 -> 2b 白等一帧
  -> 2c 花全图 OCR -> 只读到"点击继续" -> 判成 result -> ResultPage.act() 找不到亮紫按钮
  -> 什么都不点 -> 下一帧又零命中…… 6.7s 一圈原地空转, 直到 400 步跑完。
  同一条链上还暴露了第二个洞: page 在 None/result 之间来回翻, _flag_stuck 每两帧被
  "page is None 就清零", 连着 60s 零动作一次 [卡页] 警报都没发。
本测试把两件事一起钉住: [1]~[5] 钉页面, [6] 钉检测器。
"""
import glob
import logging, os, sys
logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)s %(message)s')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools'))
from PIL import Image

import game_utils as g

D = os.path.dirname(os.path.abspath(__file__))
QUEUE = []
CLICKS = []


def fake_capture(hwnd):
    item = QUEUE[0]
    if isinstance(item, Image.Image):
        return item, 1
    return Image.open(os.path.join(D, item)).convert('RGB'), 1


g.capture_window = fake_capture
g.find_game_window = lambda: 12345
try:
    g.u32.IsWindow = lambda h: True
except Exception:
    pass

import auto_bot
from colorprint import REF_SIZE, to_arr
from pages import ALL_PAGES
from pages.base import route_prints, is_soft
from pages.newcard import NewCardPage
from pages.unknown import STUCK_DIR_OFFLINE
from auto_bot import App, STUCK_AFTER
from vision import ScreenFeature

FAILED = []
OCR_CNT = [0]
NEW = ['shots/newcard_live%s.png' % t for t in ('160350', '160411', '160431', '160451')]


def check(ok, msg):
    print('  %s %s' % ('ok  ' if ok else 'FAIL', msg))
    if not ok:
        FAILED.append(msg)


def load(rel):
    return Image.open(os.path.join(D, rel)).convert('RGB')


NC = [p for p in ALL_PAGES if p.name == 'newcard'][0]
RES = [p for p in ALL_PAGES if p.name == 'result'][0]

print('[1] 4 帧真机语料: 点色硬命中 newcard, result 指纹不中(= 不会再被 OCR 抢走)')
for rel in NEW:
    img = load(rel)
    page, score, src = route_prints(ALL_PAGES, img)
    check(page is NC and score >= 1.0 and not is_soft(src),
          '%s -> newcard 硬命中 (%s %.2f)' % (rel, src, score))
    check(RES.print_score(img) < 0.5,
          '  result 指纹只中 %.2f(旧版就是被 OCR 判成 result 才空转的)' % RES.print_score(img))

print('[2] 与卡无关性: 判色点全部落在 y>=830 的底部带(卡牌美术/卡名/属性数字一个都不许进)')
ys = [q[1] for q in NC.points]
check(min(ys) >= 830, '%d 个判色点 y 最小 %d >= 830 (换一张卡不会整片失效)' % (len(ys), min(ys)))
bands = [y for y in ys if not (850 <= y <= 880 or 905 <= y <= 925)]
check(not bands, '15 个点全在两条带里: 白字笔画 y850~880 + 紫底 y905~925 (越界 %s)' % (bands,))
sp = []
for x, y, c in NC.points:
    vals = [tuple(to_arr(load(r))[y, x]) for r in NEW]
    sp.append(max(max(v[k] for v in vals) - min(v[k] for v in vals) for k in range(3)))
check(max(sp) == 0, '4 帧真机语料上 15 个点逐位相同(最大色差 %d, 容差 +-19)' % max(sp))

print('[3] act() 纯点色: 白字外接框中心; 真结算帧上 MIN_PX 必须挡住(判错也点不动)')
ctx = type('C', (), {})()
ctx.f = ScreenFeature(img=load(NEW[0]), boxes=[], joined='')
ctx.last_action = {}
ctx.click = lambda x, y: CLICKS.append((int(x), int(y)))
ctx.acted = lambda key, gap=None: False
CLICKS[:] = []
check(NC.act(ctx) and CLICKS == [(276, 864)], '新卡帧 -> 点 (276,864) (实测 %s)' % (CLICKS,))
for rel in ['shots/flow3_r1.png', 'shots/result_live040817.png', 'shots/levelup_live073932.png']:
    ctx.f = ScreenFeature(img=load(rel), boxes=[], joined='')
    CLICKS[:] = []
    check(not NC.act(ctx) and not CLICKS, '%s -> 不动作零点击' % rel)

print('[4] 真跑 App.step(): page=newcard + 全程零 OCR + 同一轮就出手')
app = App(dry_run=True, low_cpu=False)
app.ensure_window()
app.vision.refresh_hwnd(12345)
_orig_ocr = app.vision.ocr


def _ocr(*a, **kw):
    f, ran = _orig_ocr(*a, **kw)
    OCR_CNT[0] += int(bool(ran))
    return f, ran


app.vision.ocr = _ocr
app.click = lambda x, y: CLICKS.append((int(x), int(y)))
for rel in NEW:
    img = load(rel)
    QUEUE[:] = [img]
    for q in app.pages:
        for attr in ('_last', '_sig', '_tries', '_gave_up_at'):
            if hasattr(q, attr):
                setattr(q, attr, 0 if attr == '_gave_up_at' else None if attr == '_sig' else 0.0)
    app._nohit_streak = 0
    app._trans_streak = 0
    app._act_gap = 0
    app.last_action = {}
    CLICKS[:] = []
    page, acted, ocr_ran = app.step()
    check(page is not None and page.name == 'newcard' and acted and not ocr_ran,
          '%s -> page=%s acted=%s ocr=%s 落点=%s' % (rel, page.name if page else None,
                                                    acted, ocr_ran, CLICKS))
    hit = [c for c in CLICKS if abs(c[0] - 276) <= 8 and abs(c[1] - 864) <= 8]
    check(bool(hit), '  点的就是白字[点击继续] (落点=%s)' % (CLICKS,))
check(OCR_CNT[0] == 0, '到目前为止 OCR 实际跑了 %d 次' % OCR_CNT[0])

print('[5] 全语料: newcard 指纹只认这 4 帧; detect() 恒 0(不给 OCR 抢走身份)')
n = 0
hits = []
for p in sorted(glob.glob(os.path.join(D, 'shots', '*.png')) +
                glob.glob(os.path.join(D, 'shots_live', '*.png'))):
    im = Image.open(p)
    if im.size != (REF_SIZE[0], REF_SIZE[1]):
        continue
    n += 1
    if NC.print_match(im):
        hits.append(os.path.relpath(p, D).replace(chr(92), '/'))
check(n >= 820, '扫了 %d 张 552x1006 帧' % n)
# shots_live/ 里那 4 张是语料帧的原件(同一份像素, 16:03 现场), 按内容去重才是"几张帧"
uniq = {}
for h in hits:
    uniq.setdefault(hash(open(os.path.join(D, h), 'rb').read()), []).append(h)
check(len(hits) == 8 and len(uniq) == 4,
      '命中 %d 个路径 = 4 张不同帧(语料 + shots_live 原件): %s' % (len(hits), list(uniq.values())))
check(NC.detect(type('F', (), {'has': lambda s, *a: True})()) == 0.0,
      'detect() 恒 0.0 —— OCR 读到"点击继续"也不许判成 newcard(那是 result 的词)')

print('[6] _flag_stuck: 2b 防抖的 None/result 翻帧不能再打断卡页计数(真机那 60s 必须报)')
real_log = auto_bot.logging


class _Log(object):
    def __init__(self):
        self.msgs = []

    def warning(self, fmt, *a):
        self.msgs.append(fmt % a if a else fmt)

    def info(self, fmt, *a):
        pass


def _run_stuck(imgs, flip):
    """imgs: 每帧画面; flip=True 时按真机 16:03 的节奏 page 在 None/result 之间交替"""
    lg = _Log()
    auto_bot.logging = lg
    a = App(dry_run=True, low_cpu=False)
    a.cur_page = 'result'
    a._ad_until = 0.0
    res = [p for p in a.pages if p.name == 'result'][0]
    for i, im in enumerate(imgs):
        a.f = ScreenFeature(img=im, boxes=[], joined='')
        a._flag_stuck(None if (flip and i % 2 == 0) else res, False)
    auto_bot.logging = real_log
    return [m for m in lg.msgs if '卡页' in m]


img0 = load(NEW[0])
same = [img0] * (STUCK_AFTER + 4)
check(len(_run_stuck(same, False)) == 1,
      '同一页同一画面连 %d 帧零动作 -> 报 1 次 [卡页]' % (STUCK_AFTER + 4,))
check(len(_run_stuck(same, True)) == 1,
      '真机 16:03 那种 None/result 交替 -> 照样报 1 次(旧版这里一次都不报)')
moving = []
for i in range(STUCK_AFTER + 4):
    im = img0.copy()
    im.paste(Image.new('RGB', (24, 24), (i * 7 % 256, i * 13 % 256, i * 29 % 256)),
             (30 + i * 3, 300))
    moving.append(im)
check(len(_run_stuck(moving, True)) == 0, '画面每帧都在变(转场/广告) -> 一次都不报')
check(len(_run_stuck(same, False)) == 1 and True, '重复一次确认幂等')

print()
print('全程 OCR 实际跑了 %d 次' % OCR_CNT[0])
if FAILED:
    print('FAILED %d 项' % len(FAILED))
    for m in FAILED:
        print('  - ' + m)
    sys.exit(1)
print('ALL DONE 新卡页回归全绿')