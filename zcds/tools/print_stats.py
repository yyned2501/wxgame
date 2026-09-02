# -*- coding: utf-8 -*-
"""用 shots 语料实测各页点色指纹, 重算/校正 pages/*.py 指纹块上方的统计注释.

用法:
    python -X utf8 tools\\print_stats.py            # 写回注释行
    python -X utf8 tools\\print_stats.py --dry-run  # 只打印, 不改文件

只改写那一行注释; 绝不碰 points / prints 字面量(要改坐标请用 pick 重标).
行尾统一 CRLF(顺带修复误产生的混合行尾).
"""
import argparse, os, re, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import colorprint as cp          # noqa: E402
import pick_print as pp          # noqa: E402
from pages import ALL_PAGES      # noqa: E402

PAT = re.compile(r'^\s*#.*种形态.*判色点')


def stats_for(page, own, foreign):
    fps = page.fingerprints()
    hit = sum(1 for a in own if page.print_match(a))
    bad = sum(1 for l, a in foreign if page.print_match(a))
    margin = max([max(cp.print_score(a, s2, page.degree, page.pos_tol) for s2 in fps)
                  for _l, a in foreign] + [0.0])
    cover = [sum(1 for a in own if cp.is_multi_color(a, s2, page.degree, page.pos_tol))
             for s2 in fps]
    return fps, hit, bad, margin, cover


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='只打印统计, 不写回注释')
    args = ap.parse_args()

    cor = pp.corpus()
    print('%-12s %-6s %-6s %-6s %-9s %-8s %-7s %s'
          % ('page', 'forms', 'pts/fm', 'units', 'own-hit', 'foreign', 'margin', 'cover'))
    for p in ALL_PAGES:
        fps = p.fingerprints()
        if not fps:
            print('%-12s (无指纹, 只走 OCR)' % p.name)
            continue
        own = [a for l, n, a in cor if pp.group_of(l) == p.name]
        foreign = [(l, a) for l, n, a in cor if pp.group_of(l) != p.name]
        fps, hit, bad, margin, cover = stats_for(p, own, foreign)
        npts = len(fps[0])
        per = npts // 5
        print('%-12s %-6d %-6d %-6d %-9s %-8s %-7.2f %s'
              % (p.name, len(fps), npts, per, '%d/%d' % (hit, len(own)), bad, margin, cover))
        new = ('    # %d 种形态 x %d 个十字单元(每单元 5 点, 共 %d 判色点/形态), '
               '任一形态全中即判为 %s; '
               '语料 %d/%d 全中 / 异页误中 %d / margin %.2f(异页最高只中 %.0f/%d 点) / '
               '各形态覆盖 %s 帧'
               ) % (len(fps), per, npts, p.name, hit, len(own), bad, margin,
                    margin * npts, npts, cover)
        if args.dry_run:
            print('        -> ' + new.strip())
            continue
        path = os.path.join(ROOT, 'pages', p.name + '.py')
        raw = open(path, 'rb').read()
        nb = 0
        while raw[nb * 3:nb * 3 + 3] == b'\xef\xbb\xbf':
            nb += 1
        if nb > 1:
            print('        !! 多重 BOM, 跳过 %s' % path)
            continue
        bom = b'\xef\xbb\xbf' if nb else b''
        lines = [ln.rstrip('\r\n') for ln in raw[3 * nb:].decode('utf-8').splitlines(True)]
        tail = '\r\n' if raw.endswith(b'\n') else ''
        done = 0
        for i, ln in enumerate(lines):
            if PAT.match(ln):
                lines[i] = new
                done += 1
        if not done:
            print('        !! 没找到统计注释行, 未改写: %s' % path)
            continue
        open(path, 'wb').write(bom + '\r\n'.join(lines).encode('utf-8') + tail.encode('utf-8'))
        print('        已写回 %d 行' % done)


if __name__ == '__main__':
    main()
