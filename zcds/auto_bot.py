# -*- coding: utf-8 -*-
"""占城大师 后台自动挂机 v3.1 (CPU 优化版)

架构:
  battle_scan.py    战斗页颜色扫描(无 OCR, ~10ms): 白=可点/红=钱不够, 石矿识别
  vision.py         特征提取层: grab() 零 OCR 抓帧 + ocr() 按需(线程数/轮询均受限)
  pages/*.py        页面层: 每页一个模块(点色指纹/动作/预期跳转/act_needs_ocr)
  auto_bot.py       主循环: 点色定页(全中/软命中, 零OCR) -> 要读字的页才 OCR 本页ROI -> 动作 -> 转移校验

设计铁律: 点色优先(用户 2026-09-03 定案) —— OCR 又慢又不准, 定页面、点哪里,
  能用颜色就绝不碰 OCR。真机实测一轮: 点色全表 2.2ms / 全图 OCR 675ms / 本页 ROI OCR 369ms。
  每页用 act_needs_ocr 声明动作层是否真需要读字(价格护栏/按钮文案), 不需要的整轮零 OCR;
  声明不需要但临时要读字的(弹窗文字关闭键), 用 ctx.need_text() 惰性补一次。

CPU 优化:
  - 战斗页零 OCR: 全部用颜色扫描
  - 指纹全中的纯点色页零 OCR; 其他页面只裁本页 roi + 限线程(ocr_config.yaml)
  - 微信进程优先级降为 BelowNormal(可 --no-low-cpu 关闭)

窗口尺寸:
  点色指纹是在 552x1006 基准尺寸上标定的, 窗口一旦被缩放, 色块就错位 -> 指纹层整片失效.
  因此机器人启动后每轮都会把窗口钉回基准尺寸(可 --no-resize 关闭).
"""
import argparse, logging, os, subprocess, sys, time
from datetime import datetime

import game_utils as g
from colorprint import REF_SIZE
from config import PAGE_CFG
from vision import Vision, ScreenFeature
from pages import ALL_PAGES
from pages.base import detect_ocr, is_soft, route_prints

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(ROOT, 'bot.log')
# 软命中(点色差<=1个指纹点)要连续这么多帧同一页才允许动手:
# 转场/动画中间帧不会连着两帧长得一样, 稳住了才点, 免得误点。
SOFT_ACT_AFTER = 2


def setup_logging():
    os.makedirs(os.path.join(ROOT, 'shots'), exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE, encoding='utf-8')])


class App:
    """主循环 + 页面执行上下文(ctx)"""

    def __init__(self, max_battles=0, dry_run=False, low_cpu=True, affinity_cores=0,
                 resize=True, max_steps=0, shots=0):
        self.max_battles = max_battles
        self.dry_run = dry_run
        self.low_cpu = low_cpu
        self.affinity_cores = affinity_cores
        self.resize = resize             # 每轮把窗口钉回指纹基准尺寸
        self.max_steps = max_steps   # >0: 跑满 N 轮退出(dry-run 冒烟用)
        self.shots = shots      # >0: 每轮存帧 -> shots_live/dbg_*.png (取证用)
        self.steps = 0
        self._win_warn = 0
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
        self._act_gap = 3.0
        self.print_confirmed = False     # 本轮页面是否由点色指纹确认(动作层据此免检)
        self._text_done = False          # 本轮这帧是否已经跑过 OCR(need_text 不重复花销)
        self._soft_page = None           # 上一帧软命中的页(软命中要连续若干帧才算稳)
        self._soft_streak = 0

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
            self.vision = Vision(self.hwnd)   # 新引擎首轮必然 OCR, 不必再置标记
            self._win_warn = 0

    def ensure_window_size(self):
        """把窗口钉回指纹标定的基准尺寸 REF_SIZE(点色色块对尺寸极敏感)"""
        if not self.resize:
            return
        w0, h0 = g.window_size(self.hwnd)
        if w0 < 2 or h0 < 2:
            return                     # 假句柄/离线测试: 没有真实窗口, 不折腾也不刷日志
        ok, w, h = g.set_window_size(self.hwnd, REF_SIZE[0], REF_SIZE[1])
        if (w0, h0) != (w, h):
            logging.info('[窗口] 尺寸 %dx%d -> %dx%d (指纹基准 %dx%d)',
                         w0, h0, w, h, REF_SIZE[0], REF_SIZE[1])
            if self.vision is not None:
                self.vision.reset()      # 画面缩放后旧特征与 OCR 缓存全部作废
        if not ok:
            self._win_warn += 1
            if self._win_warn % 10 == 1:
                logging.warning('[窗口] 无法设为 %dx%d, 实际 %dx%d -> 指纹层可能失效 '
                                '(不想自动改窗口就加 --no-resize)',
                                REF_SIZE[0], REF_SIZE[1], w, h)
        else:
            self._win_warn = 0

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

    # ---- 惰性文字特征(点色优先) ----
    def need_text(self):
        """点色命中时默认不跑 OCR; 动作层真需要读字, 才现补一次本页 ROI OCR(每轮至多一次)"""
        if self._text_done or self.f is None:
            return self.f
        self._text_done = True
        fg = PAGE_CFG.get(self.cur_page, PAGE_CFG['unknown'])
        self.f, _ = self.vision.ocr(self.f.img, region=fg['roi'], scale=fg['scale'],
                                    min_gap=fg['ocr_gap'])
        return self.f

    def _soft_stable(self, name):
        """软命中是否已连续 SOFT_ACT_AFTER 帧同一页(= 这帧画面稳了, 可以按它动手)"""
        if self._soft_page == name:
            self._soft_streak += 1
        else:
            self._soft_page, self._soft_streak = name, 1
        return self._soft_streak >= SOFT_ACT_AFTER

    def step(self):
        """跑一轮: 点色定页(零 OCR) -> 只有声明要读字的页才 OCR 本页 ROI -> 动作.
        返回 (page, acted, ocr_ran)"""
        self.ensure_window_size()
        img = self.vision.grab()
        self._text_done = False
        # 1) 定页只看点色指纹: 实测 2ms 判完全表, 同样的轮次跑全图 OCR 要 675ms
        page, score, src = route_prints(self.pages, img, prefer=self.expected or ())
        soft = is_soft(src)
        defer = False
        if page is None:
            # 2) 点色连"差一个点"的软命中都没有(新页面/被别的窗口遮挡) -> 才允许花一次全图 OCR
            self.f, ocr_ran = self.vision.ocr(img, force=True)
            self._text_done = True
            page, score = detect_ocr(self.pages, self.f)
            src = 'ocr' if page.name != self.pages[-1].name else 'unknown'
            self.print_confirmed = False
            self._soft_page, self._soft_streak = None, 0
        else:
            self.print_confirmed = True
            src = 'print-' + src
            if not soft:
                self._soft_page, self._soft_streak = None, 0
            else:
                defer = not self._soft_stable(page.name)
            if defer:
                # 3a) 软命中头一帧: 页面身份认下了, 但这帧差点(动画/转场) -> 不动手也不跑 OCR
                self.f = ScreenFeature(img=img, boxes=[], joined='')
                ocr_ran = False
            elif page.act_needs_ocr:
                # 3) 动作层非读文字不可 -> 只裁本页 ROI, 且受该页 ocr_gap 节流
                fg = PAGE_CFG.get(page.name, PAGE_CFG['unknown'])
                self.f, ocr_ran = self.vision.ocr(
                    img, region=fg['roi'], scale=fg['scale'], min_gap=fg['ocr_gap'])
                self._text_done = True
            else:
                # 纯点色页: 整轮零 OCR, 只把帧交给动作层
                self.f = ScreenFeature(img=img, boxes=[], joined='')
                ocr_ran = False
        logging.info(f'[指纹] {page.name} {src} {score:.2f}')
        if defer:
            logging.warning(f'[指纹-软] {page.name} {score:.2f} 差<=1点·第{self._soft_streak}/'
                            f'{SOFT_ACT_AFTER}帧未稳 -> 本轮不动作, 也不花 OCR')
            return page, False, ocr_ran
        if soft:
            logging.warning(f'[指纹-软] {page.name} {score:.2f} 连续{self._soft_streak}帧 -> '
                            f'按稳定帧放行(依然不跑全图 OCR)')
        # --shots N: 取证模式, 每轮把当前帧存到 shots_live/dbg_*.png
        if self.shots:
            self.shots -= 1
            d = os.path.join(ROOT, 'shots_live')
            os.makedirs(d, exist_ok=True)
            fn = 'dbg_{0:03d}_{1}_{2}.png'.format(
                self.steps, page.name, time.strftime('%H%M%S'))
            try:
                self.f.img.save(os.path.join(d, fn))
                logging.info(f'{"[DRY]" if self.dry_run else ""}[存帧] {fn}')
            except Exception as e:
                logging.warning('[存帧] 失败: %s', e)
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
        # 点色定完页、该读的字已经备好 -> 同一轮就能出手。
        # 旧版进页第一轮只补特征不动作(_skip_act), 每换一页白扔一轮, 已删除。
        acted = page.act(self)
        if acted and page.next_pages and page.name != 'battle':
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
                self.steps += 1
                if self.max_steps and self.steps >= self.max_steps:
                    logging.info(f'达到目标轮数 {self.max_steps}, 结束')
                    break
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
    ap.add_argument('--max-steps', type=int, default=0, help='最多跑 N 轮后退出, 0=不限 (dry-run 冒烟用)')
    ap.add_argument('--dry-run', action='store_true', help='只打印行为不真点')
    ap.add_argument('--shots', type=int, default=0, help='每轮存帧到 shots_live/dbg_*.png, 存 N 帧(取证用)')
    ap.add_argument('--no-low-cpu', action='store_true', help='不降低微信进程优先级')
    ap.add_argument('--affinity', type=int, default=0, help='微信进程限 N 个CPU核(0=不限)')
    ap.add_argument('--no-resize', action='store_true',
                    help=f'不自动把窗口调成指纹基准尺寸 {REF_SIZE[0]}x{REF_SIZE[1]}')
    a = ap.parse_args()
    setup_logging()
    g.enter_default_desktop()
    try:
        App(a.max_battles, a.dry_run, low_cpu=not a.no_low_cpu,
            affinity_cores=a.affinity, resize=not a.no_resize,
            max_steps=a.max_steps, shots=a.shots).run()
    except Exception as e:
        logging.exception('启动失败: %s', e)
    input('按回车退出...')


if __name__ == '__main__':
    main()
