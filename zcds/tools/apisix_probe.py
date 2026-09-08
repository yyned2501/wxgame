"""
apisix_probe.py - 占城大师 mini-data ApiSix 加密层探测
发现: HTTP 加密层 = ApiSix (客户端生成 randomAesKey -> RSA 公钥加密 -> body AES 加密)
关键: 因为 randomAesKey 是【我】生成的, 服务器用同一 key 加密响应 -> 我能解自己的响应!
      不需要破别人的会话。

RSA 公钥 (从 PID 20828 内存 UTF-16 提取, tools/zcds_rsa_pub.pem):
  1024-bit PKCS#1, 加密输出 128 字节
密文结构假设 (b00401_req 505B = 128 + 377):
  encrypt_field = base64( RSA(randomAesKey)[128B] || AES(randomAesKey, plaintext)[377B] )
  377 非 16 倍数 -> body 用流式模式 (CTR/CFB/OFB) 或 GCM

待确定 (需逆 MakeQueryPath / CanPostApiSix 函数体):
  - randomAesKey 长度与字符集 (GenerateSecureRandomKey)
  - AES 模式 + IV 来源
  - RSA 填充 (PKCS1v15 / OAEP)
  - 响应格式 (是否也带 128B 前缀)
"""
import os, base64, json, ssl, urllib.request, secrets, string
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric import padding, utils
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

HERE = os.path.dirname(os.path.abspath(__file__))
RSA_PEM = open(os.path.join(HERE, 'zcds_rsa_pub.pem'), 'rb').read()
PUB = load_pem_public_key(RSA_PEM)
HOST = 'cszdz-cn-wx.sereypath.com:18013'
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE


def gen_aes_key(n=16):
    alpha = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alpha) for _ in range(n)).encode()


def rsa_encrypt(key_bytes, mode='pkcs1'):
    if mode == 'pkcs1':
        return PUB.encrypt(key_bytes, padding.PKCS1v15())
    return PUB.encrypt(key_bytes, padding.OAEP(
        mgf=utils.MGF1(algorithm=algorithms.SHA1()),
        algorithm=algorithms.SHA1(), label=None))


def aes_stream(key, iv, data, mode='ctr'):
    m = {'ctr': modes.CTR, 'cfb': modes.CFB, 'ofb': modes.OFB}[mode]
    c = Cipher(algorithms.AES(key), m(iv)).encryptor()
    return c.update(data) + c.finalize()


def build_encrypt_field(key, plaintext, mode='ctr', iv_mode='zeros'):
    ct_body = aes_stream(key, b'\x00'*16 if iv_mode == 'zeros' else key[:16],
                         plaintext, mode)
    return base64.b64encode(rsa_encrypt(key) + ct_body).decode()


def probe_login(plaintext):
    key = gen_aes_key(16)
    body = json.dumps({'encrypt': build_encrypt_field(key, plaintext)}).encode()
    req = urllib.request.Request(f'https://{HOST}/mini-data/auth/login', data=body,
        method='POST', headers={'content-type': 'application/json;charset=UTF-8',
        'x-encrypted': 'true', 'x-encrypted-param': '1', 'User-Agent': 'wxgame-probe/1.0'})
    r = urllib.request.urlopen(req, timeout=8, context=CTX)
    raw = r.read()
    print(f'  HTTP {r.status} resp={raw[:80]}')
    return raw


if __name__ == '__main__':
    # 探测: 各种模式组合, 看响应是否比垃圾解密更长/不同 (长度 oracle)
    sample = json.dumps({'code': 'test', 'openId': 'oNxUz3d9ektPyga7dh8Pfx0uQ7S0',
                         'uid': 754125365240168449}).encode()
    for mode in ['ctr', 'cfb', 'ofb']:
        for ivm in ['zeros', 'key']:
            try:
                print(f'[probe] aes={mode} iv={ivm}')
                probe_login(sample)
            except Exception as e:
                print(f'  ERR {repr(e)[:120]}')
