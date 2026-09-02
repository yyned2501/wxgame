# -*- coding: utf-8 -*-
"""占城大师 后台自动挂机 v3.1 (CPU 优化版)

架构:
  battle_scan.py    战斗页颜色扫描(无 OCR, ~10ms): 白=可点/红=钱不够, 石矿识别
  vision.py         特征提取层: 指纹门控 + ROI OCR(线程数/轮询均受限)
  pages/*.py        页面层: 每页一个模块(特征/动作/预期跳转)
  auto_bot.py       主循环: 指纹门控 -> 页面路由 -> 动作 -> 转移校验

CPU 优化:
  - 战斗页零 OCR: 全部用颜色扫描
  - 其他页面: 画面没大变化不 OCR; 每页按 roi 裁剪 + 限线程(ocr_config.yaml)
  - 微信进程优先级降为 BelowNormal(可 --no-low-cpu 关闭)
"""
import argparse, logging, os, subprocess, sys, time
from datetime import datetime

import game_utils as g
from config import PAGE_CFG
from vision import Vision
from pages import ALL_PAGES
from pages.base import route

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(ROOT, 'bot.log')


def setup_logging():
    os.makedirs(os.path.join(ROOT, 'shots'), exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE, encoding='utf-8')])


class App:
    """主循环 + 页面执行上下文(ctx)"""

    def __init__(self, max_battles=0, dry_run=False, low_cpu=True, affinity_cores=0):
        self.max_battles = max_battles
        self.dry_run = dry_run
        self.low_cpu = low_cpu
        self.affinity_cores = affinity_cores
        self.hwnd = None
        self.vision = None
        self.pages = ALL_PAGES
        # 页面执行上下文
        self.f = None                    # 当前 ScreenFeature
        self.battles = 0
        self.clicked_cells = set()
        self.last_cell = 0
        self.last_action = {}
        self.unknown_idle = 0
        self.expected = None             # 动作后期望的页面集合
        self.cur_page = None
        self.reocr = 'full'              # None | 'full' | 'roi'(内部保留)
        self._act_gap = 3.0
        self._skip_act = False

    # ---- 上下文工具(供页面调用) ----
    def click(self, x, y):
        if self.dry_run:
            logging.info(f'[dry] 点击 ({x},{y})')
            return
        import ctypes, ctypes.wintypes as wt
        u32 = ctypes.windll.user32
        h = self._widget()
        if not h:
            logging.error('找不到渲染窗口')
            return
        wr = wt.RECT(); u32.GetWindowRect(h, ctypes.byref(wr))
        gr = wt.RECT(); u32.GetWindowRect(self.hwnd, ctypes.byref(gr))
        px = int(x) - (gr.left - wr.left)
        py = int(y) - (gr.top - wr.top)
        lp = (py << 16) | (px & 0xFFFF)
        u32.SendMessageW(h, 0x0200, 0, lp)
        u32.SendMessageW(h, 0x0201, 0x0001, lp)
        time.sleep(0.06)
        u32.SendMessageW(h, 0x0202, 0, lp)

    def _widget(self):
        import ctypes, ctypes.wintypes as wt
        u32 = ctypes.windll.user32
        h = None
        def cb(w, lp):
            nonlocal h
            buf = ctypes.create_unicode_buffer(256)
            u32.GetClassNameW(w, buf, 256)
            if 'RenderWidgetHost' in buf.value:
                rc = wt.RECT(); u32.GetWindowRect(w, ctypes.byref(rc))
                if rc.right - rc.left > 50 and rc.bottom - rc.top > 50:
                    h = w
                    return False
            return True
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
        u32.EnumChildWindows(self.hwnd, WNDENUMPROC(cb), 0)
        return h or u32.ChildWindowFromPoint(self.hwnd, ctypes.wintypes.POINT(100, 100))

    def acted(self, key, gap=None):
        """动作冷却: True=还在冷却期(跳过); False=可以执行并刷新"""
        gap = gap or self._act_gap
        now = time.time()
        if now - self.last_action.get(key, 0) < gap:
            return True
        self.last_action[key] = now
        return False

    def ensure_window(self):
        if self.hwnd is None or not g.u32.IsWindow(self.hwnd):
            self.hwnd = g.find_game_window()
            if self.hwnd is None:
                raise RuntimeError('找不到游戏窗口, 请先打开 占城大师')
            self.vision = Vision(self.hwnd)
            self.reocr = 'full'

    def apply_low_cpu(self):
        """把微信进程优先级降到 BelowNormal(+可选限核), 降低对系统的抢占"""
        if not self.low_cpu:
            return
        script = os.path.join(ROOT, 'tools', 'set_low_cpu.ps1')
        if not os.path.exists(script):
            logging.warning('缺少 tools/set_low_cpu.ps1, 跳过降优先级')
            return
        cmd = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
               '-File', script, '-Priority', 'BelowNormal']
        if self.affinity_cores:
            cmd += ['-AffinityCores', str(self.affinity_cores)]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=30)
            if r.returncode:
                logging.warning('降低微信优先级异常: %s',
                                r.stderr.decode('utf-8', 'replace')[:200])
            else:
                logging.info('已降低微信进程优先级' +
                             (f' 并限 {self.affinity_cores} 核' if self.affinity_cores else ''))
        except Exception as e:
            logging.warning('降低微信优先级失败(可忽略): %s', e)

    def step(self):
        """跑一轮: 指纹门控取特征 -> 路由页面 -> 动作 -> 转移校验.
        返回 (page, acted, ocr_ran)"""
        fg = PAGE_CFG.get(self.cur_page, PAGE_CFG['unknown'])
        full = self.reocr == 'full' or self.vision.changed_big
        region = None if full else fg['roi']
        scale = 0.5 if full else fg['scale']
        self.f, ocr_ran = self.vision.current(
            region, scale=scale, force=(self.reocr is not None),
            min_gap=fg['ocr_gap'])
        self.reocr = None
        # 点色指纹全中 = 确认页面, 命中即免 OCR; 没全中才回退 OCR 打分
        page, score, src = route(self.pages, self.f, prefer=self.expected or ())
        logging.info(f'[指纹] {page.name} {src} {score:.2f}')
        # 转移校验
        if self.expected and page.name not in self.expected and page.name != 'unknown':
            logging.info(f'[转移] 预期{self.expected} 实际->{page.name}')
        if page.name != self.cur_page:
            logging.info(f'[状态] {self.cur_page} -> {page.name}')
            self.cur_page = page.name
            self.unknown_idle = 0
            self.expected = None
            # 每场战斗的棋盘都是新的: 进入战斗页必须清空"已点过的格子",
            # 否则 clicked_cells 只增不减, 打几场之后所有格子都被永久拉黑 -> 战斗页不再动手
            if page.name == 'battle':
                self.clicked_cells.clear()
                self.last_cell = 0
            # 刚进入页面时, 上一轮多半是全图OCR(小字会丢) -> 补一轮本页ROI OCR
            if self.reocr is None and page.name != 'battle':
                self.reocr = 'roi'
            # 进入页面的第一轮不动作, 等ROI特征补齐
            self._skip_act = True
        acted = False if self._skip_act else page.act(self)
        self._skip_act = False
        if acted:
            if page.name == 'battle':
                self.reocr = None             # 战斗继续靠颜色扫描
            else:
                self.reocr = 'full'           # 点了会跳页的按钮 -> 下轮全图
            if page.next_pages and page.name != 'battle':
                self.expected = set(page.next_pages)
        elif not acted and page.name not in ('battle', 'matching', 'unknown'):
            self.expected = None
        return page, acted, ocr_ran

    # ---- 主循环 ----
    def run(self):
        self.ensure_window()
        self.apply_low_cpu()
        logging.info('=' * 60)
        logging.info(f'占城大师后台挂机 v3.1 max_battles={self.max_battles or "无限"} '
                     f'dry_run={self.dry_run} low_cpu={self.low_cpu} '
                     f'affinity={self.affinity_cores or "不限"}')
        logging.info(f'窗口={self.hwnd}  开始={datetime.now():%H:%M:%S}')
        while True:
            try:
                self.ensure_window()
                page, acted, _ = self.step()
                if self.max_battles and self.battles >= self.max_battles:
                    logging.info(f'达到目标场次 {self.max_battles}, 结束')
                    break
                fg = PAGE_CFG.get(self.cur_page, PAGE_CFG['unknown'])
                time.sleep(fg['poll'])
            except KeyboardInterrupt:
                logging.info('手动中断')
                break
            except Exception as e:
                logging.exception('循环异常: %s', e)
                time.sleep(8)
        logging.info('挂机结束')


def main():
    ap = argparse.ArgumentParser(description='占城大师自动挂机 (CPU 优化版)')
    ap.add_argument('--max-battles', type=int, default=0, help='打满 N 场后退出, 0=无限')
    ap.add_argument('--dry-run', action='store_true', help='只打印行为不真点')
    ap.add_argument('--no-low-cpu', action='store_true', help='不降低微信进程优先级')
    ap.add_argument('--affinity', type=int, default=0, help='微信进程限 N 个CPU核(0=不限)')
    a = ap.parse_args()
    setup_logging()
    g.enter_default_desktop()
    try:
        App(a.max_battles, a.dry_run, low_cpu=not a.no_low_cpu,
            affinity_cores=a.affinity).run()
    except Exception as e:
        logging.exception('启动失败: %s', e)
    input('按回车退出...')


if __name__ == '__main__':
    main()
