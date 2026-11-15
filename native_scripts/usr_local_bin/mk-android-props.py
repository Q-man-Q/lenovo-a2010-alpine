import struct

SIZE = 131072
buf = bytearray(SIZE)
data_off = 128
used = 0

def align4(n):
    return (n + 3) & ~3

def alloc(n):
    global used
    off = used
    used += align4(n)
    return off

# Root prop_bt at data[0]
def new_bt(name_bytes):
    sz = 20 + len(name_bytes) + 1
    off = alloc(sz)
    buf[data_off + off] = len(name_bytes)
    buf[data_off + off + 20 : data_off + off + 20 + len(name_bytes)] = name_bytes
    return off

root = new_bt(b'')

def get_u32(off):
    return struct.unpack_from('<I', buf, data_off + off)[0]

def set_u32(off, val):
    struct.pack_into('<I', buf, data_off + off, val)

def bt_name(off):
    nlen = buf[data_off + off]
    return bytes(buf[data_off + off + 20 : data_off + off + 20 + nlen])

def cmp_name(a, b):
    if len(a) < len(b): return -1
    if len(a) > len(b): return 1
    if a < b: return -1
    if a > b: return 1
    return 0

def add_prop(name, value):
    parts = name.encode().split(b'.')
    cur = root
    for seg in parts:
        child = get_u32(cur + 16) # children
        if child == 0:
            child = new_bt(seg)
            set_u32(cur + 16, child)
            cur = child
        else:
            node = child
            while True:
                c = cmp_name(seg, bt_name(node))
                if c == 0:
                    cur = node
                    break
                elif c < 0:
                    left = get_u32(node + 8)
                    if left == 0:
                        left = new_bt(seg)
                        set_u32(node + 8, left)
                        cur = left
                        break
                    node = left
                else:
                    right = get_u32(node + 12)
                    if right == 0:
                        right = new_bt(seg)
                        set_u32(node + 12, right)
                        cur = right
                        break
                    node = right
    nb = name.encode()
    vb = value.encode()
    poff = alloc(4 + 92 + len(nb) + 1)
    set_u32(poff, (len(vb) << 24))
    buf[data_off + poff + 4 : data_off + poff + 4 + len(vb)] = vb
    buf[data_off + poff + 96 : data_off + poff + 96 + len(nb)] = nb
    set_u32(cur + 4, poff)

props = {}
try:
    with open("/system/build.prop", "r", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if k and len(v.encode()) <= 91:
                props[k] = v
except Exception:
    pass

props.update({
    'persist.mtk.wcn.combo.chipid': '0x0335',
    'service.nvram_init': 'Ready',
    'gps.clock.type': '0',
    'dev.dsp': '/dev/stpgps',
    'dev.gps': '/dev/stpgps',
    'debug.debug_nmea': '1',
})
for k, v in props.items():
    add_prop(k, v)

struct.pack_into('<IIII', buf, 0, used, 1, 0x504f5250, 0xfc6ed0ab)
with open('/dev/__properties__', 'wb') as f:
    f.write(buf)
