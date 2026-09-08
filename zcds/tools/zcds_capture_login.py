"""
zcds_capture_login.py - 安全版:
1. 启动 mitmdump 监听 8080
2. 设 Windows 系统代理
3. 不杀任何进程
4. 等 bot 自然触发登录 (sessionKey 过期 或 玩家主动操作)
5. 捕获 cszdz-cn-wx.sereypath.com 流量到 capture_live.bin
"""
import subprocess, time, os, sys

CAPTURE_FILE = r'C:\projects\wxgame\zcds\capture\mitm_live.bin'
os.makedirs(os.path.dirname(CAPTURE_FILE), exist_ok=True)

# 1. 启动 mitmdump
print('[*] 启动 mitmdump on :8080 ...')
proc = subprocess.Popen([
    'C:\\Users\\YY\\AppData\\Local\\Programs\\Python\\Python312\\Scripts\\mitmdump.exe',
    '--listen-port', '8080',
    '--ssl-insecure',
    '-w', CAPTURE_FILE,
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(f'[*] mitmdump PID={proc.pid}')
time.sleep(3)

# 2. 设系统代理
print('[*] 设置系统代理...')
r = subprocess.run(['netsh', 'winhttp', 'set', 'proxy', '127.0.0.1:8080'], capture_output=True, text=True)
print('  ' + r.stdout.strip() + r.stderr.strip())

# 3. 监控 (不杀进程)
print('[*] 等待流量 (bot sessionKey 过期自动重登 OR 玩家操作触发)...')
print('[*] Ctrl-C 退出')
try:
    for i in range(60):  # 10 分钟
        time.sleep(10)
        # 检查捕获文件大小
        sz = os.path.getsize(CAPTURE_FILE) if os.path.exists(CAPTURE_FILE) else 0
        # 检查 WeChat 进程
        out = subprocess.check_output(['tasklist', '/FO', 'CSV'], text=True, encoding='utf-8', errors='replace')
        n = sum(1 for line in out.splitlines() if 'WeChatAppEx' in line)
        print(f'  [{i*10}s] capture={sz}b  WeChatAppEx x {n}')
        if sz > 1000 and sz > 0:
            print(f'[*] 有流量了! 文件 {sz} 字节')
            break
except KeyboardInterrupt:
    pass

# 4. 清理
print('[*] 清理...')
subprocess.run(['netsh', 'winhttp', 'reset', 'proxy'], capture_output=True)
proc.terminate()
try: proc.wait(timeout=3)
except: proc.kill()

# 5. 显示结果
if os.path.exists(CAPTURE_FILE):
    sz = os.path.getsize(CAPTURE_FILE)
    print(f'[*] 最终捕获 {CAPTURE_FILE} = {sz} 字节')
    if sz > 0:
        # 用 mitmdump 解析
        r = subprocess.run([
            'C:\\Users\\YY\\AppData\\Local\\Programs\\Python\\Python312\\Scripts\\mitmdump.exe',
            '-r', CAPTURE_FILE, '--set', 'flow_detail=0'
        ], capture_output=True, text=True, timeout=10)
        # 找 cszdz 相关
        for line in r.stdout.split('\n'):
            if 'cszdz' in line.lower() or 'auth/login' in line:
                print('  ', line[:200])
else:
    print('[*] 无流量')

print('[*] done')
