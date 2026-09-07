"""
wasm_map.py - 正确解析 wasm element section, 建 RVA(il2cpp method address) -> wasm func index 映射
spec: flags bit0=passive bit1=has-tableidx bit2=exprs
  0: off-expr, vec<funcidx>
  1: elemkind(1B), vec<funcidx>
  2: tableidx(leb), off-expr, elemkind(1B), vec<funcidx>
  3: elemkind(1B), vec<funcidx>
  4: off-expr, vec<expr>
  5: reftype(1B), vec<expr>
  6: tableidx(leb), off-expr, reftype(1B), vec<expr>
  7: reftype(1B), vec<expr>
expr: 指令流到 0x0b; 立即数: 0x41 leb / 0x42 sleb / 0x23 leb / 0xd2 leb / 0xd0 无
"""
import json, sys

WASM = r'C:\projects\wxgame\zcds\game_src\_wasmcode_\wasmcode\3513b885f1bda583.webgl.wasm.code.unityweb.wasm'

def leb(d, i):
    r = 0; s = 0
    while True:
        b = d[i]; i += 1
        r |= (b & 0x7f) << s
        if not (b & 0x80): return r, i
        s += 7

def sections(d):
    i = 8; secs = {}
    while i < len(d):
        sid = d[i]; i += 1
        sz, i = leb(d, i)
        secs.setdefault(sid, []).append((i, sz))
        i += sz
    return secs

def count_func_imports(d, secs):
    off, sz = secs[2][0]
    j = off
    n, j = leb(d, j)
    fi = 0
    for _ in range(n):
        ml, j = leb(d, j); j += ml
        nl, j = leb(d, j); j += nl
        kind = d[j]; j += 1
        if kind == 0:
            _, j = leb(d, j); fi += 1
        elif kind == 1: j += 2
        elif kind == 2: j += 2
        elif kind == 3: j += 1
    return fi

def read_expr(d, j):
    """返回 (value_or_None, new_j); 只认 ref.func 的值"""
    val = None
    while True:
        b = d[j]; j += 1
        if b == 0x0b:
            return val, j
        if b in (0x41, 0x23, 0xd2):
            v, j = leb(d, j)
            if b == 0xd2: val = v
        elif b == 0x42:
            v, j = leb(d, j)
        elif b == 0xd0:
            pass
        else:
            # 未知指令: 保守报错
            raise ValueError(f'unknown expr opcode 0x{b:02x} at {j-1}')

def build_table(d, secs):
    table = {}
    for off, sz in secs.get(9, []):
        j = off
        n_seg, j = leb(d, j)
        for s in range(n_seg):
            flags, j = leb(d, j)
            has_table = bool(flags & 2)
            passive = bool(flags & 1)
            use_expr = bool(flags & 4)
            if has_table:
                _, j = leb(d, j)
            base = 0
            if not passive:
                base_expr, j = read_expr(d, j)
                base = base_expr or 0
            if not use_expr:
                if flags in (1, 2, 3):
                    _ = d[j]; j += 1  # elemkind
            else:
                if flags in (5, 6, 7):
                    _ = d[j]; j += 1  # reftype
            n_fn, j = leb(d, j)
            for k in range(n_fn):
                if not use_expr:
                    fi, j = leb(d, j)
                    table[base + k] = fi
                else:
                    val, j = read_expr(d, j)
                    if val is not None:
                        table[base + k] = val
    return table

if __name__ == '__main__':
    d = open(WASM, 'rb').read()
    secs = sections(d)
    fi_imports = count_func_imports(d, secs)
    table = build_table(d, secs)
    import collections
    cnt = collections.Counter(table.values())
    print(f'func_imports={fi_imports} table_entries={len(table)}')
    print('top5 dup:', cnt.most_common(5))
    RVAS = {
        'URLEncryptString': 0x1f9ac,
        'EncryptString': 0x1f9af,
        'SPEncrypt1_0_Encrypt1': 0x1f9b0,
        'Utf8StrToByte': 0x1f9b1,
        'EncodeBase64': 0x1f9b2,
        'cctor': 0x1f9b3,
    }
    out = {'func_imports': fi_imports, 'map': {}}
    for name, rva in RVAS.items():
        f = table.get(rva)
        defined = f - fi_imports if f is not None else None
        out['map'][name] = {'func': f, 'defined': defined}
        print(f'  {name:24s} rva=0x{rva:x} func={f} defined#{defined}')
    # 局部连续性检查
    print('  continuity 129450..129465:', [table.get(r) for r in range(129450, 129466)])
    json.dump({'func_imports': fi_imports,
               'table': {str(k): v for k, v in table.items()}},
              open(r'C:\projects\wxgame\zcds\tools\wasm_table_map.json', 'w'))
    print('saved wasm_table_map.json')
