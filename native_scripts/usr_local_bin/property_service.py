#!/usr/bin/env python3
"""Android property_service for Alpine (Lenovo A2010, MT6735M).

Listens on /dev/socket/property_service and actually updates
/dev/__properties__ so MTK/Android daemons (ccci_mdinit, mtk_agpsd, ...)
can property_set() at runtime.

Protocol (Android 5.1 libcutils property_set):
    client sends struct prop_msg = { unsigned cmd; char name[32]; char value[92]; }
    i.e. 128 bytes: cmd(4) name(32) value(92). cmd == 1 == PROP_MSG_SETPROP.
"""

import os
import struct
import socket
import sys
import threading

SIZE = 131072
DATA_OFF = 128
REGION = '/dev/__properties__'
SOCKET_PATH = '/dev/socket/property_service'
LOG = '/tmp/property_service.log'


def log(msg):
    try:
        with open(LOG, 'a') as f:
            f.write(msg + '\n')
    except Exception:
        pass


# --------------------------------------------------------------------------
# prop_area tree building (ported from mk-android-props.py)
# --------------------------------------------------------------------------

def build_region(props):
    buf = bytearray(SIZE)
    used = [0]

    def align4(n):
        return (n + 3) & ~3

    def alloc(n):
        off = used[0]
        used[0] += align4(n)
        return off

    def new_bt(name_bytes):
        sz = 20 + len(name_bytes) + 1
        off = alloc(sz)
        buf[DATA_OFF + off] = len(name_bytes)
        buf[DATA_OFF + off + 20:DATA_OFF + off + 20 + len(name_bytes)] = name_bytes
        return off

    root = new_bt(b'')

    def get_u32(off):
        return struct.unpack_from('<I', buf, DATA_OFF + off)[0]

    def set_u32(off, val):
        struct.pack_into('<I', buf, DATA_OFF + off, val)

    def bt_name(off):
        nlen = buf[DATA_OFF + off]
        return bytes(buf[DATA_OFF + off + 20:DATA_OFF + off + 20 + nlen])

    def cmp_name(a, b):
        if len(a) < len(b):
            return -1
        if len(a) > len(b):
            return 1
        return -1 if a < b else (1 if a > b else 0)

    def add_prop(name, value):
        parts = name.encode().split(b'.')
        cur = root
        for seg in parts:
            child = get_u32(cur + 16)
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
        buf[DATA_OFF + poff + 4:DATA_OFF + poff + 4 + len(vb)] = vb
        buf[DATA_OFF + poff + 96:DATA_OFF + poff + 96 + len(nb)] = nb
        set_u32(cur + 4, poff)

    for k, v in props.items():
        add_prop(k, v)

    # header: count, serial, magic(0x504f5250 "PROP"), version(0xfc6ed0ab)
    struct.pack_into('<IIII', buf, 0, used[0], 1, 0x504f5250, 0xfc6ed0ab)
    return bytes(buf)


# --------------------------------------------------------------------------
# parse existing prop_area back into {name: value}
# --------------------------------------------------------------------------

def parse_region(raw):
    props = {}
    if len(raw) < DATA_OFF + 4:
        return props

    def get_u32(off):
        return struct.unpack_from('<I', raw, DATA_OFF + off)[0]

    def walk(node_off, prefix):
        if node_off == 0:
            return
        nlen = raw[DATA_OFF + node_off]
        seg = raw[DATA_OFF + node_off + 20:DATA_OFF + node_off + 20 + nlen].decode('latin1')
        full = prefix + seg

        prop_off = get_u32(node_off + 4)
        if prop_off:
            serial = get_u32(prop_off)
            vlen = (serial >> 24) & 0xff
            value = raw[DATA_OFF + prop_off + 4:DATA_OFF + prop_off + 4 + vlen].decode('latin1')
            name = raw[DATA_OFF + prop_off + 96:DATA_OFF + prop_off + 96 + 128]
            name = name.split(b'\x00', 1)[0].decode('latin1')
            props[name or full] = value

        walk(get_u32(node_off + 8), prefix)      # left sibling
        walk(get_u32(node_off + 12), prefix)     # right sibling
        walk(get_u32(node_off + 16), full + '.')  # children

    # root node at offset 0; start from its children
    walk(get_u32(0 + 16), '')
    return props


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    props = {}
    try:
        with open(REGION, 'rb') as f:
            props = parse_region(f.read())
        log('parsed %d existing props' % len(props))
    except Exception as e:
        log('parse existing failed: %s' % e)

    lock = threading.Lock()

    def write_region():
        raw = build_region(props)
        with open(REGION, 'wb') as f:
            f.write(raw)

    write_region()

    os.makedirs('/dev/socket', exist_ok=True)
    try:
        os.unlink(SOCKET_PATH)
    except FileNotFoundError:
        pass

    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o666)
    srv.listen(32)
    log('listening on %s' % SOCKET_PATH)

    def handle(conn):
        try:
            data = b''
            while len(data) < 128:
                chunk = conn.recv(128 - len(data))
                if not chunk:
                    break
                data += chunk
            if len(data) >= 4:
                cmd = struct.unpack_from('<I', data, 0)[0]
                if cmd == 1:  # PROP_MSG_SETPROP
                    name = data[4:36].split(b'\x00', 1)[0].decode('latin1')
                    value = data[36:128].split(b'\x00', 1)[0].decode('latin1')
                    if name:
                        with lock:
                            props[name] = value
                            write_region()
                        log('SET %s=%s' % (name, value))
        except Exception as e:
            log('ERR %s' % e)
        finally:
            conn.close()

    while True:
        conn, _ = srv.accept()
        threading.Thread(target=handle, args=(conn,), daemon=True).start()


if __name__ == '__main__':
    main()
