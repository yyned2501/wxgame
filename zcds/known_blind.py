# -*- coding: utf-8 -*-
"""「设计内压暗盲区」分类器 —— 把 COLORPRINT.md §32 那类帧从"零 OCR 闸门"里单独摘出来

2026-09-04 真机第 37 轮: 战斗里蹦出「传说卡牌来袭! 5% 超幸运!」全屏过场动画, 它盖住整屏
把**每一个像素压暗**(全帧 mean 168.9 -> 137.2), battle 的 3 个十字单元(推条 x2 + 气泡)
同时全灭 => 点色定不出页, 主循环那一轮白跑一次全图 OCR(真机 675ms); 动画放完(6~9s)自己恢复。

闸门里的两种失败必须分开对待:
  硬失败(零容忍)   点色把一帧**认成了另一页** —— 这会点错按钮, 一次都不许有。
  设计内成本(有账) 整帧被动画压暗导致"谁都没认领" —— 代价只是慢一次 OCR, 不会点错。
不给这种帧补"压暗形态"指纹的硬理由(§32.2): 压暗**不是等比缩放**(蓝条三通道系数
1.03/0.82/0.80, 气泡 0.855/0.854/0.854, 两组不一致), 动画本身还在动 => 硬凑的形态会在别的帧
制造"假全中", 比零命中危险得多。也别想用"比语料均值暗多少"当判据: battle 语料本身就
128.6~160.7 双峰(差 32 灰阶), 任何一条亮度阈值都会误伤或放水。

所以放行只看**一条独立证据**, 四个条件全满足才算, 少一条照旧报回归:
  1) 点色**谁都没认领**(src is None) 且全表最高分 < SOFT_MIN_MARGIN —— 有页贴着门限抢就不许放过
  2) 文件名是 bot 自己存的证据帧: dbg_NNN_<页>_<hhmmss>.png 或 ocr_<页>_<hhmmss>.png
  3) <页> 是**已经有指纹**的页 —— 冒出新页面必须报(新页面的标签只会是 unknown, 过不了这条)
  4) 有**独立第二份证据**说明真机当场拿全图 OCR 复核过、认回来的还是这一页
     => 页面身份没错, 只是花了一次 OCR。两种存证分别要求:
       dbg_ 帧: 同一秒(±2s)存在 ocr_ 同名兄弟, 且两张图逐字节相同(md5 相等);
       ocr_ 帧: **自证** —— 文件名里的页名就是那一次全图 OCR 的判决本身。
     为什么 ocr_ 不能再要求双胞胎: self.shots 是**取证倒数计数器**, --shots 用完之后
     dbg_ 帧就不再落盘, 而 ocr_ 帧还在按自己的节奏存 -> 语料每长一张 ocr_ 帧这道闸门
     就必红一次(2026-09-04 R40 12:43:11 实证: ocr_battle_124311.png 没有兄弟帧,
     test_popup_escape[5] 由绿转红)。放宽它不扩大放水边界: 双胞胎的两个页名来自
     **同一次判决**, 对"OCR 把新页面误认成老页"这条已知边界本来就不提供额外保护,
     兜它的是条件 1/2/3 + blind_cap + test_dim_frame 的 590 次压暗复核。

已知放水边界: 如果真机把一张**新页面**用 OCR 认成了某个老页(标签写进文件名), 第 4 条也会放行。
兜这条的是 1)"没人来抢"、5)盲区帧数上界 blind_cap()、以及 test_dim_frame.py 的
"295 语料 x 两档压暗 = 590 次判定, 误判成别的页必须 0"。

用法(回归脚本里):
    from known_blind import unclaimed_note, blind_cap
    why = unclaimed_note(path, score=score, src=src)
"""
import glob
import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
for _p in (ROOT, os.path.join(ROOT, 'tools')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pages import ALL_PAGES                    # noqa: E402
from pages.base import SOFT_MIN_MARGIN         # noqa: E402

DIM_SLACK = 2          # 同一次 step 里两张落盘最多差 2 秒
BLIND_RATIO = 0.005    # 盲区帧数上界 = 有指纹帧总数 x 0.5%(再多就不是"偶发动画")
BLIND_FLOOR = 4        # 上界的绝对下限

# bot 存证据帧的两种命名(页名 = 那一轮判出来的页): dbg_NNN_<页>_<hhmmss> / ocr_<页>_<hhmmss>
EVID = re.compile(r'^(?:dbg_(\d+)_|ocr_)(\w+?)_(\d{6})\.png$')
FP_PAGES = {p.name for p in ALL_PAGES if p.fingerprints()}
_MD5 = {}


def md5(path):
    if path not in _MD5:
        with open(path, 'rb') as f:
            _MD5[path] = hashlib.md5(f.read()).hexdigest()
    return _MD5[path]


def _sec(hhmmss):
    s = int(hhmmss)
    return (s // 10000) * 3600 + (s // 100 % 100) * 60 + s % 100


def parse(path):
    """证据帧路径 -> (页名, 秒) ; 不是证据帧 -> None"""
    m = EVID.match(os.path.basename(str(path)))
    if not m:
        return None
    return m.group(2), _sec(m.group(3))


def paired_evidence(path):
    """找"同一帧的第二次落盘" -> 兄弟文件名 / 'self'(OCR 帧自证); 没有 -> None

    dbg_ 和 ocr_ 是同一次 step 里对**同一个数组**写的两份文件, 所以 dbg_ 要求逐字节相同;
    ocr_ 帧本身就是那次全图 OCR 的判决存证(_save_ocr_shot 只在点色没人认领那一轮调用),
    页名是它自己写出来的 -> 再找兄弟只是重复计数, 按自证处理(原因见模块 docstring 条件 4)。
    """
    p = parse(path)
    base = os.path.basename(str(path))
    if not p or p[0] not in FP_PAGES:
        return None
    page, sec = p
    d = os.path.dirname(str(path))
    if base.startswith('ocr_'):
        return 'self'
    # dbg_ -> 找 ocr_ 兄弟(同一次 step 对同一个数组写的两份文件)
    pat = os.path.join(d, 'ocr_%s_*.png' % page)
    for q in glob.glob(pat):
        q2 = parse(q)
        if not q2 or q2[0] != page:
            continue
        if abs(q2[1] - sec) > DIM_SLACK:
            continue
        try:
            if md5(q) == md5(path):
                return os.path.basename(q)
        except OSError:
            continue
    return None


def unclaimed_note(path, score, src, margin=SOFT_MIN_MARGIN):
    """点色定不出页的一帧: 是设计内盲区 -> 返回理由(会被打印); 否则 None = 必须算进闸门"""
    if src is not None:
        return None                            # 有页认领 -> 走正常判定(认错页零容忍)
    if score >= margin:
        return None                            # 有页贴着软命中门限抢 -> 必须人看
    q = paired_evidence(path)
    if not q:
        return None
    if q == 'self':
        return ('§32 压暗盲区: 点色无人认领(全表最高分 %.3f < %.2f), '
                '本帧就是 bot 存证的 OCR 判决帧, 页名 = 真机当场全图 OCR 的判决 -> %s'
                % (score, margin, os.path.basename(str(path))))
    return ('§32 压暗盲区: 点色无人认领(全表最高分 %.3f < %.2f), '
            '真机同一次 step 的全图 OCR 复核回同一页 -> %s 与本帧逐字节相同'
            % (score, margin, q))


def blind_cap(n_fp_frames):
    return max(BLIND_FLOOR, int(n_fp_frames * BLIND_RATIO))