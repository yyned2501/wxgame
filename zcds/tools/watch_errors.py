# -*- coding: utf-8 -*-
"""挂机 24h 错误监控: 实时扫 bot.log, 输出新增 ERROR / WARNING.

严重信号(主循环崩溃 / 活锁 / 卡页 / 看不到渲染窗口)立即打印并标红;
非严重 WARNING(广告撒手 / 自检失败 / 存帧失败)累积 30s 一次输出.
末尾追加每分钟一次的统计 (ERROR 数 / WARNING 数 / 战斗数).

用法:
    python tools/watch_errors.py                # 默认扫 zcds/bot.log, 30s 一汇总
    python tools/watch_errors.py --interval 10 # 10s 一汇总
    python tools/watch_errors.py --log path    # 指定别的日志文件
"""
import argparse
import os
import re
import sys
import time
from collections import Counter

# 严重信号: 出现就立刻打印 (不等到下一次汇总), 不打印有可观察延迟
SEVERE_PATTERNS = [
    (re.compile(r'ERROR|循环异常|异常:'),                'red',     '主循环/系统异常'),
    (re.compile(r'\[活锁\]'),                            'red',     '活锁 — 同一坐标反复点'),
    (re.compile(r'\[卡页\]'),                            'yellow',  '卡页 — 连续零动作'),
    (re.compile(r'\[兜底\]'),                            'yellow',  '兜底 — 点色/OCR 失败'),
    (re.compile(r'\[指纹-软\]'),                          'yellow',  '指纹软命中'),
    (re.compile(r'找不到渲染窗口|找不到游戏窗口'),         'red',     '窗口丢了'),
]
# 非严重: WARNING 但不报警, 累积到汇总
PASSIVE_PATTERNS = [
    re.compile(r'\[广告\]'),
    re.compile(r'\[自检\]'),
    re.compile(r'\[窗口\]'),
    re.compile(r'\[存帧\]|\[广告取证\]|\[广告探针\]|\[待标语料\]'),
    re.compile(r'降低微信'),
    re.compile(r'缺少 tools/set_low_cpu\.ps1'),
]

ANSI = {
    'red':    '\033[31m',
    'yellow': '\033[33m',
    'green':  '\033[32m',
    'cyan':   '\033[36m',
    'reset':  '\033[0m',
    'bold':   '\033[1m',
}


def color(s, c):
    """彩色输出 (Windows cmd 也支持 ANSI via VT mode)"""
    if not sys.stdout.isatty():
        return s
    return f'{ANSI.get(c, "")}{s}{ANSI["reset"]}'


def classify(line):
    """返回 ('severe'/'passive'/'info', pattern_name) 或 None"""
    for pat, _c, name in SEVERE_PATTERNS:
        if pat.search(line):
            return 'severe', name
    for pat in PASSIVE_PATTERNS:
        if pat.search(line):
            return 'passive', None
    if re.search(r'\bINFO\b', line):
        return 'info', None
    return 'other', None


def tail_lines(path, since_offset):
    """读文件从 since_offset 起的新行"""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            f.seek(since_offset)
            new_lines = f.readlines()
            new_offset = f.tell()
        return new_lines, new_offset
    except FileNotFoundError:
        return [], since_offset


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--log', default=None, help='bot.log 路径 (默认 zcds/bot.log)')
    ap.add_argument('--interval', type=int, default=30, help='汇总间隔秒数')
    ap.add_argument('--recheck', type=int, default=2, help='紧急信号立即重检间隔秒数')
    args = ap.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = args.log or os.path.join(os.path.dirname(script_dir), 'bot.log')
    print(color(f'[watcher] 启动, 日志={log_path}, 汇总={args.interval}s', 'cyan'))
    print(color(f'[watcher] 严重信号=红/黄立即打印; WARNING 累积到汇总', 'cyan'))

    if not os.path.exists(log_path):
        print(color(f'[watcher] 等待日志文件出现...', 'yellow'))

    # 启动时 seek 到文件末尾, 跳过整个历史日志; 只监控 bot 启动后的新增行
    if os.path.exists(log_path):
        with open(log_path, 'rb') as f:
            f.seek(0, 2)  # 0+SEEK_END = 文件末尾
            offset = f.tell()
        print(color(f'[watcher] 从 offset={offset} 开始监控 (跳过历史日志)', 'cyan'))
    else:
        offset = 0

    last_summary = time.time()
    last_recheck = time.time()
    total_severe = Counter()
    total_warning = 0
    total_info = 0
    initial_wait = True

    while True:
        now = time.time()
        new_lines, offset = tail_lines(log_path, offset)

        if initial_wait and not new_lines and not os.path.exists(log_path):
            time.sleep(2)
            continue
        if initial_wait and new_lines:
            initial_wait = False
            print(color(f'[watcher] 日志开始增长, offset={offset}', 'green'))

        # 严重信号: 立即打印
        for ln in new_lines:
            kind, name = classify(ln)
            if kind == 'severe':
                # 去时间戳前缀的简化显示
                ts = ln.split(' ', 2)[:2]
                ts_str = ' '.join(ts) if len(ts) >= 2 else ln[:20]
                color_c = 'red' if '主循环' in (name or '') or '窗口' in (name or '') else 'yellow'
                print(color(f'[{color_c.upper()}] {ts_str} {name}', color_c))
                print(f'    {ln.rstrip()}')
                total_severe[name] += 1
            elif kind == 'passive':
                total_warning += 1
            elif kind == 'info':
                total_info += 1

        # 紧急重检: 如果有 ERROR 出现, 立刻再扫一次(防漏)
        if any('ERROR' in ln or '循环异常' in ln for ln in new_lines):
            time.sleep(0.5)
            more, offset = tail_lines(log_path, offset)
            for ln in more:
                kind, name = classify(ln)
                if kind == 'severe':
                    print(color(f'[RED-FAST] {name}', 'red'))
                    print(f'    {ln.rstrip()}')
                    total_severe[name] += 1

        # 汇总
        if now - last_summary >= args.interval:
            last_summary = now
            elapsed_min = args.interval / 60.0
            print(color(
                f'\n[汇总] {time.strftime("%H:%M:%S")} '
                f'近 {args.interval}s | '
                f'WARNING={total_warning} | '
                f'INFO={total_info}',
                'cyan'))
            if total_severe:
                for n, c in total_severe.most_common():
                    print(color(f'  - {n}: {c}', 'yellow' if n == '卡页 — 连续零动作' or '兜底' in (n or '') else 'red'))
            total_warning = 0
            total_info = 0
            sys.stdout.flush()

        time.sleep(1)


if __name__ == '__main__':
    main()
