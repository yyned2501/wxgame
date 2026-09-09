# -*- coding: utf-8 -*-
"""窗口/截图/click/drag 封装.

旧 `game_utils.py` 是全局函数模块, 任何地方都能 import 然后直接调 `g.u32.PostMessageW`.
这里封装成类, 注入到 Page. 内部仍 import 旧 game_utils 复用其函数, 等所有页面迁完再删旧模块.

用法:
    win = Window()
    hwnd = win.find_game_window('占城大师')
    img = win.capture(hwnd)
    win.click(ctx, x, y)             # 单点
    win.drag(ctx, x1, y1, x2, y2)    # 拖动
"""
import logging

import game_utils as _g  # 复用旧实现


class Window:
    """窗口交互封装."""

    def __init__(self):
        self.hwnd = None            # 当前活动窗口句柄
        self.widget = None          # RenderWidgetHost 子窗口(click/drag 目标)

    def find(self, title='占城大师'):
        """查找游戏窗口, 返回 hwnd 或 None."""
        self.hwnd = _g.find_game_window(title)
        return self.hwnd

    def is_alive(self):
        """当前 hwnd 仍然有效吗?"""
        return self.hwnd is not None and bool(_g.u32.IsWindow(self.hwnd))

    def capture(self, hwnd=None, flag=0):
        """抓窗口截图, 返回 PIL Image."""
        h = hwnd or self.hwnd
        if h is None:
            raise RuntimeError('没有可用的窗口句柄')
        return _g.capture_window(h, flag=flag)[0]

    def capture_screen(self, hwnd=None):
        """截整个游戏窗口区域(用于缩放)."""
        h = hwnd or self.hwnd
        return _g.capture_screen(h)

    def get_rect(self, hwnd=None):
        """窗口矩形 (left, top, right, bottom)."""
        h = hwnd or self.hwnd
        return _g.get_rect(h)

    def window_size(self, hwnd=None):
        """窗口尺寸 (w, h)."""
        h = hwnd or self.hwnd
        return _g.window_size(h)

    def set_size(self, hwnd, w, h, keep_pos=True):
        """改窗口尺寸到基准 (552x1006)."""
        _g.set_window_size(hwnd, w, h, keep_pos=keep_pos)

    def focus(self, hwnd=None):
        """把窗口带到前台."""
        _g.focus_window(hwnd or self.hwnd)

    def get_widget(self, hwnd=None):
        """查找 RenderWidgetHost 子窗口 (click/drag 真正发到这里)."""
        h = hwnd or self.hwnd
        self.widget = _g._widget.__wrapped__(self) if hasattr(_g._widget, '__wrapped__') else _g._widget(self)
        return self.widget

    def click(self, ctx, x, y, duration=0.08):
        """在窗口坐标 (x, y) 单击. duration=0.08s 按下时间."""
        if self.widget is None:
            self.get_widget()
        if self.widget is None:
            logging.error('找不到渲染窗口')
            return False
        _g.click_window(self.widget, x, y, duration=duration)
        return True

    def drag(self, ctx, x1, y1, x2, y2, steps=10, hold_each=0.02):
        """拖动 (x1,y1) -> (x2,y2). SendMessageW 路径, 不抢前台.
        末尾多发 2 次 UP 兜底(2026-09-08 真机: 防 SendMessageW UP 没生效导致鼠标卡住).
        """
        if self.widget is None:
            self.get_widget()
        if self.widget is None:
            logging.error('找不到渲染窗口')
            return False
        # 委托给 ctx.click 的 SendMessageW 路径(保持与现有 drag() 行为一致)
        import ctypes
        u32 = _g.u32
        gr = _g.get_rect(self.hwnd)
        wr = _g.get_rect(self.widget)
        def to_widget(x, y):
            px = int(x) - (gr[0] - wr[0])
            py = int(y) - (gr[1] - wr[1])
            return (py << 16) | (px & 0xFFFF)
        lp1 = to_widget(x1, y1)
        lp2 = to_widget(x2, y2)
        import time as _t
        u32.SendMessageW(self.widget, 0x0200, 0, lp1)
        u32.SendMessageW(self.widget, 0x0201, 0x0001, lp1)
        _t.sleep(0.05)
        for i in range(1, steps + 1):
            t = i / steps
            mx = x1 + (x2 - x1) * t
            my = y1 + (y2 - y1) * t
            u32.SendMessageW(self.widget, 0x0200, 0x0001, to_widget(mx, my))
            _t.sleep(hold_each)
        u32.SendMessageW(self.widget, 0x0202, 0, lp2)
        # 兜底: 多发 UP, 防止 SendMessageW UP 没生效
        u32.SendMessageW(self.widget, 0x0202, 0, lp2)
        u32.SendMessageW(self.widget, 0x0200, 0, 0)
        u32.SendMessageW(self.widget, 0x0202, 0, 0)
        return True

    def desktop_is_interactive(self):
        """检查桌面是否可交互."""
        return _g.desktop_is_interactive()

    def enter_default_desktop(self, force=False):
        """切到默认桌面."""
        return _g.enter_default_desktop(force=force)

    def acquire_single_instance(self, name='Local\\ZCDS_AutoBot'):
        """互斥量, 防止并发跑."""
        return _g.acquire_single_instance(name=name)