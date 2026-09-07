"""
dump_renderer.py - 读 WeChatAppEx 渲染进程的实时堆/模块内存
不依赖 Frida (被 anti-debug 挡), 用 Windows API OpenProcess + VirtualQueryEx + ReadProcessMemory
扫所有可读 region (含堆), 找加密 key / session / openId
"""
import ctypes, ctypes.wintypes as wt
import sys, os, re, base64, time

KERNEL32 = ctypes.WinDLL('kernel32', use_last_error=True)
PSAPI    = ctypes.WinDLL('psapi', use_last_error=True)

OpenProcess = KERNEL32.OpenProcess
OpenProcess.restype = wt.HANDLE
OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]

ReadProcessMemory = KERNEL32.ReadProcessMemory
ReadProcessMemory.restype = wt.BOOL
ReadProcessMemory.argtypes = [wt.HANDLE, wt.LPCVOID, wt.LPVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]

VirtualQueryEx = KERNEL32.VirtualQueryEx
VirtualQueryEx.restype = ctypes.c_size_t
VirtualQueryEx.argtypes = [wt.HANDLE, wt.LPCVOID, ctypes.c_void_p, ctypes.c_size_t]

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('BaseAddress', wt.LPVOID),
        ('AllocationBase', wt.LPVOID),
        ('AllocationProtect', wt.DWORD),
        ('RegionSize', ctypes.c_size_t),
        ('State', wt.DWORD),
        ('Protect', wt.DWORD),
        ('Type', wt.DWORD),
    ]

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MEM_COMMIT = 0x1000
PAGE_READABLE = 0x00000004 | 0x00000002 | 0x00000010 | 0x00000020 | 0x00000040 | 0x00000080

def enum_regions(pid):
    """枚举所有 PAGE_READABLE + MEM_COMMIT 的 region"""
    h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h: return [], None
    addr = 0
    regions = []
    mbi = MEMORY_BASIC_INFORMATION()
    last_end = 0
    while True:
        if not VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        if mbi.State == MEM_COMMIT and (mbi.Protect & PAGE_READABLE):
            regions.append((mbi.BaseAddress, mbi.RegionSize))
        ba = mbi.BaseAddress or last_end
        try:
            sz = int(mbi.RegionSize)
        except: sz = 0x1000
        addr = (ba if isinstance(ba, int) else int(ba)) + sz
        last_end = addr
        if addr > 0x7fffffffffff or addr <= 0: break
    return regions, h

def scan_pid(pid, markers, key_min=20, key_max=48, region_cap=50):
    regions, h = enum_regions(pid)
    if not h:
        print(f'[!] OpenProcess pid={pid} failed err={ctypes.get_last_error()}')
        return {}
    print(f'[*] pid={pid} regions={len(regions)}')
    results = {m:[] for m in markers}
    key_hits = []
    buf = ctypes.create_string_buffer(8*1024*1024)
    nread = ctypes.c_size_t(0)
    scanned = 0
    for addr, sz in regions[:region_cap]:
        if sz > 100*1024*1024: continue   # 跳过 >100MB region
        try:
            chunk = min(sz, 8*1024*1024)
            if not ReadProcessMemory(h, wt.LPCVOID(addr), buf, chunk, ctypes.byref(nread)):
                continue
            scanned += nread.value
            data = buf.raw[:nread.value]
            # 1. markers
            for m in markers:
                start = 0
                while True:
                    idx = data.find(m, start)
                    if idx < 0: break
                    results[m].append((addr + idx, data[idx:idx+min(80, nread.value-idx)]))
                    start = idx + 1
            # 2. base64-like keys (20-48 长度, 不像英文/路径)
            for mm in re.finditer(rb'(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{20,48}=*(?![A-Za-z0-9+/])', data):
                s = mm.group()
                if len(s) not in (24, 32, 40, 44, 48): continue
                if b'/' in s: continue
                vowels = sum(c in b'aeiouAEIOU' for c in s)
                if vowels > len(s)*0.3: continue
                consec = 0; max_consec = 0
                for c in s:
                    if 65 <= c <= 90 or 97 <= c <= 122:
                        consec += 1; max_consec = max(max_consec, consec)
                    else: consec = 0
                if max_consec >= 7: continue
                # 尝试 base64 解码
                try:
                    raw = base64.b64decode(s + b'=' * (-len(s) % 4))
                    if len(raw) not in (16, 24, 32): continue
                    key_hits.append((addr + mm.start(), s, raw))
                except: pass
        except Exception as e: pass
    print(f'[*] scanned {scanned/1024/1024:.1f} MB')
    return results, key_hits

if __name__ == '__main__':
    target_pid = int(sys.argv[1]) if len(sys.argv) > 1 else 20828
    markers = [
        b'wx9eed71970378b2ae',
        b'cszdz-cn-wx',
        b'Base64KeyStr',
        b'SPEncrypt1_0',
        b'LoginAESKey',
        b'XyxLogin',
        b'URLEncodeTools',
        b'sessionKey',
        b'AESCryptor',
    ]
    res, keys = scan_pid(target_pid, markers)
    print()
    for m, hits in res.items():
        print(f'  {m.decode():25s} hits={len(hits)}')
        for addr, ctx in hits[:3]:
            try: txt = ctx.decode('utf-8','replace')
            except: txt = ctx.hex()
            print(f'    @0x{addr:x}: {txt[:80]!r}')
    print()
    if keys:
        print(f'[*] base64 key 候选 ({len(keys)} 个):')
        seen = set()
        for addr, s, raw in keys:
            if s in seen: continue
            seen.add(s)
            print(f'    @0x{addr:x}  {s.decode():40s} -> {raw.hex()}')
    else:
        print('[*] 无 base64 key 候选')
