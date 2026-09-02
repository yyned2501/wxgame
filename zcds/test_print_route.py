# -*- coding: utf-8 -*-
"""离线路由回归: 点色指纹 -> route() 的完整决策链(不开窗口, 不跑 OCR)

tools/pick_print.py verify 只测 match_print(纯指纹层); 本脚本补 auto_bot.step()
真正调用的 route(): 指纹优先 -> prefer(上一步声明的转移候选) -> OCR 兜底 -> unknown.

用法(项目根目录): python -X utf8 test_print_route.py     # 退出码 0 = 全通过
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from PIL import Image

import pick_print as pp                        # 复用同一份语料标注, 不两处维护
from pages import ALL_PAGES
from pages.base import route
from vision import ScreenFeature

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print('  FAIL  ' + msg)


def feat(name, text=''):
    """造一帧真实的 ScreenFeature: img 用语料截图, joined 手喂(等价一次 OCR 结果)"""
    img = Image.open(pp.img_path(name)).convert('RGB')
    return ScreenFeature(img=img, boxes=[], joined=text)


def main():
    corpus = pp.corpus()
    print('[1] 全语料 指纹定页: %d 张' % len(corpus))
    for lbl, name, _ in corpus:
        page, score, src = route(ALL_PAGES, feat(name), prefer=())
        want = pp.group_of(lbl)
        if want == 'other':
            check(not src.startswith('print'),
                  'other %s 不该被指纹命中(实际 %s %s %.2f)' % (name, page.name, src, score))
        else:
            check(page.name == want and src.startswith('print') and score >= 1.0,
                  '%s(%s) 期望 %s, 实际 %s %s %.2f' % (name, lbl, want, page.name, src, score))

    print('[2] prefer(转移候选) 只影响顺序, 不改变结论')
    p, s, src = route(ALL_PAGES, feat('battle_full'), prefer=('battle',))
    check(p.name == 'battle' and src == 'print-prefer', 'battle_full prefer 命中应为 print-prefer, 实际 %s %s' % (p.name, src))
    p, s, src = route(ALL_PAGES, feat('battle_full'), prefer=('lobby',))
    check(p.name == 'battle' and src == 'print-order', 'battle_full prefer 未命中应回落 print-order, 实际 %s %s' % (p.name, src))
    p, s, src = route(ALL_PAGES, feat('chestinfo'), prefer=('lobby',))
    check(p.name == 'chest_info' and src == 'print-order', 'prefer 里的页不得压过真实指纹, 实际 %s %s' % (p.name, src))

    print('[3] 指纹(像素) 优先于文字: 大厅上叠弹窗文案时仍判大厅')
    p, s, src = route(ALL_PAGES, feat('live_lobby', text='购买礼包 月卡 特权 超值'), prefer=())
    check(p.name == 'lobby' and src.startswith('print'),
          '指纹应压过 vip_popup 文案, 实际 %s %s' % (p.name, src))

    print('[4] 指纹没全中 -> 回退 OCR 打分')
    other = [n for lbl, n, _ in corpus if lbl == 'other']
    p, s, src = route(ALL_PAGES, feat(other[0], text='玩家对战'), prefer=())
    check(p.name == 'lobby' and src == 'ocr', '兜底应走 OCR 判 lobby, 实际 %s %s %.2f' % (p.name, src, s))
    p, s, src = route(ALL_PAGES, feat(other[0], text=''), prefer=())
    check(p.name == 'unknown' and src == 'unknown', '指纹和文字都没依据时应 unknown, 实际 %s %s' % (p.name, src))
    for n in other:
        p, s, src = route(ALL_PAGES, feat(n), prefer=())
        check(src in ('ocr', 'unknown'), 'other %s 落到了指纹层 %s %s' % (n, p.name, src))

    print('[5] 页面声明自检')
    n_fp = 0
    for pg in ALL_PAGES:
        fps = pg.fingerprints()
        if fps:
            n_fp += 1
            check(all(len(fp) >= 15 for fp in fps),
                  '%s 有指纹组不足 15 个判色点(3 个十字单元)' % pg.name)
        else:
            check(pg.name in ('claim_popup', 'diamond_popup', 'unknown'),
                  '%s 没有指纹且不在允许只走 OCR 的清单里' % pg.name)
    check(ALL_PAGES[-1].name == 'unknown', 'ALL_PAGES 最后一项必须是 unknown(兜底)')
    print('    %d/%d 页已标点色指纹; 只走 OCR: %s'
          % (n_fp, len(ALL_PAGES), ', '.join(p.name for p in ALL_PAGES if not p.fingerprints())))

    print('')
    if FAILS:
        print('不通过 %d 项:' % len(FAILS))
        for m in FAILS:
            print('  - ' + m)
        return 1
    print('全部通过 (共 %d 张语料)' % len(corpus))
    return 0


if __name__ == '__main__':
    sys.exit(main())
