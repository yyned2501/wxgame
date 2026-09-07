"""
占城大师 API 客户端 v4 —— live 主机已确认 + dump.cs 反编译全套
基于 dump.cs 反编译 + R44 现场抓包验证
依赖: pip install requests cryptography

【已验证】
  现场主机: https://cszdz-cn-wx.sereypath.com:18013  (cszdz-cn-wx.sereypath.com)
  8 个真活端点 (2026-08-24 抓包):
    GET  /mini-data/sys/nowTime                     (明文, server time)
    POST /mini-data/auth/login                      (AES-128-CBC + LoginAESKey 加密)
    POST /mini-data/data/private/get                (业务数据读)
    POST /mini-data/data/private/update             (业务数据写)
    POST /mini-data/data/private/version            (业务数据版本)
    POST /mini-mail/mail/query-count                (邮箱)
    POST /mini-mail/mail/query-new                  (邮箱)
    POST /mini-notice/public/notice                 (公告)
  CDN: oiumwaa-frx.sereypath.com (asset bundles)
  XYX 配置: xig.rayiantway.com:8509/obtain (AES-128-CBC + we20210409dobest)
  /gm/api/* 端点 404 (dump.cs 里有, 生产没部署)

【加密协议】
  XYX obtain 响应: AES-128-CBC + KEY=we20210409dobest, IV 从首块 XOR 推导
  登录请求/响应: URLEncodeTools.SPEncrypt1_0_Encrypt1 (custom, 非标准 AES-CBC)
                KEY=2020we0616dobest, 密文长度非 16 倍数 (505/620/504/611)
                -> 解开需要 wasm 逆向 URLEncodeTools.SPEncrypt1_0_Encrypt1 实现
  业务请求: ECDH 握手后 AES-GCM (AESCryptor)
            需先用 /mini-data/auth/login 拿到 session token

【游戏数据模型 (dump.cs)】
  ArchitectureIds: 1001-1038 (35 个兵种 + 资源)
  ArenaID: 1001-1007 (7 个竞技场)
  ABTestName: obtain_from_chest_on 等 5 个 UUID
  LoginAESKey = "2020we0616dobest"

用法:
  # 0. 默认就指向真活主机 (无需 --host)
  python api_client.py --probe-live
  python api_client.py --now-time
  python api_client.py --encrypt-test hello
  python api_client.py --list-archetypes
  python api_client.py --list-arenas
  python api_client.py --list-ab
  python api_client.py --list-endpoints
"""
import sys, json, argparse, base64, hmac, hashlib, struct
import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend


# ====== 现场验证过的游戏主机 (2026-08-24 R44 真机抓包) ======
LIVE_HOST = "https://cszdz-cn-wx.sereypath.com:18013"
CDN_HOST  = "https://oiumwaa-frx.sereypath.com"
XYX_HOST  = "https://xig.rayiantway.com:8509"

# ====== 8 个真活端点 (抓包+实测) ======
LIVE_ENDPOINTS = {
    "now_time":       ("GET",  "/mini-data/sys/nowTime",              False),
    "auth_login":     ("POST", "/mini-data/auth/login",                True),   # 加密
    "data_get":       ("POST", "/mini-data/data/private/get",          True),
    "data_update":    ("POST", "/mini-data/data/private/update",       True),
    "data_version":   ("POST", "/mini-data/data/private/version",      True),
    "mail_count":     ("POST", "/mini-mail/mail/query-count",          False),
    "mail_query_new": ("POST", "/mini-mail/mail/query-new",            False),
    "public_notice":  ("POST", "/mini-notice/public/notice",           False),
}

# ====== dump.cs 里的端点 (生产可能没部署, --probe-live 会验证) ======
BIZ_ENDPOINTS = {
    "lottery-upload-contact":  "/mini-lottery/lottery/uploadContactInfo",
    "pvp-season-reward":       "/mini-lottery/pvp/season/getMyRewardResult",
}
GM_ENDPOINTS = {
    "battle-gold":             "/gm/api/battle-gold",
    "battle-result":           "/gm/api/battle-result",
    "battle-artifact-charge":  "/gm/api/battle-artifact-charge",
    "battle-hex-card":         "/gm/api/battle-hex-card",
}
GM_COMMANDS = {"pvpBattleWin": "强制胜", "pvpBattleLose": "强制败"}


# ====== 游戏常量 ======
LOGIN_AES_KEY = b"2020we0616dobest"      # XyxLogin.LoginAESKey (dump.cs:801087)
XYX_AES_KEY   = b"we20210409dobest"      # xig 配置层密钥 (AUTOMATION_REPORT.md)
GM_TOKEN      = "local-frame-relay-gm-token"

AB_TEST = {
    "more_level_exp_on":     "333c59cc-1a44-4c03-b671-e43259d15051",
    "monthly_card_on":       "b7e88a32-0864-4434-9a12-fcb42a472a70",
    "obtain_from_chest_on":   "62ae5120-7a8f-4ac3-af16-85d32efa91d5",
    "linear_arena_on":       "855174bb-7e54-4dc1-8965-4b0cc97bfdcc",
    "morale_on":             "83b8961a-25c2-497d-a6be-0c4dc07f9220",
}

ARCHETYPE_IDS = {
    "JinKuang":        1001, "ChiFuZhanShi":   1002, "KuLouBing":     1003,
    "GongJianShou":    1004, "JianShi":        1005, "QiBing":        1006,
    "FaShi":           1007, "NuBing":         1008, "TouShiChe":     1009,
    "YouXia":          1010, "FeiLong":        1011, "JingRuiQiBing": 1012,
    "LongQiShi":       1013, "JianTa":         1014, "TouShiTa":      1015,
    "KuLouGongShou":   1016, "KuLouQiShi":     1017, "SiLingFaShi":   1018,
    "JuJiShou":        1019, "KuLouJuRen":     1020, "DeLuYi":        1021,
    "SiLingNvWang":    1022, "ChangMaoShou":   1023, "LangQiBing":    1024,
    "JianSheng":       1025, "BingShuangJuLong": 1026,
    "CunMin":          1029, "TieJiang":       1030, "GeBuLin":       1031,
    "QiShi":           1032, "ShiXiangGui":    1033, "SiWangQiShi":   1034,
    "QiuZhang":        1035, "EMoLingZhu":     1036, "XiongMaoRen":   1037,
    "NvWuShen":        1038,
}
ARENA_IDS = {f"Arena{1001+i}": 1001+i for i in range(7)}


# ====== 加密 (AES-128-CBC + PKCS7) ======
def aes_cbc_decrypt(key, ciphertext, iv=b'\x00' * 16):
    """AES-128-CBC 解密 + 去 PKCS7 padding"""
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    dec = cipher.decryptor()
    pt = dec.update(ciphertext) + dec.finalize()
    if pt and pt[-1] <= 16:
        pad = pt[-1]
        if all(b == pad for b in pt[-pad:]):
            return pt[:-pad]
    return pt

def aes_cbc_encrypt(key, plaintext, iv=b'\x00' * 16):
    """AES-128-CBC 加密 (登录/业务请求 body)"""
    if isinstance(plaintext, str):
        plaintext = plaintext.encode()
    padder = padding.PKCS7(128).padder()
    pt = padder.update(plaintext) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    return cipher.encryptor().update(pt) + cipher.finalize()

def encrypt_test(plaintext, key=LOGIN_AES_KEY):
    iv = b'\x00' * 16
    ct = aes_cbc_encrypt(key, plaintext, iv)
    pt2 = aes_cbc_decrypt(key, ct, iv)
    return {"key_hex": key.hex(), "iv_hex": iv.hex(), "plaintext": plaintext,
            "ciphertext_hex": ct.hex(), "decrypt_ok": plaintext.encode() == pt2}


# ====== HTTP 客户端 ======
def call(host, path, payload=None, headers_extra=None, method="POST", timeout=10):
    url = f"{host.rstrip('/')}{path}"
    h = {"Content-Type": "application/json", "User-Agent": "wxgame-probe/1.0"}
    if headers_extra: h.update(headers_extra)
    if method == "POST":
        r = requests.post(url, json=payload or {}, headers=h, timeout=timeout, verify=False)
    else:
        r = requests.get(url, params=payload or {}, headers=h, timeout=timeout, verify=False)
    return r.status_code, r.text, dict(r.headers)

def call_gm(host, endpoint, payload=None, method="POST", timeout=10):
    return call(host, GM_ENDPOINTS[endpoint], payload, {"X-GM-Token": GM_TOKEN}, method, timeout)

def call_biz(host, api_name, session_key, user_id, payload=None, method="POST", timeout=10):
    return call(host, BIZ_ENDPOINTS[api_name], payload,
                {"X-Session-Token": session_key, "X-User-Id": str(user_id)}, method, timeout)

def call_live(name, payload=None, headers_extra=None, host=LIVE_HOST, timeout=8):
    """打到真活主机的便捷函数"""
    if name not in LIVE_ENDPOINTS:
        return None, f"unknown endpoint: {name}", {}
    method, path, _enc = LIVE_ENDPOINTS[name]
    return call(host, path, payload, headers_extra, method, timeout)


# ====== 现场探测 ======
def probe_live(host=LIVE_HOST):
    """逐一探 8 个真活端点 + GM 端点, 输出 HTTP 状态 + 前 100 字节"""
    requests.packages.urllib3.disable_warnings()
    out = {"live_host": host, "live_endpoints": {}, "gm_endpoints": {}, "biz_endpoints": {}}
    for name, (m, p, enc) in LIVE_ENDPOINTS.items():
        try:
            code, text, hdrs = call(host, p, {}, {}, m)
            out["live_endpoints"][name] = {
                "method": m, "path": p, "status": code,
                "body_preview": text[:150], "content_type": hdrs.get("content-type", "?")
            }
        except Exception as e:
            out["live_endpoints"][name] = {"path": p, "error": repr(e)[:200]}
    for name, path in GM_ENDPOINTS.items():
        try:
            code, text, _ = call_gm(host, name)
            out["gm_endpoints"][name] = {"path": path, "status": code, "body_preview": text[:120]}
        except Exception as e:
            out["gm_endpoints"][name] = {"error": repr(e)[:200]}
    for name, path in BIZ_ENDPOINTS.items():
        try:
            code, text, _ = call(host, path, {}, {"X-Session-Token": "fake"}, "POST")
            out["biz_endpoints"][name] = {"path": path, "status": code, "body_preview": text[:120]}
        except Exception as e:
            out["biz_endpoints"][name] = {"error": repr(e)[:200]}
    return out


# ====== CLI ======
def main():
    requests.packages.urllib3.disable_warnings()
    ap = argparse.ArgumentParser(description="占城大师 API 客户端 v4 (live host verified)")
    ap.add_argument("--host", default=LIVE_HOST, help=f"游戏服务器 (默认: {LIVE_HOST})")
    ap.add_argument("--probe-live", action="store_true", help="探全部 8 个真活端点 + GM + 业务")
    ap.add_argument("--now-time", action="store_true", help="打 GET /mini-data/sys/nowTime")
    ap.add_argument("--live-endpoint", help=f"打指定真活端点: {list(LIVE_ENDPOINTS)}")
    ap.add_argument("--live-data", help="真活端点的 raw JSON payload")
    ap.add_argument("--encrypt-test", help="跑 AES-128-CBC 自检 (传明文)")
    ap.add_argument("--list-archetypes", action="store_true", help="列出所有兵种 ID")
    ap.add_argument("--list-arenas", action="store_true", help="列出所有竞技场")
    ap.add_argument("--list-ab", action="store_true", help="列出所有 AB 测试 UUID")
    ap.add_argument("--list-endpoints", action="store_true", help="列出全部端点")
    args = ap.parse_args()

    if args.encrypt_test:
        print(json.dumps(encrypt_test(args.encrypt_test), ensure_ascii=False, indent=2)); return
    if args.list_archetypes:
        print("兵种 ID (ArchitectureIds):"); [print(f"  {v:4d}  {k}") for k,v in ARCHETYPE_IDS.items()]; return
    if args.list_arenas:
        print("竞技场 ID (ArenaID):"); [print(f"  {v}  {k}") for k,v in ARENA_IDS.items()]; return
    if args.list_ab:
        print("AB 测试 UUID:"); [print(f"  {k:30s}  {v}") for k,v in AB_TEST.items()]; return
    if args.list_endpoints:
        print(f"LIVE_HOST = {LIVE_HOST}")
        print("\n真活端点 (已验证):")
        for n, (m, p, enc) in LIVE_ENDPOINTS.items():
            print(f"  [{m}] {p:50s}  加密={enc}")
        print("\ndump.cs 里的 GM 端点 (生产未部署):")
        for n, p in GM_ENDPOINTS.items():
            print(f"  {p}")
        print("\ndump.cs 里的业务端点:")
        for n, p in BIZ_ENDPOINTS.items():
            print(f"  {p}")
        return
    if args.probe_live:
        print(json.dumps(probe_live(args.host), ensure_ascii=False, indent=2)); return
    if args.now_time:
        code, text, _ = call_live("now_time", host=args.host)
        print(f"HTTP {code}: {text}"); return
    if args.live_endpoint:
        payload = json.loads(args.live_data) if args.live_data else {}
        code, text, _ = call_live(args.live_endpoint, payload, host=args.host)
        print(f"HTTP {code}: {text}"); return
    ap.print_help()

if __name__ == "__main__":
    main()
