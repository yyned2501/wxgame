# -*- coding: utf-8 -*-
"""真机证据帧全量复核: 把 shots_live 里 bot 自己存的每一张帧过一遍点色指纹, 和文件名标签对账。

和 test_zero_ocr 的分工:
    test_zero_ocr = 闸门(标定语料 + 没进过语料的 dbg_ 留出帧), 断言"零 OCR 也能定页"
    live_audit    = 体检(全量真机帧, 连闸门不吃的 ocr_* 也吃), 断言"没有一帧被认成别的页"

为什么需要它(2026-09-04 真机第 38 轮): 第一次全量扫 2558 张就翻出 11 张"指纹和文件名不一致",
逐张肉眼验真的结论是 **指纹全对, 标签是错的**:
    ocr_result_1603xx(4 张) -> newcard    整屏就是新卡页, OCR 把"点击继续"读成了 result
    ocr_result_082513       -> fps_popup  帧率弹窗盖在结算页上, 弹窗优先 = 对
    dbg_004_chest_info_074830 -> hero_level 英雄等级弹窗盖在宝箱页上, 弹窗优先 = 对
    dbg_*_unknown_*(5 张)   -> levelup/versus 老构建没标过这些页, 当时只能记 unknown
所以"文件名 = 真值"这个前提本身不成立, 不能把这些帧直接抬进闸门(抬一次红一次 = 闸门废掉, §32.5)。
本工具的口径: **凡是"标签是有指纹的页"却和指纹不一致的帧, 必须逐条登记在 VERIFIED 里并附肉眼依据;
冒出一条没登记的新不一致 = 退出码 1。** 这样"新增认错页"能被机器抓住, 而历史脏标签不用装死。

用法(游戏目录):
    python -X utf8 tools\\live_audit.py            # 全量扫(2500+ 张约 40s)
    python -X utf8 tools\\live_audit.py --quiet    # 只打摘要和账目
退出码: 0 = 没有未登记的不一致帧; 1 = 有(逐条打印, 肉眼看一眼再决定是补指纹还是改代码)
"""
import argparse
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import numpy as np                      # noqa: E402
import colorprint as cp                 # noqa: E402
from PIL import Image                   # noqa: E402
from pages import ALL_PAGES             # noqa: E402
from pages.base import route_prints     # noqa: E402
from known_blind import EVID, FP_PAGES, unclaimed_note   # noqa: E402

SHOTS = os.path.join(ROOT, 'shots_live')

# 这些标签按构造就不是真值: unknown = 当时谁都没认出来; other = 老构建的侧页统称。
NOT_TRUTH = {'unknown', 'other'}

# 逐张肉眼验真过的"指纹 vs 文件名标签"不一致帧: (帧名正则, 指纹判的页或 None, 依据)
# 页名写 None = 点色谁都没认领(代价只是慢一次 OCR, 不会点错), 同样要登记原因。
VERIFIED = [
    (r'^ocr_result_160(35|41|43|45)\d\.png$', 'newcard',
     '整屏是新卡页(弩炮 + 点击继续), OCR 把"点击继续"读成 result'),
    (r'^ocr_result_082513\.png$', 'fps_popup',
     '帧率自适应弹窗盖在结算页上, 弹窗排在 ResultPage 前面 = 设计内'),
    (r'^dbg_004_chest_info_074830\.png$', 'hero_level',
     '英雄等级弹窗盖在宝箱页上, HeroLevelPage 排在 ChestInfoPage 前面 = 设计内'),
    (r'^ocr_battle_051920\.png$', None,
     '全屏法术动画(攻城重锤)横幅横切棋盘, battle 三个十字单元同时被盖 = 和 §32 同一类成本'),
    (r'^ocr_versus_00(4[6-9]|50)\d{2}\.png$', None,
     ' lobby 上盖着"秘境大冒险"运营弹窗, OCR 把背景里的"玩家对战"读成 versus'),
]


def verified_for(fname, page):
    """这张帧的不一致是否已肉眼验真并登记 -> 返回依据; 没登记 -> None"""
    for pat, want, why in VERIFIED:
        if re.match(pat, fname) and want == page:
            return why
    return None


def frame_arr(path):
    im = Image.open(path).convert('RGB')
    if im.size != cp.REF_SIZE:
        im = im.resize(cp.REF_SIZE)
    return cp.to_arr(im)


def evidence():
    """shots_live 里 bot 自己存的证据帧 -> [(路径, 标签)]"""
    if not os.path.isdir(SHOTS):
        return []
    out = []
    for n in sorted(os.listdir(SHOTS)):
        m = EVID.match(n)
        if m:
            out.append((os.path.join(SHOTS, n), m.group(2)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quiet', action='store_true', help='只打摘要')
    a = ap.parse_args()
    rows = evidence()
    print('指纹表 %d 页; 证据帧 %d 张' % (len(FP_PAGES), len(rows)))
    if not rows:
        print('没有 shots_live 证据帧, 无事可做')
        return 0

    t0 = time.time()
    ok = blind = noreg = reg = skip_notruth = skip_nofp = 0
    recovered = []      # 老构建记 unknown, 今天指纹认出来了 -> 好消息, 单独统计
    unclaimed = {}      # 点色没认领的帧按标签聚合
    for path, label in rows:
        fname = os.path.basename(path)
        page, score, src = route_prints(ALL_PAGES, frame_arr(path))
        got = page.name if page else None
        if label in NOT_TRUTH:
            skip_notruth += 1
            if got and label == 'unknown':
                recovered.append((fname, got))
            continue
        if label not in FP_PAGES:          # 这页本来就没指纹(claim_popup 等), 按设计交 OCR
            skip_nofp += 1
            continue
        if got == label:
            ok += 1
            continue
        note = unclaimed_note(path, score, src)
        if note:
            blind += 1
            continue
        why = verified_for(fname, got)
        if why:
            reg += 1
            if got is None:
                unclaimed[label] = unclaimed.get(label, 0) + 1
            elif not a.quiet:
                print('  已登记 %s 标签=%s 指纹=%s -> %s' % (fname, label, got, why))
            continue
        noreg += 1
        print('  未登记 %s 标签=%s 指纹=%s score=%.3f src=%s  <-- 肉眼看一眼'
              % (fname, label, got, score, src))
    print('耗时 %.1fs (%.1f ms/帧)' % (time.time() - t0,
                                       (time.time() - t0) * 1000 / max(len(rows), 1)))
    print('对账: 一致 %d / 设计内压暗盲区 %d / 已登记不一致 %d / 未登记 %d'
          % (ok, blind, reg, noreg))
    print('  (标签非真值跳过 %d 张, 其中老构建记 unknown 今天认出页的 %d 张; 本页无指纹跳过 %d 张)'
          % (skip_notruth, len(recovered), skip_nofp))
    if unclaimed:
        print('  点色没认领(只是慢一次 OCR, 不会点错): %s' % sorted(unclaimed.items()))
    if recovered and not a.quiet:
        for f, g in recovered[:10]:
            print('    今天认出来了 %s -> %s' % (f, g))
    if noreg:
        print('FAIL 有 %d 张帧的指纹和标签对不上且没登记原因' % noreg)
        return 1
    print('ALL DONE 真机证据帧全量复核: 没有一帧被认成别的页')
    return 0


if __name__ == '__main__':
    sys.exit(main())
