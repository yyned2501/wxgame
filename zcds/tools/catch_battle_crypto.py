"""
catch_battle_crypto.py - 游戏对战时高频 dump 堆, 抓 mini-data 加密的明文↔密文对
目标: 找到 (a) 业务请求明文 JSON (对战参数), (b) 对应 base64 密文, (c) randomAesKey
"""
import ctypes, ctypes.wintypes as wt, re, json, time, sys, os
K = ctypes.WinDLL('kernel32', use_last_error=True)
OP = K.OpenProcess; RPM = K.ReadProcessMemory; VQ = K.VirtualQueryEx
class MBI(ctypes.Structure):
    _fields_=[('BaseAddress',wt.LPVOID),('AllocationBase',wt.LPVOID),('AllocationProtect',wt.DWORD),('RegionSize',ctypes.c_size_t),('State',wt.DWORD),('Protect',wt.DWORD),('Type',wt.DWORD)]

pid = int(sys.argv[1]) if len(sys.argv) > 1 else 9512
h = OP(0x0010|0x1000, False, pid)
addr=0x10000; mbi=MBI(); regions=[]
while True:
    if not VQ(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)): break
    ba=mbi.BaseAddress
    if ba is None: break
    rs=int(mbi.RegionSize)
    if mbi.State==0x1000 and (mbi.Protect&0xEE) and rs < 200*1024*1024: regions.append((int(ba),rs))
    addr=int(ba)+rs
    if addr>0x7fffffffffff or addr<=0: break
print(f'pid {pid}: {len(regions)} regions')

BIZ = ['attack','defend','army','troop','march','soldier','castle','tower','battle','match','arena',
       'territory','coord','hex','building','ArchitectureId','deploy','energy','pvp','Pvp','PVP',
       'challenge','room','Room','player','target','defense','unit','wave','startBattle','result']
seen_pt=set(); seen_ct=set(); keys=set()
def scan(d, base):
    # 明文业务 JSON
    for m in re.finditer(rb'\{[^{}]{6,400}\}', d):
        try: s=m.group().decode('utf-8')
        except: continue
        if '"encrypt"' in s or 'nowTime' in s or 'adzType' in s or 'login_errorcode' in s: continue
        hits=[b for b in BIZ if b in s]
        if len(hits)>=2 and s not in seen_pt:
            seen_pt.add(s)
            print(f'\n[PLAIN @0x{base+m.start():x}] ({",".join(hits[:5])}) {s[:300]}')
    # base64 密文 (encrypt 字段值)
    for m in re.finditer(rb'"encrypt":"([A-Za-z0-9+/=]{80,})"', d):
        b=m.group(1).decode()
        if b not in seen_ct:
            seen_ct.add(b)
            print(f'[CIPHER @0x{base+m.start():x}] len={len(b)} {b[:70]}...')
    # 16 字符高熵 ascii (randomAesKey)
    for m in re.finditer(rb'(?:[\x21-\x7e]\x00){16}', d):
        s=bytes(bb for bb in m.group() if bb)
        if len(s)==16 and re.fullmatch(rb'[A-Za-z0-9]{16}', s) and re.search(rb'[0-9]',s) and re.search(rb'[a-z]',s) and re.search(rb'[A-Z]',s):
            if s not in keys:
                keys.add(s)
                print(f'[KEY? @0x{base+m.start():x}] {s.decode()}')

n=int(sys.argv[2]) if len(sys.argv)>2 else 25
for i in range(n):
    for ba,rs in regions:
        try:
            buf=ctypes.create_string_buffer(rs); nr=ctypes.c_size_t(0)
            if RPM(h, wt.LPCVOID(ba), buf, rs, ctypes.byref(nr)):
                scan(buf.raw[:nr.value], ba)
        except: pass
    time.sleep(1.0)
    if i%5==0: print(f'--- iter {i}: plain={len(seen_pt)} cipher={len(seen_ct)} keys={len(keys)}')
K.CloseHandle(h)
print(f'\nDONE plain={len(seen_pt)} cipher={len(seen_ct)} keys={len(keys)}')
json.dump({'plain':list(seen_pt)[:50],'cipher':list(seen_ct)[:50],'keys':[k.decode() for k in keys][:50]},
          open('tools/battle_crypto.json','w'), ensure_ascii=False, indent=1)
