#!/usr/bin/env python3
import os, fcntl, struct

MTKFB_SET_OVERLAY_LAYER       = 0x40744f00
MTKFB_TRIG_OVERLAY_OUT        = 0x00004f01
MTKFB_SET_VIDEO_LAYERS        = 0x40744f02
MTKFB_CONFIG_IMMEDIATE_UPDATE = 0x40044f04

try:
    fb_fd = os.open('/dev/graphics/fb0', os.O_RDWR)

    # 1. Enable immediate auto-update mode in MTK display controller
    buf_imm = struct.pack('I', 1)
    try:
        fcntl.ioctl(fb_fd, MTKFB_CONFIG_IMMEDIATE_UPDATE, buf_imm)
        print('MTKFB_CONFIG_IMMEDIATE_UPDATE enabled!', flush=True)
    except Exception as e:
        print('MTKFB_CONFIG_IMMEDIATE_UPDATE err:', e, flush=True)

    # 2. Disable all hardware overlay layers 1, 2, 3
    for layer_id in [1, 2, 3]:
        buf = bytearray(116)
        struct.pack_into('II', buf, 0, layer_id, 0) # enable = 0
        for cmd in (MTKFB_SET_OVERLAY_LAYER, MTKFB_SET_VIDEO_LAYERS):
            try:
                fcntl.ioctl(fb_fd, cmd, buf)
            except Exception:
                pass

    try:
        fcntl.ioctl(fb_fd, MTKFB_TRIG_OVERLAY_OUT, 0)
    except Exception:
        pass

    os.close(fb_fd)
    print('MediaTek overlay layers cleared and auto-update active!', flush=True)
except Exception as e:
    print('Overlay reset error:', e, flush=True)
