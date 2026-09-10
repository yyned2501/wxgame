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

WINSTA_ALL_ACCESS = 0x037F          # 窗口站点全权(切桌面必须用它, 见 enter_default_desktop 注释)
DESKTOP_MIN_RIGHTS = 0x0001 | 0x0002 | 0x0008 | 0x0100   # READOBJECTS|CREATEWINDOW|HOOKCONTROL|SWITCH


def desktop_is_interactive():
    """本线程当前挂的桌面能不能看见真实窗口(有带标题的可见顶层窗口就算能)"""
    seen = [0]

    def cb(hwnd, _lp):
        if u32.IsWindowVisible(hwnd) and u32.GetWindowTextLengthW(hwnd) > 0:
            seen[0] += 1
            return False
        return True

    u32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)(cb), 0)
    return seen[0] > 0


def enter_default_desktop(force=False):
    """把进程/线程挂到 WinSta0\\Default, 让非交互上下文(sandbox/服务)里启动的脚本也看得见游戏窗口。

    返回 (是否真的切了, 一句话说明) —— 调用方负责打日志。force=True 无视自查强切。

    🔴 两条实测坑(2026-09-04 真机 R35 取证, COLORPRINT.md 30.8):
      1) OpenWindowStationW 的访问掩码必须是 WINSTA_ALL_ACCESS(0x37F)。旧代码只给
         0x0001(WINSTA_READATTRIBUTES), 切完之后本线程的**屏幕 DC 被废**: GetDC(0)+BitBlt
         出来整帧 0 像素(capture_screen 全黑), 而 PrintWindow / EnumWindows / 鼠标消息
         全都照常 —— 症状就是 bot 进程里 ads_*.png 全黑、同一时刻独立进程抓屏幕 mean≈146。
         单开桌面(SetThreadDesktop)不背这个锅, 只开站点(SetProcessWindowStation)就复现。
      2) 切换有代价, 所以默认先自查: 本来就在交互桌面上直接跳过, 一行都不动。
    """
    if not force and desktop_is_interactive():
        return False, '已在交互桌面 -> 不切(SetProcessWindowStation 低权限掩码会废掉屏幕通道)'
    hws = u32.OpenWindowStationW('WinSta0', False, WINSTA_ALL_ACCESS)
    how = 'WINSTA_ALL_ACCESS'
    if not hws:
        hws = u32.OpenWindowStationW('WinSta0', False, 0x0001)   # 退一步: 宁可丢屏幕通道也要保住窗口可见性
        how = 'WINSTA_READATTRIBUTES(降级, 屏幕通道会全黑)'
    if hws:
        u32.SetProcessWindowStation(hws)
    hdt = u32.OpenDesktopW('Default', 0, False, DESKTOP_MIN_RIGHTS)
    if hdt:
        u32.SetThreadDesktop(hdt)
    return True, '已切 WinSta0\\Default: station=%s(%s) desktop=%s' % (hws, how, hdt)

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
    """打印窗口内容, 返回 PIL RGB 图像

    自检(2026-09-10): PrintWindow(PW_RENDERFULLCONTENT) 在某些场景下(游戏窗口被反复点
    击后变非前台 / 某些 Win10/11 上对 chromium 内核的非前台窗口)会抓不到 webview 内容,
    只返回窗口 chrome 残影. 实测正常帧均值 ~93, 失灵帧均值 ~5, 屏幕通道同期帧均值 ~98.
    现在: PrintWindow 帧均值 < 100 时, 抓一张 capture_screen 对比; 均值差 > 10 -> 失灵,
    fallback 到 capture_screen 通道. 绝大多数时候不增加开销(只在怀疑失灵时才跑对比).
    """
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
    img = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1).convert('RGB')
    # ---- PrintWindow 失灵自检 ----
    try:
        import numpy as np
        gray = float(np.asarray(img.convert('L'), dtype=np.float32).mean())
        if gray < 100.0:
            sc = capture_screen(hwnd)
            sc_gray = float(np.asarray(sc.convert('L'), dtype=np.float32).mean())
            if abs(gray - sc_gray) > 10.0:
                # PrintWindow 失灵, 走屏幕通道兜底
                import logging
                logging.warning('[抓帧] PrintWindow 失灵 (PW 均值 %.1f, 屏幕 %.1f, 差 %.1f) -> fallback capture_screen',
                                gray, sc_gray, abs(gray - sc_gray))
                return sc, ok
    except Exception:
        pass
    return img, ok

def capture_screen_rect(x, y, w, h):
    """抓**屏幕上**这块矩形里实际显示的像素(和 capture_window 的窗口自绘是两条不同通道)。

    为什么需要第二条通道: 微信小游戏的激励视频是 GPU 合成的独立层, PrintWindow 抓不到
    它(真广告帧实测整屏纯黑、只剩顶栏 5~6% 非黑像素)。于是"窗口自绘里还是游戏页"就有
    两种完全不同的解释: A 广告压根没起来 / B 广告在屏幕上盖着、只是 PrintWindow 看不见。
    同一时刻再抓一张屏幕像素就能分清 —— 两条通道一致才敢判 A。
    前提: 目标区域没被别的窗口盖住(脚本点[领取]前会先把游戏窗口带到前台)。
    """
    hsrc = u32.GetDC(0)
    memdc = gdi32.CreateCompatibleDC(hsrc)
    bmp = gdi32.CreateCompatibleBitmap(hsrc, w, h)
    old = gdi32.SelectObject(memdc, bmp)
    gdi32.BitBlt(memdc, 0, 0, w, h, hsrc, x, y, 0x00CC0020)   # SRCCOPY
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
    u32.ReleaseDC(0, hsrc)
    img = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1)
    return img.convert('RGB')


def capture_screen(hwnd):
    """抓窗口在屏幕上实际显示的那块像素(矩形取自 get_rect, 和 capture_window 同尺寸)"""
    left, top, right, bottom = get_rect(hwnd)
    return capture_screen_rect(left, top, right - left, bottom - top)


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

# ---- 抢前台(GetForegroundWindow 必须声明 restype, 否则 64 位句柄会被截成 32 位 int) ----
u32.GetForegroundWindow.restype = wt.HWND
u32.SetForegroundWindow.argtypes = [wt.HWND]
u32.BringWindowToTop.argtypes = [wt.HWND]


def focus_window(hwnd):
    """把游戏窗口带到前台, 返回最终是否真的在前台。

    为什么非做不可: 微信小游戏的激励视频是 XWEB 的独立渲染层, 窗口被别的程序盖住时
    可能直接不给量。真机 2026-09-04 R33 后台点了 6 次[领取]一次广告都没起来, 而
    2026-08-24 12:47 用户在场(窗口在前台)同样的点击 12s 后就放起了广告。

    Windows 有"前台锁": 只有当前前台进程才准换前台, 直接 SetForegroundWindow 常常只
    让任务栏图标闪一下。所以失败时用标准的 Alt 键技巧绕过 —— 按一下 Alt 会让系统认为
    本线程刚收到过输入, 紧接着的 SetForegroundWindow 就合法了。
    """
    fg = lambda: int(u32.GetForegroundWindow() or 0)
    if fg() == int(hwnd):
        return True
    u32.SetForegroundWindow(hwnd)
    if fg() == int(hwnd):
        return True
    VK_MENU, KEYUP = 0x12, 0x0002
    u32.keybd_event(VK_MENU, 0, 0, 0)
    u32.keybd_event(VK_MENU, 0, KEYUP, 0)
    u32.BringWindowToTop(hwnd)
    u32.SetForegroundWindow(hwnd)
    time.sleep(0.15)
    return fg() == int(hwnd)


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
