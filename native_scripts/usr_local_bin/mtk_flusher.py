#!/usr/bin/env python3
import os, fcntl, struct

MTK_DISP_WAIT_VSYNC   = 0x400c4fd5
MTKFB_TRIG_OVERLAY_OUT = 0x00004f01

try:
    disp_fd = os.open('/dev/mtk_disp_mgr', os.O_RDWR)
    fb_fd   = os.open('/dev/graphics/fb0', os.O_RDWR)
    buf     = struct.pack('iii', 0, 0, 0)

    while True:
        fcntl.ioctl(disp_fd, MTK_DISP_WAIT_VSYNC, buf)
        fcntl.ioctl(fb_fd, MTKFB_TRIG_OVERLAY_OUT, 0)
except Exception:
    pass
