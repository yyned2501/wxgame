# -*- coding: utf-8 -*-
r"""帧率自适应弹窗回归锁: 点色认出 fps_popup + 纯点色关弹窗 + unknown 的回执键兜底档

真机 2026-09-04 08:26~08:41 的现场(日志 21060 行往后, 118 步零动作):
  战斗掉帧 -> 弹"帧率自适应"蓝面板盖住结算页 -> 这一页没标指纹 -> 点色整表零命中
  -> 全图 OCR 读到的是**背景** result 的字 -> 判成 result -> ResultPage.act() 的亮紫
  按钮被弹窗挡住 -> return False -> "OCR 连续 3 帧认出页面却零动作" -> 交 unknown
  -> 遮罩试探 (270,860)/(270,300)/(30,300) 三个点全在弹窗外面 -> 15 分钟点不掉。
本测试钉三层: [1]~[4] 这一页本身, [5]~[6] 下一张没标指纹的弹窗怎么办。
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
from colorprint import REF_SIZE, color_bbox
from pages import ALL_PAGES
from pages.base import route_prints, is_soft
from pages.fps_popup import FpsPopupPage, BTN_BOX, YELLOW, BTN_MIN_PX
from pages.unknown import UnknownPage
from auto_bot import App, MODAL_OK_TRIES
from vision import ScreenFeature, TBox

FAILED = []
OCR_CNT = [0]
FP = [p for p in ALL_PAGES if p.name == 'fps_popup'][0]
RES = [p for p in ALL_PAGES if p.name == 'result'][0]
UNK = [p for p in ALL_PAGES if p.name == 'unknown'][0]
NEW = sorted(glob.glob(os.path.join(D, 'shots', 'fps_popup_live*.png')))
# 同一页的现场原件(当时没标指纹, 所以被存成 unknown/OCR 取证帧), 也算命中
SAME_PAGE = ('shots_live/ocr_result_082513.png', 'shots_live/stuck_unknown_082550.png',
             'shots_live/stuck_unknown_082901.png', 'shots_live/stuck_unknown_083520.png')
NEG = ['shots/lobby_live084600.png', 'shots/matching_live004245.png',
       'shots/result_live040817.png', 'shots/battle_live014400.png',
       'shots/chest_info_live004230.png', 'shots/vip_popup_live005647.png']


def check(ok, msg):
    print('  %s %s' % ('ok  ' if ok else 'FAIL', msg))
    if not ok:
        FAILED.append(msg)


def load(rel):
    return Image.open(os.path.join(D, rel)).convert('RGB')


print('[1] %d 帧真机语料: 点色硬命中 fps_popup, result 指纹不中(= 不会再被 OCR 抢走)' % len(NEW))
check(len(NEW) >= 8, '语料帧数 %d' % len(NEW))
for rel in NEW:
    img = load(rel)
    page, score, src = route_prints(ALL_PAGES, img)
    check(page is FP and score >= 1.0 and not is_soft(src),
          '%s -> fps_popup 硬命中 (%s %.2f)' % (os.path.basename(rel), src, score))
    check(RES.print_score(img) < 0.5,
          '  result 指纹只中 %.2f(旧版就是被 OCR 判成 result 才空转的)' % RES.print_score(img))

print('[2] 判色点全部落在弹窗面板内(面板外是被压暗的上一页, 底色随上一页变, 一个都不许进)')
pts = FP.points
check(all(65 <= x <= 487 and 325 <= y <= 705 for x, y, _c in pts),
      '%d 个点全在面板区 x65~487 / y325~705 内' % len(pts))
check(min(y for _x, y, _c in pts) >= 340,
      '最上面的点 y=%d >= 340(标题行), 没吃到面板上方的 MVP 动画星星' % min(y for _x, y, _c in pts))

print('[3] act() 纯点色: 黄色[知道了]外接框中心; 别的页面上 MIN_PX 必须挡住(判错也点不动)')
ctx = type('C', (), {})()
ctx.f = ScreenFeature(img=load(NEW[0]), boxes=[], joined='')
ctx.last_action = {}
ctx.click = lambda x, y: CLICKS.append((int(x), int(y)))
ctx.acted = lambda key, gap=None: False
for rel in NEW[:3]:
    ctx.f = ScreenFeature(img=load(rel), boxes=[], joined='')
    CLICKS[:] = []
    check(FP.act(ctx) and CLICKS and abs(CLICKS[0][0] - 275) <= 6 and abs(CLICKS[0][1] - 644) <= 6,
          '%s -> 点 %s (黄色按钮外接框中心)' % (os.path.basename(rel), CLICKS))
for rel in NEG:
    if not os.path.exists(os.path.join(D, rel)):
        continue
    img = load(rel)
    bb = color_bbox(img, BTN_BOX, YELLOW, 85, BTN_MIN_PX)
    CLICKS[:] = []
    ctx.f = ScreenFeature(img=img, boxes=[], joined='')
    check(not FP.act(ctx) and not CLICKS,
          '%s -> 不动作零点击(同带黄色像素 %s)' % (rel, None if bb is None else bb[2]))

print('[4] 真跑 App.step(): page=fps_popup + 全程零 OCR + 同一轮就出手')
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
for rel in NEW[:4]:
    img = load(rel)
    QUEUE[:] = [img]
    for q in app.pages:
        for attr in ('_last', '_sig', '_tries', '_gave_up_at'):
            if hasattr(q, attr):
                setattr(q, attr, 0 if attr in ('_last', '_tries') else None if attr == '_sig' else 0.0)
    app._nohit_streak = 0
    app._trans_streak = 0
    app._act_gap = 0
    app.last_action = {}
    app.modal_ok, app._modal_ok_budget = None, 0
    CLICKS[:] = []
    page, acted, ocr_ran = app.step()
    check(page is not None and page.name == 'fps_popup' and acted and not ocr_ran,
          '%s -> page=%s acted=%s ocr=%s 落点=%s' % (os.path.basename(rel),
            page.name if page else None, acted, ocr_ran, CLICKS))
    hit = [c for c in CLICKS if abs(c[0] - 275) <= 8 and abs(c[1] - 644) <= 8]
    check(bool(hit), '  点的就是黄色[知道了] (落点=%s)' % (CLICKS,))
check(OCR_CNT[0] == 0, '到目前为止 OCR 实际跑了 %d 次(点色认出页, 一个字都不该读)' % OCR_CNT[0])

print('[5] 全语料精度: 判色全中只认这一页 —— 2764 帧里命中 = 10 语料 + 4 同页现场帧, 零误中')
hits = []
n = 0
for p in sorted(glob.glob(os.path.join(D, 'shots', '*.png')) +
                glob.glob(os.path.join(D, 'shots_live', '*.png'))):
    im = Image.open(p)
    if im.size != REF_SIZE:
        continue
    n += 1
    if FP.print_match(im):
        hits.append(os.path.relpath(p, D).replace(chr(92), '/'))
want = set(os.path.relpath(x, D).replace(chr(92), '/') for x in NEW) | set(SAME_PAGE)
check(n >= 2000, '扫了 %d 张 552x1006 帧' % n)
check(set(hits) == want,
      '命中 %d 个路径, 全部属于这一页(语料 10 + 同页现场帧 4): %s'
      % (len(hits), sorted(set(hits) - want) or '无越界'))

print('[6] 回执键兜底档: OCR 认出页却零动作时, 先点"知道了", 含价格/领取字样一律不碰')
a2 = App(dry_run=True, low_cpu=False)
a2.f = ScreenFeature(img=load(NEW[0]), boxes=[TBox('已开启自动帧率控制', 100, 480, 350, 60),
                                             TBox('知道了', 250, 630, 50, 30)], joined='')
a2._scan_modal_ok()
check(a2.modal_ok == (275, 645, '知道了') and a2._modal_ok_budget == MODAL_OK_TRIES,
      '纯回执按钮 -> modal_ok=%s 额度=%d' % (a2.modal_ok, a2._modal_ok_budget))
a2.f = ScreenFeature(img=load(NEW[0]), boxes=[TBox('免费领取', 250, 630, 60, 30),
                                             TBox('知道了 30宝石', 250, 700, 90, 30)], joined='')
a2._scan_modal_ok()
check(a2.modal_ok is None, '带"领取/宝石"字样的框 -> 拒绝, modal_ok=None(花钱护栏不许绕)')
a2.f = ScreenFeature(img=load(NEW[0]), boxes=[TBox('已开启自动帧率控制, 我知道了 will 保持流畅',
                                                  100, 480, 350, 60)], joined='')
a2._scan_modal_ok()
check(a2.modal_ok is None, '正文里出现"我知道了"(长度>6) -> 当正文跳过, modal_ok=None')

print('[7] unknown.act(): 有回执键就点它(一次一发, 额度用完交回原升级表)')
a3 = App(dry_run=True, low_cpu=False)
a3.f = ScreenFeature(img=load(NEW[0]), boxes=[], joined='')
a3.click = lambda x, y: CLICKS.append((int(x), int(y)))
a3._act_gap = 0
a3.last_action = {}
a3.modal_ok = (275, 645, '知道了')
a3._modal_ok_budget = MODAL_OK_TRIES
CLICKS[:] = []
r1 = UNK.act(a3)
check(r1 and CLICKS == [(275, 645)] and a3._modal_ok_budget == MODAL_OK_TRIES - 1,
      '第一帧 -> 点回执键 %s, 剩余额度 %d' % (CLICKS, a3._modal_ok_budget))
CLICKS[:] = []
a3._modal_ok_budget = 0
r2 = UNK.act(a3)
check(not r2 and not CLICKS, '额度用完 -> 交回原升级表(不再乱点, 也不重复点遮罩)')
a3.modal_ok = None
check(UNK.act(a3) is not None, 'modal_ok=None -> 走原来的候选/遮罩阶梯(不炸)')

print()
print('全程 OCR 实际跑了 %d 次' % OCR_CNT[0])
if FAILED:
    print('FAILED %d 项' % len(FAILED))
    for m in FAILED:
        print('  - ' + m)
    sys.exit(1)
print('ALL DONE 帧率自适应弹窗回归全绿')
