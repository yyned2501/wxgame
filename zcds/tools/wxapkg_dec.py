"""
wxapkg_dec.py - 用 wux1an/wxapkg 的算法解密微信 v4 wxapkg
算法 (wechat/util.go:55):
  salt = "saltiest", iv = "the iv: 16 bytes"
  dk = PBKDF2(wxid, salt, 1000, 32, SHA1)
  AES-256-CBC 解密 data[6:6+1024]
  data[6+1024:] XOR wxid[-2]
然后按 wxapkg 格式解包文件表
"""
import sys, os, struct, hashlib, base64
from hashlib import pbkdf2_hmac
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

SALT = b'saltiest'
IV = b'the iv: 16 bytes'

def decrypt_wxapkg(wxid, data):
    dk = pbkdf2_hmac('sha1', wxid.encode(), SALT, 1000, 32)
    dec = Cipher(algorithms.AES(dk), modes.CBC(IV)).decryptor()
    head = dec.update(data[6:6+1024])
    xor_key = wxid[-2].encode()[0] if len(wxid) >= 2 else 0x66
    tail = bytes(b ^ xor_key for b in data[6+1024:])
    return head[:1023] + tail

def unpack_wxapkg(raw, outdir):
    # wxapkg header: magic(4)=0xbe 0x20 0x11 0x21? 实际: firstMark(1) info(4) version(1) ...
    # 标准: byte0=0xbe, 1-4=info, 5=version, 6-9=secondMark? 解出来的 head 前几字节:
    if raw[0] != 0xbe:
        print(f'  [!] magic != 0xbe: {raw[:8].hex()}')
        return False
    # 偏移: 0:be 1-4:info 5:version 6-9:index 10-13:count? 实际格式:
    # first_mark(1) info(4) version(1) index_info_length(4) index_data_length(4) last_mark(1)
    idx_info_len, = struct.unpack('>I', raw[6:10])
    idx_data_len, = struct.unpack('>I', raw[10:14])
    print(f'  index_info_len={idx_info_len} index_data_len={idx_data_len} last_mark=0x{raw[14]:02x}')
    pos = 15
    file_count = struct.unpack('>I', raw[pos:pos+4])[0]
    pos += 4
    print(f'  file_count={file_count}')
    os.makedirs(outdir, exist_ok=True)
    entries = []
    for _ in range(file_count):
        name_len = struct.unpack('>I', raw[pos:pos+4])[0]
        pos += 4
        name = raw[pos:pos+name_len].decode('utf-8', 'replace')
        pos += name_len
        offset, size = struct.unpack('>II', raw[pos:pos+8])
        pos += 8
        entries.append((name, offset, size))
    for name, offset, size in entries:
        fp = os.path.join(outdir, name.lstrip('/').replace('/', os.sep))
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, 'wb') as f:
            f.write(raw[offset:offset+size])
    print(f'  解出 {len(entries)} 个文件 -> {outdir}')
    return True

if __name__ == '__main__':
    wxid = sys.argv[1] if len(sys.argv) > 1 else 'wx9eed71970378b2ae'
    src = sys.argv[2]
    outdir = sys.argv[3] if len(sys.argv) > 3 else src + '_dec'
    data = open(src, 'rb').read()
    print(f'[*] {src} ({len(data)} bytes)')
    raw = decrypt_wxapkg(wxid, data)
    print(f'[*] 解密后 head: {raw[:16].hex()}')
    unpack_wxapkg(raw, outdir)
