# -*- coding: utf-8 -*-
"""占城大师 微信小游戏自动脚本 - 公共工具: 切桌面、找窗口、截图、点击"""
import ctypes, ctypes.wintypes as wt, time, sys
from PIL import Image

u32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wt.DWORD), ('biWidth', wt.LONG), ('biHeight', wt.LONG),
                ('biPlanes', wt.WORD), ('biBitCount', wt.WORD), ('biCompression', wt.DWORD),
                ('biSizeImage', wt.DWORD), ('biXPelsPerMeter', wt.LONG), ('biYPelsPerMeter', wt.LONG),
                ('biClrUsed', wt.DWORD), ('biClrImportant', wt.DWORD)]
class BITMAPINFO(ctypes.Structure):
    _fields_ = [('bmiHeader', BITMAPINFOHEADER)]

def enter_default_desktop():
    hws = u32.OpenWindowStationW('WinSta0', False, 0x0001)
    u32.SetProcessWindowStation(hws)
    hdt = u32.OpenDesktopW('Default', 0, False, 0x0100 | 0x0002 | 0x0008)
    u32.SetThreadDesktop(hdt)
    return hdt

def find_game_window(title_contains='占城大师'):
    results = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(hwnd, lparam):
        n = u32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        u32.GetWindowTextW(hwnd, buf, n + 1)
        if u32.IsWindowVisible(hwnd) and title_contains in buf.value:
            results.append(hwnd)
        return True
    u32.EnumWindows(EnumWindowsProc(cb), 0)
    return results[0] if results else None

def get_rect(hwnd):
    r = wt.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom

def capture_window(hwnd, flag=2):
    """打印窗口内容, 返回 PIL RGB 图像"""
    left, top, right, bottom = get_rect(hwnd)
    w, h = right - left, bottom - top
    hdc = u32.GetWindowDC(hwnd)
    memdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(memdc, bmp)
    ok = u32.PrintWindow(hwnd, memdc, flag)
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(memdc, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    gdi32.SelectObject(memdc, old)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(memdc)
    u32.ReleaseDC(hwnd, hdc)
    img = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1)
    return img.convert('RGB'), ok

def window_size(hwnd):
    """当前窗口外框尺寸 (w, h); 句柄无效时返回 (0, 0)"""
    left, top, right, bottom = get_rect(hwnd)
    return right - left, bottom - top


def set_window_size(hwnd, w, h, keep_pos=True):
    """把窗口外框设为 w x h —— 点色指纹的标定基准尺寸。

    指纹色块是在 552x1006 上标定的, 窗口一旦被缩放, 色块就错位 -> 指纹层整片失效,
    所以机器人启动/每轮都要把窗口钉回基准尺寸。
    返回 (是否达标, 实际宽, 实际高)。
    """
    cur_w, cur_h = window_size(hwnd)
    if cur_w < 2 or cur_h < 2:
        # 窗口已关 / 假句柄(离线测试): GetWindowRect 拿不到矩形, 不做任何操作
        return False, cur_w, cur_h
    if cur_w == w and cur_h == h:
        return True, cur_w, cur_h
    SW_RESTORE = 9
    if u32.IsZoomed(hwnd):            # 最大化时先还原, 否则 MoveWindow 无效
        u32.ShowWindow(hwnd, SW_RESTORE)
        time.sleep(0.25)
    left, top, _, _ = get_rect(hwnd)
    if not keep_pos:
        left, top = 0, 0
    u32.MoveWindow(hwnd, left, top, w, h, True)
    time.sleep(0.25)
    now_w, now_h = window_size(hwnd)
    return (now_w == w and now_h == h), now_w, now_h

def click_window(hwnd, x, y, duration=0.08):
    """在窗口内坐标 (x, y) 点击 (SendInput)"""
    left, top, right, bottom = get_rect(hwnd)
    sx, sy = left + x, top + y
    ctypes.windll.user32.SetCursorPos(sx, sy)
    time.sleep(0.05)
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    def send(flags):
        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [('dx', wt.DWORD), ('dy', wt.DWORD), ('mouseData', wt.DWORD),
                        ('dwFlags', wt.DWORD), ('time', wt.DWORD), ('dwExtraInfo', ctypes.POINTER(wt.ULONG))]
        class INPUT(ctypes.Structure):
            _anonymous_ = ('mi',)
            _fields_ = [('type', wt.DWORD), ('mi', MOUSEINPUT)]
        mi = MOUSEINPUT(0, 0, 0, flags, 0, None)
        inp = INPUT(0, mi)
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    send(MOUSEEVENTF_LEFTDOWN)
    time.sleep(duration)
    send(MOUSEEVENTF_LEFTUP)
