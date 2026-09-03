# -*- coding: utf-8 -*-
"""未知页面兜底: 点色认出[引导模态]/[侧页返回箭头]就照着点, 都不认得才试探遮罩。

零 OCR 是本页的硬要求(act_needs_ocr=False): 这两类帧的"身份判据"本身就是颜色
(大白气泡 + 手套 / 左下角青色箭头), 花 675ms 全图 OCR 既慢又读不出可用信息。
"""
import logging
import os
import time

import numpy as np
from config import ROOT, SHOTS_DIR

# 取证帧写到哪: 只有真机才往 shots/ 丢。离线回归(dry_run)每跑一次就会多几张 stuck_*.png,
# 而那个目录是标定语料 —— 冲进来一堆没标注的帧, 只会让 tools/pick_print.py check 的
# 未标注列表越来越长(实测一小时内从 12 张涨到 17 张)。那种帧照样要能人眼核对,
# 所以写到 scratch/reg_stuck/, 不碰语料。
# 判据用 dry_run 且默认按离线: 生产里的 App 一定带这个属性, 反过来任何没带它的
# 假 ctx(回归脚手架)一律当离线处理 —— 失败方向是安全的(少写语料, 不会漏存真机帧)。
STUCK_DIR_OFFLINE = os.path.join(os.path.dirname(SHOTS_DIR), 'scratch', 'reg_stuck')


def stuck_dir(ctx):
    """这张 stuck_*.png 该写到哪: 真机 -> shots/(语料+取证), 离线回归 -> scratch/reg_stuck/"""
    if getattr(ctx, 'dry_run', True):
        os.makedirs(STUCK_DIR_OFFLINE, exist_ok=True)
        return STUCK_DIR_OFFLINE
    return SHOTS_DIR

from .base import (NAV_LOBBY_TAB, Page, back_arrow_pos, find_close_badge, guide_targets,
                  nav_present, nav_tab_cx)

MASK_POINTS = [(270, 860), (270, 300), (30, 300), (520, 300), (270, 200)]
MAX_IDLE = 8
# ---- "点了没反应"升级表(真机 2026-09-03 08:36 竞技场晋级页死循环 3 分钟的教训) ----
# 旧版: 看到箭头 -> 点写死的 (63,970) -> 那一格是空白 -> 画面不变 -> 8s 后再来一遍,
#       无限循环, 而且 acted=True 让主循环的卡页计数器一直归零, 连 WARNING 都刷不出来。
# 新版: 落点由颜色现算, 再按候选表逐个试; 画面签名一变就重新计数(说明点到了),
#       候选点完画面还一模一样 -> 判定这页点不动, 存帧取证 + 睡 GIVEUP_SEC。
ARROW_OFFSETS = [(0, 0), (0, 8), (-8, 0), (8, -6)]
# 关闭徽章(红底白叉)中心由 find_close_badge 现算, 本身就有 +-2px 抖动(手指图标会挡),
# 再给几个微调点: 语料 6 张徽章帧第一点即中, 后面几点只是保险。
BADGE_OFFSETS = [(0, 0), (0, -6), (6, 0), (-6, 0)]
MAX_TRY = 5                    # 候选落点上限(引导表最多 5 个: 关叉/指尖/下一步/气泡/掌心)
GIVEUP_SEC = 45
SIG_SIZE = (28, 51)            # 画面签名: 灰度缩略, 只判"点完这页有没有变", 不做识别


def frame_sig(img):
    a = np.asarray(img.convert('L').resize(SIG_SIZE), dtype=np.uint8)
    return a.tobytes()


class UnknownPage(Page):
    name = 'unknown'
    next_pages = ()
    act_needs_ocr = False

    _sig = None
    _tries = 0
    _gave_up_at = 0.0

    def detect(self, f):
        return 0.0            # 兜底页

    def _reset(self):
        self._sig, self._tries = None, 0

    def _candidates(self, img):
        """(这帧是什么, 可点落点列表) —— 引导模态优先: 它盖在别人家页面上, 先点掉才有后续"""
        pts = guide_targets(img)
        if pts:
            return '引导模态', pts[:MAX_TRY]
        badge = find_close_badge(img)
        if badge is not None:
            return ('弹窗关闭徽章',
                    [(badge[0] + dx, badge[1] + dy) for dx, dy in BADGE_OFFSETS][:MAX_TRY])
        pos = back_arrow_pos(img)
        if pos is not None:
            return '侧页返回箭头', [(pos[0] + dx, pos[1] + dy) for dx, dy in ARROW_OFFSETS]
        # 万一是从 OCR 那条路落进来的兄弟页签, 照样知道该点中间那个回大厅
        if nav_present(img) and nav_tab_cx(img) != NAV_LOBBY_TAB[0]:
            return '兄弟页签', [NAV_LOBBY_TAB]
        return '', []

    def act(self, ctx):
        img = getattr(ctx.f, 'img', None)
        if img is None:
            return False
        what, cands = self._candidates(img)
        if not cands:
            self._reset()
            ctx.unknown_idle += 1
            if ctx.unknown_idle >= MAX_IDLE:
                d, ts = stuck_dir(ctx), time.strftime('%H%M%S')
                ctx.f.img.save(os.path.join(d, 'stuck_%s.png' % ts))
                logging.warning('未知界面 x%d, 截图 %s'
                                % (ctx.unknown_idle,
                                   os.path.relpath(os.path.join(d, 'stuck_%s.png' % ts), ROOT)))
                if ctx.unknown_idle < MAX_IDLE + 3:
                    pt = MASK_POINTS[(ctx.unknown_idle - MAX_IDLE) % len(MASK_POINTS)]
                    logging.info(f'[未知] 试探遮罩 {pt}')
                    ctx.click(*pt)
                else:
                    time.sleep(45)
                    ctx.unknown_idle = 0
            return False
        sig = frame_sig(img)
        if sig != self._sig:            # 画面变了 = 上一次点击起作用了(或换了页), 重新计数
            self._sig, self._tries = sig, 0
        if self._tries >= len(cands):
            if time.time() - self._gave_up_at < GIVEUP_SEC:
                return False
            self._give_up(ctx, img, what, cands)
            self._sig, self._tries = None, 0     # 冷却后重新量一次落点再试一轮
            return False
        x, y = cands[self._tries]
        self._tries += 1
        logging.info(f'[未知] {what}: 点候选 {self._tries}/{len(cands)} -> ({x},{y})')
        ctx.click(x, y)
        return True

    def _give_up(self, ctx, img, what, cands):
        self._gave_up_at = time.time()
        d = stuck_dir(ctx)
        tag = 'guide' if '引导' in what else ('badge' if '徽章' in what else 'arrow')
        try:
            fn = 'stuck_%s_%s.png' % (tag, time.strftime('%H%M%S'))
            img.save(os.path.join(d, fn))
        except Exception:
            fn = '(存帧失败)'
        logging.warning(f'[未知] {what} 的 {len(cands)} 个落点({cands})点完画面零变化 -> '
                        f'这页点不动, 存帧 {os.path.relpath(os.path.join(d, fn), ROOT)}/{fn}, '
                        f'睡 {GIVEUP_SEC}s 再看'
                        f'(多半是撞上了没标指纹的新页面)')
