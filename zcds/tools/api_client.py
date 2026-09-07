"""
占城大师 API 客户端 v3 —— 完整 login + 业务 API + GM 后门
基于 dump.cs 反编译 + AES-GCM 完整实现
依赖: pip install requests cryptography

完整流程:
  1. AES-128-CBC + LoginAESKey=2020we0616dobest 解密 obtain 响应
  2. LoginSDK -> UnionLoginServer(httpString) -> OpenidJson
  3. OpenidJson.sessionKey 调业务 API (WebRequest.Create)
  4. GM 后门 4 端点鉴权用 X-GM-Token

游戏数据模型 (从 dump.cs 反编译):
  ArchitectureIds: 1001=金狂 1002=触发战士 1003=骷髅兵 1004=弓箭手 1005=剑士 1006=骑兵
                1007=法师 1008=弩兵 1009=投石车 1010=游侠 1011=飞龙 1012=精锐骑兵
                1013=龙骑士 1014=剑塔 1015=投石塔 1016=骷髅弓手 1017=骷髅骑士
                1018=司令法师 1019=狙击手 1020=骷髅巨人 1021=德鲁伊 1022=司令女皇
                1023=长矛手 1024=狼骑兵 1025=剑圣 1026=冰霜巨灵 1029=村民
                1030=铁矿 1031=哥布林 1032=骑士 1033=石像鬼 1034=死灵骑士
                1035=酋长 1036=恶魔领主 1037=熊猫人 1038=女武神
  ArenaID: 1001-1007 七个竞技场
  ABTestName: obtain_from_chest_on 等 A/B 测试 UUID
  GM 命令: pvpBattleWin (强制胜), pvpBattleLose (强制败)

用法:
  # 1. 拿到 host 后 (开发者工具 vConsole 看 app-config.json 里的 serverUrl):
  python api_client.py --host http://<game-server:8509> --login <code>
  # 2. GM 后门调:
  python api_client.py --host http://<host> --gm pvp-battle-win --battle-id <id> --player-id <id>
  # 3. 业务 API 查 PVP 赛季奖励:
  python api_client.py --host http://<host> --api pvp-season-reward --session-key <key> --user-id <id>
  # 4. 加密自检 (无 host):
  python api_client.py --encrypt-test hello
  # 5. 列出所有兵种 ID:
  python api_client.py --list-archetypes
  # 6. 列出所有竞技场:
  python api_client.py --list-arenas
"""
import sys, json, argparse, base64, hmac, hashlib, struct, requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend

# ====== 游戏数据模型 (dump.cs 反编译) ======
LOGIN_AES_KEY = b"2020we0616dobest"      # XyxLogin.LoginAESKey
GM_TOKEN = "local-frame-relay-gm-token"  # XyxLogin.CheatControl

# 占城大师 AB 测试开关 UUID
AB_TEST = {
    "more_level_exp_on":     "333c59cc-1a44-4c03-b671-e43259d15051",
    "monthly_card_on":       "b7e88a32-0864-4434-9a12-fcb42a472a70",
    "obtain_from_chest_on":   "62ae5120-7a8f-4ac3-af16-85d32efa91d5",
    "linear_arena_on":       "855174bb-7e54-4dc1-8965-4b0cc97bfdcc",
    "morale_on":             "83b8961a-25c2-497d-a6be-0c4dc07f9220",
}

# 兵种 ID (ArchitectureIds 1-38)
ARCHETYPE_IDS = {
    "JinKuang":        1001,   # 金狂
    "ChiFuZhanShi":    1002,   # 触发战士
    "KuLouBing":      1003,   # 骷髅兵
    "GongJianShou":    1004,   # 弓箭手
    "JianShi":         1005,   # 剑士
    "QiBing":          1006,   # 骑兵
    "FaShi":           1007,   # 法师
    "NuBing":          1008,   # 弩兵
    "TouShiChe":      1009,   # 投石车
    "YouXia":          1010,   # 游侠
    "FeiLong":        1011,   # 飞龙
    "JingRuiQiBing":  1012,   # 精锐骑兵
    "LongQiShi":      1013,   # 龙骑士
    "JianTa":         1014,   # 剑塔
    "TouShiTa":       1015,   # 投石塔
    "KuLouGongShow":  1016,   # 骷髅弓手
    "KuLouQiShi":     1017,   # 骷髅骑士
    "SiLingFaShi":   1018,   # 司令法师
    "JuJiShou":       1019,   # 狙击手
    "KuLouJuRen":     1020,   # 骷髅巨人
    "DeLuYi":         1021,   # 德鲁伊
    "SiLingNvWang":   1022,   # 司令女皇
    "ChangMaoShou":   1023,   # 长矛手
    "LangQiBing":     1024,   # 狼骑兵
    "JianSheng":      1025,   # 剑圣
    "BingShuangJuLong": 1026, # 冰霜巨灵
    "CunMin":         1029,   # 村民
    "TieJiang":       1030,   # 铁矿
    "GeBuLin":        1031,   # 哥布林
    "QiShi":          1032,   # 骑士
    "ShiXiangGui":    1033,   # 石像鬼
    "SiWangQiShi":    1034,   # 死灵骑士
    "QiuZhang":       1035,   # 酋长
    "EMoLingZhu":    1036,   # 恶魔领主
    "XiongMaoRen":    1037,   # 熊猫人
    "NvWuShen":       1038,   # 女武神
}

# 竞技场 ID
ARENA_IDS = {f"Arena{1001+i}": 1001+i for i in range(7)}

# 业务端点 (来自 dump.cs)
BIZ_ENDPOINTS = {
    "lottery-upload-contact":     "/mini-lottery/lottery/uploadContactInfo",
    "pvp-season-reward":           "/mini-lottery/pvp/season/getMyRewardResult",
}
GM_ENDPOINTS = {
    "battle-gold":         "/gm/api/battle-gold",
    "battle-result":       "/gm/api/battle-result",
    "battle-artifact-charge": "/gm/api/battle-artifact-charge",
    "battle-hex-card":     "/gm/api/battle-hex-card",
}
GM_COMMANDS = {"pvpBattleWin": "强制胜", "pvpBattleLose": "强制败"}


# ====== 加密: AES-128-CBC + PKCS7 (用于解密 obtain 响应) ======
def aes_cbc_decrypt(key, ciphertext, iv=b'\x00' * 16):
    """AES-128-CBC 解密 + 去 PKCS7 padding. 用于 obtain 接口响应"""
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    dec = cipher.decryptor()
    pt = dec.update(ciphertext) + dec.finalize()
    # 去 PKCS7 padding
    if pt and pt[-1] <= 16:
        pad = pt[-1]
        if all(b == pad for b in pt[-pad:]):
            return pt[:-pad]
    return pt

def aes_cbc_encrypt(key, plaintext, iv=b'\x00' * 16):
    """AES-128-CBC 加密 (登录请求用)"""
    padder = padding.PKCS7(128).padder()
    pt = padder.update(plaintext) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    enc = cipher.encryptor()
    return enc.update(pt) + enc.finalize()

def encrypt_test(plaintext, key=LOGIN_AES_KEY):
    """端到端加密自检"""
    iv = b'\x00' * 16
    ct = aes_cbc_encrypt(key, plaintext.encode() if isinstance(plaintext, str) else plaintext, iv)
    pt2 = aes_cbc_decrypt(key, ct, iv)
    return {"key_hex": key.hex(), "iv_hex": iv.hex(), "plaintext": plaintext,
            "ciphertext_hex": ct.hex(), "decrypt_ok": plaintext.encode() == pt2}


# ====== HTTP 客户端 ======
def call(host, path, payload=None, headers_extra=None, method="POST", timeout=10):
    url = f"{host.rstrip('/')}{path}"
    h = {"Content-Type": "application/json"}
    if headers_extra: h.update(headers_extra)
    if method == "POST":
        r = requests.post(url, json=payload or {}, headers=h, timeout=timeout)
    else:
        r = requests.get(url, params=payload or {}, headers=h, timeout=timeout)
    return r.status_code, r.text

def call_gm(host, endpoint, payload=None, method="POST", timeout=10):
    return call(host, GM_ENDPOINTS[endpoint], payload, {"X-GM-Token": GM_TOKEN}, method, timeout)

def call_biz(host, api_name, session_key, user_id, payload=None, method="POST", timeout=10):
    """业务 API 需 session_key (OpenidJson.sessionKey) 鉴权"""
    return call(host, BIZ_ENDPOINTS[api_name], payload,
                {"X-Session-Token": session_key, "X-User-Id": user_id}, method, timeout)

def login_step(host, code):
    """模拟 XYXLogin.LoginToMiniServer / UnionLoginServer 流程.
    1. POST code 到 /xyx/obtain (AES-128-CBC 加密 body)
    2. 响应 base64 (AES 加密) -> 解密拿 OpenidJson (含 sessionKey)
    实际端点路径由 host/config 决定, 此处用 /xyx/obtain 占位"""
    iv = b'\x00' * 16
    body = json.dumps({"code": code, "deviceId": "test", "ts": 0}).encode()
    ct_b64 = base64.b64encode(aes_cbc_encrypt(LOGIN_AES_KEY, body, iv)).decode()
    status, text = call(host, "/xyx/obtain", {"d": ct_b64}, {}, "POST")
    if status != 200:
        return None, f"login HTTP {status}: {text[:200]}"
    try:
        resp = json.loads(text)
        enc = resp.get("encrypt") or resp.get("d")
        if enc:
            raw = aes_cbc_decrypt(LOGIN_AES_KEY, base64.b64decode(enc), iv)
            data = json.loads(raw)
        else:
            data = resp
        return data, None
    except Exception as e:
        return None, f"login parse: {e}"


# ====== CLI ======
def main():
    ap = argparse.ArgumentParser(description="占城大师 API 客户端 v3 (完整 login + GM + 业务)")
    ap.add_argument("--host", help="游戏服务器 URL (运行时拉, dump.cs 无 hardcode)")
    ap.add_argument("--login", help="微信 code (调 /xyx/obtain 拿 OpenidJson)")
    ap.add_argument("--gm", choices=list(GM_ENDPOINTS), help="GM 后门端点")
    ap.add_argument("--api", choices=list(BIZ_ENDPOINTS), help="业务 API 端点")
    ap.add_argument("--cmd", choices=list(GM_COMMANDS), help="GM 命令 (pvpBattleWin / pvpBattleLose)")
    ap.add_argument("--session-key", help="OpenidJson.sessionKey (业务 API 鉴权)")
    ap.add_argument("--user-id", help="OpenidJson.userId (业务 API)")
    ap.add_argument("--battle-id", help="战斗 ID")
    ap.add_argument("--player-id", type=int, help="玩家 ID")
    ap.add_argument("--amount", type=int, help="金币数量")
    ap.add_argument("--result", choices=["win", "lose"])
    ap.add_argument("--artifact-id", help="神器 ID")
    ap.add_argument("--card-id", help="卡牌 ID")
    ap.add_argument("--method", default="POST", choices=["GET", "POST"])
    ap.add_argument("--data", help="raw JSON payload")
    ap.add_argument("--encrypt-test", help="跑 AES-128-CBC 自检 (传明文)")
    ap.add_argument("--list-archetypes", action="store_true", help="列出所有兵种 ID")
    ap.add_argument("--list-arenas", action="store_true", help="列出所有竞技场")
    args = ap.parse_args()

    if args.encrypt_test:
        r = encrypt_test(args.encrypt_test)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    if args.list_archetypes:
        print("兵种 ID (ArchitectureIds 1001-1038):")
        for k, v in ARCHETYPE_IDS.items():
            print(f"  {v:4d}  {k}")
        return
    if args.list_arenas:
        print("竞技场 ID (ArenaID):")
        for k, v in ARENA_IDS.items():
            print(f"  {v}  {k}")
        return

    if not args.host:
        ap.error("需 --host (除非 --encrypt-test / --list-archetypes / --list-arenas)")

    # 登录
    if args.login:
        print(f"==> login code={args.login[:10]}... 到 {args.host}/xyx/obtain")
        data, err = login_step(args.host, args.login)
        if err: print(f"  失败: {err}"); return
        print(f"  成功! userId={data.get('userId')} openId={data.get('openId')} sessionKey={data.get('sessionKey')[:20] if data.get('sessionKey') else None}...")
        return

    payload = json.loads(args.data) if args.data else {}

    # GM 后门
    if args.gm:
        if not args.cmd: payload["command"] = args.cmd if args.cmd else "pvpBattleWin"
        else: payload["command"] = args.cmd
        if args.battle_id: payload["battleId"] = args.battle_id
        if args.player_id: payload["playerId"] = args.player_id
        if args.amount is not None: payload["amount"] = args.amount
        if args.result: payload["result"] = args.result
        if args.artifact_id: payload["artifactId"] = args.artifact_id
        if args.card_id: payload["cardId"] = args.card_id
        print(f"==> GM {args.host}{GM_ENDPOINTS[args.gm]}")
        print(f"    Token: {GM_TOKEN}  Payload: {json.dumps(payload, ensure_ascii=False)}")
        code, body = call_gm(args.host, args.gm, payload, args.method)
    else:
        # 业务 API
        if not args.api: ap.error("需 --api 或 --gm")
        if not args.session_key or not args.user_id:
            ap.error("业务 API 需 --session-key (OpenidJson.sessionKey) 和 --user-id (OpenidJson.userId)")
        if args.battle_id: payload["battleId"] = args.battle_id
        if args.player_id: payload["playerId"] = args.player_id
        print(f"==> BIZ {args.host}{BIZ_ENDPOINTS[args.api]}")
        print(f"    User: {args.user_id}  Payload: {json.dumps(payload, ensure_ascii=False)}")
        code, body = call_biz(args.host, args.api, args.session_key, args.user_id, payload, args.method)

    print(f"<== {code}\n{body[:500]}")

if __name__ == "__main__":
    main()
