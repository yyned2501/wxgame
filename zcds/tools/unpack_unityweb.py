"""unpack_unityweb.py - 解 UnityWebData1.0 归档 (小程序 data.unityweb.bin)"""
import struct, os, sys

src = sys.argv[1]
outdir = sys.argv[2]
extract_all = len(sys.argv) > 3 and sys.argv[3] == 'all'

d = open(src, 'rb').read()
assert d[:16] == b'UnityWebData1.0\x00', d[:16]
pos = 16
total, = struct.unpack_from('<I', d, pos); pos += 4
hdr_len, = struct.unpack_from('<I', d, pos); pos += 4
end = pos + hdr_len
print(f'total={total} hdr_len={hdr_len}')
os.makedirs(outdir, exist_ok=True)
n = 0
names = []
while pos < end:
    plen, = struct.unpack_from('<I', d, pos); pos += 4
    path = d[pos:pos+plen].decode('utf-8', 'replace'); pos += plen
    off, size = struct.unpack_from('<II', d, pos); pos += 8
    names.append((path, off, size))
    n += 1
print(f'{n} files in archive')
for path, off, size in names:
    if extract_all or 'metadata' in path.lower() or 'il2cpp' in path.lower() or path.endswith('.dat'):
        out = os.path.join(outdir, os.path.basename(path))
        open(out, 'wb').write(d[off:off+size])
        print(f'  EXTRACT {path} ({size}B) -> {out}')
# 列前 40 个文件
for path, off, size in names[:40]:
    print(f'    {path:70s} {size}')
