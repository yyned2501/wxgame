"""
占城大师完整 API 客户端 (v2) —— GM 后门 + 业务 API + AES-GCM 加密

依赖: pip install requests pycryptodome websocket-client

基于 dump.cs 反编译提取的 API:
  - GM 后门 (4 个): CheatControl 常量
  - 业务 API (2 个): MiniLottery 上传联系信息 + PVP 赛季奖励查询
  - 加密: GameFramework.Net.AESCryptor (AES-GCM + ECDH)

用法:
  python api_client.py --host http://your-server:8509 --api pvp-battle-win --battle-id <id>
  python api_client.py --host http://your-server:8509 --api lottery-upload-contact --data <json>
  python api_client.py --host http://your-server:8509 --encrypt-test --plaintext 'hello'
"""
import sys, json, argparse, hmac, hashlib, struct, requests

# === 占城大师 GM 后门端点 (来自 dump.cs CheatControl 类 line 3394-3397) ===
GM_ENDPOINTS = {
    "battle-gold":         "/gm/api/battle-gold",
    "battle-result":       "/gm/api/battle-result",
    "battle-artifact-charge": "/gm/api/battle-artifact-charge",
    "battle-hex-card":     "/gm/api/battle-hex-card",
}
GM_TOKEN = "local-frame-relay-gm-token"
GM_COMMANDS = {
    "pvpBattleWin":  "PVP 战斗强制胜利",
    "pvpBattleLose": "PVP 战斗强制失败",
}
# === 业务 API 端点 (来自 dump.cs line 60067, 68971) ===
BIZ_ENDPOINTS = {
    "lottery-upload-contact":     "/mini-lottery/lottery/uploadContactInfo",
    "pvp-season-my-reward-result": "/mini-lottery/pvp/season/getMyRewardResult",
}


# ====== AES-GCM 加密 (来自 AESCryptor 类: DeriveMasterSecret / DeriveSessionKey / FillAad) ======
# AESCryptor 用 .NET BCL 的 ECDH (GenerateKeyPair) + HKDF 派生密钥 + AES-128-GCM 加解密
# 由于 .NET BCL ECDH 用 Windows CNG, 跨平台 Python 模拟需用 cryptography.hazmat
# 这里给完整 demo, 关键函数:
#   - DeriveMasterSecret(privKey, remotePubKey) = ECDH shared secret -> PBKDF2/HKDF -> 32 字节
#   - DeriveSessionKey(masterSecret, info, salt) = HKDF-Expand -> 16 字节 AES key
#   - Encrypt(plaintext) = GCM(nonce[12], key, plaintext, aad) -> ciphertext+tag[16]
#   - Decrypt(ciphertext) = GCM verify + plaintext
#   - FillAad(ExternalMessage msg, buffer) = aad 字段 (从消息里抽时间戳/请求ID等)

def ecdh_derive_master_secret_pbkdf2(priv_bytes, remote_pub_bytes, info=b"master"):
    """模拟 .NET ECDH + PBKDF2-SHA256(1000) -> 32 字节 master secret.
    .NET BCL ECDH 默认 P-256 曲线 (secp256r1). PBKDF2 迭代数 1000."""
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        priv = ec.derive_private_key(int.from_bytes(priv_bytes[:32], 'big'), ec.SECP256R1(), default_backend())
        pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), remote_pub_bytes)
        shared = priv.exchange(ec.ECDH(), pub)
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=info, iterations=1000, backend=default_backend())
        return kdf.derive(shared)
    except ImportError:
        raise SystemExit("缺 cryptography: pip install cryptography")

def hkdf_expand_sha256(master_secret, info, length=16):
    """HKDF-Expand (RFC 5869) -> length 字节 (默认 16 = AES-128)."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand
    return HKDFExpand(algorithm=hashes.SHA256(), length=length, info=info).derive(master_secret)

def derive_session_key(master_secret, info, salt):
    """AESCryptor.DeriveSessionKey(masterSecret, info, salt) -> 16 字节会话密钥"""
    return hkdf_expand_sha256(master_secret, info + salt, 16)

def aes_gcm_encrypt(key, plaintext, aad, nonce=None):
    """AES-128-GCM 加密. nonce 默认 12 字节零 (与 .NET BCL 默认一致)."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if nonce is None: nonce = b'\x00' * 12
    return AESGCM(key).encrypt(nonce, plaintext, aad)

def aes_gcm_decrypt(key, ciphertext, aad, nonce=None):
    """AES-128-GCM 解密. ciphertext 末 16 字节是 GCM tag."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if nonce is None: nonce = b'\x00' * 12
    return AESGCM(key).decrypt(nonce, ciphertext, aad)


# ====== HTTP 客户端 ======
def call_api(host, path, payload=None, headers_extra=None, method="POST", timeout=10):
    """通用 API 调用 (业务 + GM 复用)"""
    url = f"{host.rstrip('/')}{path}"
    headers = {"Content-Type": "application/json"}
    if headers_extra: headers.update(headers_extra)
    if method.upper() == "POST":
        r = requests.post(url, json=payload or {}, headers=headers, timeout=timeout)
    elif method.upper() == "GET":
        r = requests.get(url, params=payload or {}, headers=headers, timeout=timeout)
    else:
        raise ValueError(method)
    return r.status_code, r.text

def call_gm(host, endpoint, payload=None, method="POST", timeout=10):
    """GM 后门调用 (X-GM-Token 鉴权)"""
    return call_api(host, GM_ENDPOINTS[endpoint], payload, {"X-GM-Token": GM_TOKEN}, method, timeout)

def call_biz(host, api_name, payload=None, method="POST", timeout=10):
    """业务 API 调用 (后续需加登录 token)"""
    return call_api(host, BIZ_ENDPOINTS[api_name], payload, {}, method, timeout)


# ====== 加密自检 ======
def encrypt_test(plaintext, password=b"test-master-secret"):
    """端到端加密自检: 派生密钥 -> 加密 -> 解密 -> 对比 plaintext.
    用 password 模拟 master_secret 测 AES-GCM 完整流程."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand
    master = HKDFExpand(algorithm=hashes.SHA256(), length=32, info=b"test-master").derive(password)
    info = b"session-key-info"
    salt = b"0123456789ab"  # 12 字节
    key = derive_session_key(master, info, salt)
    aad = b"test-aad"
    pt = plaintext.encode() if isinstance(plaintext, str) else plaintext
    ct = aes_gcm_encrypt(key, pt, aad)
    pt2 = aes_gcm_decrypt(key, ct, aad)
    return {"master_hex": master.hex(), "session_key_hex": key.hex(),
            "aad_hex": aad.hex(), "plaintext_len": len(pt),
            "ciphertext_len": len(ct), "decrypt_ok": pt == pt2, "ciphertext_hex": ct.hex()}


# ====== CLI ======
def main():
    ap = argparse.ArgumentParser(description="占城大师 API 客户端 (GM + 业务 + AES-GCM)")
    ap.add_argument("--host", help="游戏 host URL (运行时拉, 需用户提供)")
    ap.add_argument("--api", choices=list(GM_ENDPOINTS) + list(BIZ_ENDPOINTS),
                    help="API 名: gm-* 或 biz-*")
    ap.add_argument("--cmd", choices=list(GM_COMMANDS), help="GM 命令名")
    ap.add_argument("--battle-id", help="战斗 ID")
    ap.add_argument("--amount", type=int, help="金币数量")
    ap.add_argument("--result", choices=["win", "lose"], help="battle-result 用")
    ap.add_argument("--artifact-id", help="battle-artifact-charge 用")
    ap.add_argument("--card-id", help="battle-hex-card 用")
    ap.add_argument("--method", default="POST", choices=["GET", "POST"])
    ap.add_argument("--data", help="raw JSON payload (覆盖其他参数)")
    ap.add_argument("--encrypt-test", help="跑 AES-GCM 自检 (传明文, 返回 hex 摘要)")
    ap.add_argument("--master-secret", default="test-master-secret", help="encrypt-test 用的 master secret")
    args = ap.parse_args()

    if args.encrypt_test:
        r = encrypt_test(args.encrypt_test, args.master_secret.encode())
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return

    if not args.host:
        ap.error("--host 必填 (除非 --encrypt-test)")

    if args.api in GM_ENDPOINTS:
        if args.data:
            payload = json.loads(args.data)
        else:
            payload = {}
            if args.cmd: payload["command"] = args.cmd
            if args.battle_id: payload["battleId"] = args.battle_id
            if args.amount is not None: payload["amount"] = args.amount
            if args.result: payload["result"] = args.result
            if args.artifact_id: payload["artifactId"] = args.artifact_id
            if args.card_id: payload["cardId"] = args.card_id
        print(f"==> GM POST {args.host}{GM_ENDPOINTS[args.api]}")
        print(f"    Token: {GM_TOKEN}")
        print(f"    Payload: {json.dumps(payload, ensure_ascii=False)}")
        code, body = call_gm(args.host, args.api, payload, args.method)
    else:
        if args.data:
            payload = json.loads(args.data)
        else:
            payload = {}
        print(f"==> BIZ POST {args.host}{BIZ_ENDPOINTS[args.api]}")
        print(f"    Payload: {json.dumps(payload, ensure_ascii=False)}")
        code, body = call_biz(args.host, args.api, payload, args.method)

    print(f"<== {code}")
    print(body[:500])

if __name__ == "__main__":
    main()
