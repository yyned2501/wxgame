# -*- coding: utf-8 -*-
"""离线「零 OCR」回归: 定页面只用点色指纹, 一张图都不许溜进 OCR

用户定案(2026-09-03): OCR 准确率太低而且速度太慢 —— 识别成功以后, 脚本里一律用点色。
所以这里钉死两件事:
  1) 凡是标过指纹的页, 语料 + 真机留出帧的每一张都必须被 route_prints() 直接定出页面
     (返回 None = 主循环那一轮就得花一次全图 OCR, 真机实测 675ms/帧, 这就是回归)
  2) 整轮扫描结束后 OCR 相关模块依然没被 import 过 —— 证明这条路径真的零 OCR
另外单独检查: 没有指纹的帧(other/广告页)必须不被点色乱认, 老实交 OCR 兜底。

用法(游戏目录): python -X utf8 test_zero_ocr.py [-v]      # 退出码 0 = 全通过
"""
import argparse
import glob
import hashlib
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import colorprint as cp
from PIL import Image

import pick_print as pp
from pages import ALL_PAGES
from pages.base import route_prints

FP_PAGES = {p.name for p in ALL_PAGES if p.fingerprints()}


def md5(path):
    with open(path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def holdout():
    """shots_live 里没进过语料的真机帧 -> [(帧, 标签)]

    标签取自文件名 dbg_NNN_<page>_<hhmmss>.png(那一轮真机日志判出来的页)。
    这些帧从没参与指纹标定 —— 拿它们测才是「识别成功之后, 新来的帧还认不认」的真话。
    """
    seen = {md5(p) for p in glob.glob(os.path.join(ROOT, 'shots', '*.png'))}
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, 'shots_live', 'dbg_*.png'))):
        m = re.match(r'dbg_\d+_(\w+?)_(\d+)\.png', os.path.basename(p))
        if not m or md5(p) in seen:
            continue
        out.append((p, pp.group_of(m.group(1))))
    return out


def frame_arr(path):
    # 真机帧 -> 参考分辨率数组(和 pp.load 同一套缩放, 否则坐标对不上)
    im = Image.open(path).convert('RGB')
    if im.size != cp.REF_SIZE:
        im = im.resize(cp.REF_SIZE)
    return cp.to_arr(im)


def frames():
    # 待测帧 -> (帧名, 数组, 页面身份, 语料/留出)
    # 坑: pp.corpus() 的第三元素是 load() 出来的 ndarray, 不是文件路径。
    for lbl, name, arr in pp.corpus():
        yield os.path.basename(name), arr, pp.group_of(lbl), '语料'
    for path, lbl in holdout():
        yield os.path.basename(path), frame_arr(path), lbl, '留出'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-v', '--verbose', action='store_true', help='逐帧打印')
    a = ap.parse_args()
    fails, rows, missed = [], {}, 0
    frames_in = list(frames())
    n_hold = sum(1 for _f, _a, _l, k in frames_in if k == '留出')
    t0 = time.time()
    for fname, arr, lbl, kind in frames_in:
        page, score, src = route_prints(ALL_PAGES, arr)
        got = page.name if page else None
        if lbl in FP_PAGES:
            ok = src is not None and got == lbl
            if not ok:
                missed += 1
                fails.append('%s %s 期望 %s, 实际 %s %s %.3f -> 主循环这一轮要白跑一次全图 OCR'
                             % (kind, fname, lbl, got, src, score))
        else:                              # 没指纹的帧: 认不出来是对的, 乱认才是事故
            ok = src is None
            if not ok:
                fails.append('%s %s 无指纹帧被点色乱认成 %s %s %.3f'
                             % (kind, fname, got, src, score))
        r = rows.setdefault(lbl, [0, 0])
        r[0] += 1
        r[1] += int(ok)
        if a.verbose:
            print('  %-4s %-4s %-11s %-11s %-13s %.3f %s'
                  % ('ok' if ok else 'BAD', kind, lbl, got or '-', src or 'OCR兜底',
                     score, fname))
    dt = time.time() - t0
    n = len(frames_in)
    print('定页面只用点色: %d 张(标定语料 %d / 真机留出 %d)' % (n, n - n_hold, n_hold))
    for lbl, (tot, hit) in sorted(rows.items()):
        print('  %-4s %-11s %3d/%3d 点色定页%s'
              % ('OK' if tot == hit else 'BAD', lbl, hit, tot,
                 '' if lbl in FP_PAGES else '   <- 本页无指纹, 按设计交 OCR'))
    print('平均 %.1f ms/帧; 需要 OCR 兜底的指纹页帧: %d' % (dt * 1000.0 / max(n, 1), missed))
    loaded = [m for m in sys.modules if 'rapidocr' in m or 'paddle' in m or m == 'vision']
    if loaded:
        fails.append('扫描过程竟然 import 了 OCR 相关模块: %s' % loaded)
    print('')
    if fails:
        print('不通过 %d 项:' % len(fails))
        for m in fails:
            print('  - ' + m)
        return 1
    print('全部通过: 有指纹的帧 100% 点色定页, 全程没碰 OCR')
    return 0


if __name__ == '__main__':
    sys.exit(main())