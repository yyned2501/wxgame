# -*- coding: utf-8 -*-
"""离线路由回归: 点色指纹 -> route() 的完整决策链(不开窗口, 不跑 OCR)

tools/pick_print.py verify 只测 match_print(纯指纹层); 本脚本补 auto_bot.step()
真正调用的 route(): 指纹优先 -> prefer(上一步声明的转移候选) -> OCR 兜底 -> unknown.

用法(项目根目录): python -X utf8 test_print_route.py     # 退出码 0 = 全通过
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from PIL import Image

import colorprint as cp                        # 判色原语(造「只差一个点」的帧)
import pick_print as pp                        # 复用同一份语料标注, 不两处维护
from pages import ALL_PAGES
from pages.base import detect_ocr, is_soft, route, route_prints, soft_hit
from vision import ScreenFeature, TBox

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print('  FAIL  ' + msg)


class _Fake:
    """软命中门限测试用的假页(只要 name 参与打分)"""

    def __init__(self, name):
        self.name = name


def blotch(img, pt, color=(0, 0, 0), r=1):
    """遮住单个判色点: 只涂该点自己的 3x3(pos_tol=1 的取样域)。

    指纹是「十字 5 点」一组组标出来的, 涂满 7x7 会一次干掉整组(5 个点),
    那是「页面真的变了」而不是动画遮挡 -> 本用例要复现的是差 1 个点这种最琐碎的情况。
    """
    x, y = pt[0], pt[1]
    a = np.asarray(img).copy()
    a[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1] = color
    return Image.fromarray(a)


def feat(name, text='', size=None):
    """造一帧真实的 ScreenFeature: img 用语料截图, joined 手喂(等价一次 OCR 结果)

    size 非空则把帧缩到该尺寸, 用来复现"玩家拖动了窗口 -> 指纹层整片失效"的真机场景。
    """
    img = Image.open(pp.img_path(name)).convert('RGB')
    if size and img.size != size:
        img = img.resize(size, Image.LANCZOS)
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
            check(pg.name in ('ad_popup', 'claim_popup', 'diamond_popup', 'unknown'),
                  '%s 没有指纹且不在允许只走 OCR 的清单里' % pg.name)
    check(ALL_PAGES[-1].name == 'unknown', 'ALL_PAGES 最后一项必须是 unknown(兜底)')
    print('    %d/%d 页已标点色指纹; 只走 OCR: %s'
          % (n_fp, len(ALL_PAGES), ', '.join(p.name for p in ALL_PAGES if not p.fingerprints())))

    print('[6] OCR 同分 tie-break: 常驻文案不得把大厅抢成 VIP 弹窗')
    # 真机陷阱: 大厅右上角一直挂着"月卡", 和 vip_popup 的关键词同分(都 1.0);
    # ALL_PAGES 里 vip_popup 排在 lobby 前面 -> 旧版按注册顺序取先出现的最大值, 会误判成弹窗。
    txt = '玩家对战 月卡 特权 购买礼包'      # 大厅常驻"月卡" => 与 vip_popup 的 detect 同分 1.0
    for sz in [(431, 788), (500, 911)]:      # 窗口被拖动缩放 -> 指纹没全中, 只能走 OCR 兜底
        f6 = feat('live_lobby', text=txt, size=sz)
        p6, s6 = detect_ocr(ALL_PAGES, f6)
        check(p6.name == 'lobby', '%dx%d 同分应判 lobby, 实际 %s %.2f' % (sz + (p6.name, s6)))
        # 缩放过的帧点色可能仍能「软命中」(指纹按整帧比例换算), 但绝不能被同分的 vip_popup 抢走
        p6b, _s6b, src6 = route(ALL_PAGES, f6, prefer=())
        check(p6b.name == 'lobby' and (src6 == 'ocr' or src6.startswith('print')),
              '%dx%d 路由应落 lobby(点色/软命中/ocr 都行), 实际 %s %s' % (sz + (p6b.name, src6)))
    # 反过来: 只剩弹窗文案(没有"玩家对战")时, 不得被 tie-break 抢给大厅
    f6c = feat('live_lobby', text='购买礼包 月卡 特权', size=(431, 788))
    p6c, _ = detect_ocr(ALL_PAGES, f6c)
    check(p6c.name == 'vip_popup', '只有弹窗文案时应照旧判 vip_popup, 实际 %s' % p6c.name)

    print('[7] 顶栏闸门: 指纹不得只靠顶栏资源数字(y<130)')
    # 真机教训: 旧 lobby 指纹 15 个点全落在金币/钻石数字上, 语料里恰好数值相同 -> 70/70 是假绿灯,
    # 换个账号/资源一变就整片失效。lobby 已重新标定到 y>=130, 这里钉死; 其余页只报警不判失败。
    for pg in ALL_PAGES:
        ys = [y for fp in pg.fingerprints() for xy in fp for y in (xy[1],)]
        if not ys:
            continue
        if pg.name == 'lobby':
            check(min(ys) >= 130, 'lobby 指纹落进顶栏数字区(最小 y=%d < 130)' % min(ys))
        elif max(ys) < 130:
            print('    !! %s 的指纹全在顶栏 y<130 (%d~%d): 换账号数值即失效, 需真机补拍再重标'
                  % (pg.name, min(ys), max(ys)))


    print('[8] 宝箱槽位坐标: 必须落在实测卡片矩形内部(旧值 y=741 在卡片外, 真机 19 次点空)')
    import numpy as np
    from pages.lobby import CHEST_SLOTS, CHEST_BAND

    def card_grid(path):
        """不靠人工标注, 直接从像素反推 4 张宝箱卡片的矩形 -> (y0, y1, [(x0,x1), ...])"""
        a = np.asarray(Image.open(path).convert('RGB')).astype(int)
        r, g2, b = a[..., 0], a[..., 1], a[..., 2]
        bg = (b < 130) & (r < 60)                     # 卡片之间/两侧的深色底
        prof = [bg[y, 40:512].mean() for y in range(700, 905)]
        on = [(p > 0.10) and (p < 0.45) for p in prof]  # 一行里正好"4 张卡 + 3 条缝"
        best, s = (0, 0, 0), None
        for i, v in enumerate(on):
            if v and s is None:
                s = i
            if (not v or i == len(on) - 1) and s is not None:
                if i - s > best[0]:
                    best = (i - s, s + 700, i - 1 + 700)
                s = None
        y0, y1 = best[1], best[2]
        cols = [bg[y0:y1 + 1, x].mean() < 0.35 for x in range(40, 512)]
        runs, s = [], None
        for i, v in enumerate(cols):
            if v and s is None:
                s = i
            if (not v or i == len(cols) - 1) and s is not None:
                if i - s >= 40:
                    runs.append((s + 40, i - 1 + 40))
                s = None
        return y0, y1, runs

    LV = os.path.join(ROOT, 'shots_live')
    geo = [os.path.join(ROOT, 'shots', n + '.png') for n in
           ('lobby_clean', 'after_battle_btn', 'live_20260902_a')]
    geo += [os.path.join(LV, f) for f in (sorted(os.listdir(LV)) if os.path.isdir(LV) else [])
            if f.startswith('probe_ref_')]
    for gp in geo:
        y0, y1, runs = card_grid(gp)
        base = os.path.basename(gp)
        check(y1 - y0 > 100, '%s 卡片带太窄: %d..%d' % (base, y0, y1))
        for i, (sx, sy) in enumerate(CHEST_SLOTS):
            check(any(x0 <= sx <= x1 for x0, x1 in runs),
                  '%s 槽%d x=%d 落在卡片外, 列块=%s' % (base, i + 1, sx, runs))
            check(y0 + 20 <= sy <= y1 - 8,
                  '%s 槽%d y=%d 出卡片纵向范围(%d..%d)' % (base, i + 1, sy, y0, y1))
        check(CHEST_BAND[0] <= y0 + 10 and CHEST_BAND[1] >= y0 + 30,
              '%s CHEST_BAND=%s 罩不住卡片顶部的倒计时角标(y%d..%d)'
              % (base, CHEST_BAND, y0, y0 + 30))
        print('    %-28s 卡片带 y%d..%d  列块 %s' % (base, y0, y1, runs))


    print('[9] _ready_chests: 判据=卡片底部按钮文字(真机 23:35 定案: 点击解锁=免费可点)')
    from pages.lobby import LobbyPage, CHEST_SLOTS as SLOTS

    def card(cx, cy, text):
        """模拟一个 OCR 框: 宽 80 高 24, 中心落在 (cx,cy)"""
        return TBox(text, cx - 40, cy - 12, 80, 24)

    def with_boxes(name, boxes):
        f = feat(name)
        f.boxes = list(boxes)
        f.joined = ' '.join(x.text for x in f.boxes)
        return f

    lp = LobbyPage()
    # 真机实测偏移(语料 lobby_clean): 标题/按钮文字都比槽位中心偏左 ~25px, 角标偏左 ~14px
    # 常驻横幅"竞技场4解锁"在 y=641(CARD_BAND 之外), x=384 距槽4 中心 57px(>45) -> 双重安全
    BANNER = card(384, 641, '竞技场4解锁')

    def badge(i, text):
        return TBox(text, SLOTS[i][0] - 14 - 40, 741 - 12, 80, 24)

    # a) 4 格全空 + 4 个"所需时长"角标 + 常驻横幅 -> 一个都不能点
    empty = ([card(sx - 29, 817, '空槽位') for sx, _ in SLOTS]
             + [badge(i, t) for i, t in enumerate(('5分', '10分', '5分', '05分'))]
             + [BANNER])
    r = lp._ready_chests(with_boxes('lobby_clean', empty))
    check(r == [], '4 格全空却仍判为可开, 实际 %s' % (r,))

    # b) 槽1 摆着宝箱(标题 竞技场2 + 底部 点击解锁) -> 只返回槽1(横幅不得算成槽4)
    one = [card(109 - 27, 826, '竞技场2'), card(109 - 26, 855, '点击解锁'),
           card(220 - 29, 817, '空槽位'), badge(1, '10分'), BANNER]
    r = lp._ready_chests(with_boxes('lobby_clean', one))
    check(r == [SLOTS[0]], '槽1[点击解锁]应返回槽1, 实际 %s' % (r,))

    # c) 关键回归: 角标"20分"是**开箱所需时长**, 不是剩余倒计时 -> 仍必须判为可点
    #    (旧版 TIMER_RE 把它当冷却, 真机上 4 个免费宝箱一律误判成"忙", 永远不开箱)
    r = lp._ready_chests(with_boxes('lobby_clean', one + [badge(0, '20分')]))
    check(r == [SLOTS[0]], '所需时长角标 20分 不得当成冷却, 实际 %s' % (r,))

    # d) 已解锁正在倒计时: 底部按钮变成"[AD] -30分钟" -> 跳过(点它=看广告, WATCH_ADS=False)
    cool = [card(109 - 27, 826, '竞技场2'), card(109 - 26, 857, '-30分钟')]
    r = lp._ready_chests(with_boxes('lobby_clean', cool))
    check(r == [], '倒计时槽位必须跳过, 实际 %s' % (r,))
    # d2) 同一形态但角标被 OCR 读成乱码(真机 23:49 读成 00时5分13脖) -> 判据在按钮行, 不误报
    r = lp._ready_chests(with_boxes('lobby_clean', cool + [badge(0, '00时5分13脖')]))
    check(r == [], '角标乱码时仍须靠按钮行判冷却, 实际 %s' % (r,))

    # d3) 关键回归(真机 23:55): 倒计时归零后按钮写[开启], 但 OCR 经常读成"开咖"
    #     -> 排除式判据照样认它是免费按钮(正面匹配"解锁|开启"会漏掉已经能领的宝箱)
    r = lp._ready_chests(with_boxes('lobby_clean',
                                    [card(114, 826, '竞技场2'), card(110, 858, '开咖')]))
    check(r == [SLOTS[0]], 'OCR 把[开启]读成[开咖]时必须仍能领, 实际 %s' % (r,))
    # d4) 按钮行只写"30分钟"(真机丢了负号) -> 必须跳过, 点它是看广告
    r = lp._ready_chests(with_boxes('lobby_clean',
                                    [card(114, 826, '竞技场2'), card(123, 860, '30分钟')]))
    check(r == [], '按钮写 30分钟(广告加速)必须跳过, 实际 %s' % (r,))
    check(r == [], '角标乱码时仍须靠按钮行判冷却, 实际 %s' % (r,))

    # e) 没有任何 OCR 框(只靠指纹命中) -> 保守不点
    r = lp._ready_chests(with_boxes('lobby_clean', []))
    check(r == [], '无 OCR 数据时应返回空, 实际 %s' % (r,))

    # f) 4 格全[点击解锁](语料 lobby_clean 的真实形态, 含所需时长角标) -> 全返回, 保持左到右
    allc = ([card(sx - 29, 818, '竞技场1') for sx, _ in SLOTS]
            + [card(sx - 26, 854, '点击解锁') for sx, _ in SLOTS]
            + [badge(i, t) for i, t in enumerate(('5分', '10分', '5分', '05分'))]
            + [BANNER])
    r = lp._ready_chests(with_boxes('lobby_clean', allc))
    check(r == list(SLOTS), '4 格全[点击解锁]应全返回, 实际 %s' % (r,))

    # g) 真机 23:34 那张 lobby_clean 原图 OCR 形态: 4 个免费宝箱不能漏
    real = [TBox('5分', 55, 729, 80, 24), TBox('5分', 277, 729, 80, 24),
            TBox('05分', 388, 729, 80, 24), TBox('10分', 162, 730, 80, 24),
            TBox('竞技场1', 146, 804, 80, 24), TBox('竞技场1', 262, 804, 80, 24),
            TBox('竞技场1', 376, 807, 80, 24), TBox('竞技场1', 486, 805, 80, 24),
            TBox('点击解锁', 43, 841, 80, 24), TBox('点击解锁', 155, 843, 80, 24),
            TBox('点击解锁', 265, 841, 80, 24), TBox('点击解锁', 376, 841, 80, 24),
            TBox('竞技场4解锁', 295, 620, 100, 24)]
    r = lp._ready_chests(with_boxes('lobby_clean', real))
    check(r == list(SLOTS), 'lobby_clean 原图 4 个免费宝箱应全判可点, 实际 %s' % (r,))

    print('[10] 软命中门限: 差<=1 点且甩开第二名才放行, 差 2 点交回 OCR')
    # 门限本身用假分数直接钉死(不必造图, 也不会随语料漂移)
    pa, pb = _Fake('a'), _Fake('b')
    check(soft_hit([(14 / 15, 15, pa, 'order')])[0] is pa, '15 点差 1 个应软命中')
    # soft_hit 只回原始来源, '-soft' 后缀由 match_print 打(端到端见下面的真图用例)
    check(soft_hit([(24 / 25, 25, pa, 'order')])[2] == 'order', '软命中须保留原始来源(order)')
    check(soft_hit([(24 / 25, 25, pa, 'prefer')])[2] == 'prefer', '软命中须保留原始来源(prefer)')
    check(soft_hit([(24 / 25, 25, pa, 'order'), (0.9, 25, pb, 'order')])[0] is None,
          '只甩开 0.06(<0.20)不得软命中')
    check(soft_hit([(28 / 30, 30, pa, 'order')])[0] is None, '差 2 点不得软命中')
    check(soft_hit([(0.0, 0, pa, 'order')])[0] is None, '没指纹的页(点数<8)不得白捡软命中')
    for base, lbl in (('live_lobby', 'lobby'), ('battle_full', 'battle')):
        img0 = Image.open(pp.img_path(base)).convert('RGB')
        pg = [q for q in ALL_PAGES if q.name == lbl][0]
        p, sc, src = route_prints(ALL_PAGES, img0)
        check(p is pg and not is_soft(src),
              '%s(%s) 原图应点色全中, 实际 %s %s %.3f' % (base, lbl, p and p.name, src, sc))
        crit = next((xy for xy in pg.fingerprints()[0] if pg.print_score(blotch(img0, xy)) < 1.0), None)
        check(crit is not None, '%s 找不到「遮住就不全中」的关键点, 该页指纹形同虚设?' % base)
        if crit:
            p, sc, src = route_prints(ALL_PAGES, blotch(img0, crit))
            check(p is pg and is_soft(src),
                  '%s(%s) 遮 1 个点应软命中(不许跑 OCR), 实际 %s %s %.3f'
                  % (base, lbl, p and p.name, src, sc))
            others = [xy for xy in pg.fingerprints()[0] if xy != crit]
            p, sc, src = route_prints(ALL_PAGES, blotch(blotch(img0, crit), others[0]))
            check(p is None,
                  '%s(%s) 遮 2 个点该交 OCR 兜底, 实际 %s %s %.3f' % (base, lbl, p and p.name, src, sc))
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
