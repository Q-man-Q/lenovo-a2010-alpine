#!/bin/sh
# MediaTek MT6735m 4G LTE Modem bring-up & AT control for Alpine Linux (Lenovo A2010-a)
# Usage: modem-ctl.sh {start|stop|status|rf-on|rf-off|scan|at <CMD>}

set -e
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export LD_LIBRARY_PATH="/system/lib:/vendor/lib"

AT_PORT="/dev/radio/pttycmd1"

prepare_env() {
    # 1. Mount NVRAM and protected modem calibration partitions (rw)
    mkdir -p /nvdata /data /protect_f /protect_s /data/ccci_cfg /dev/radio
    if mountpoint -q /nvdata; then
        mount -o remount,rw /nvdata 2>/dev/null || true
    else
        mount -t ext4 /dev/mmcblk0p18 /nvdata
    fi
    ln -sfn /nvdata /data/nvram
    mountpoint -q /protect_f || mount -t ext4 /dev/mmcblk0p3 /protect_f
    mountpoint -q /protect_s || mount -t ext4 /dev/mmcblk0p4 /protect_s

    # 2. Raw nvram node + Android log dir + permission check marker
    ln -sfn /dev/mmcblk0p2 /dev/nvram
    if [ ! -d /dev/log ]; then
        rm -f /dev/log
        mkdir -p /dev/log
    fi
    for f in main radio events system; do
        touch "/dev/log/$f"
        chmod 666 "/dev/log/$f"
    done
    chmod 770 /data/ccci_cfg
    touch /data/ccci_cfg/md_new_ver.1

    # 3. Block symlinks required by kernel MASP (sec_dev_read_rom_info / secro / seccfg)
    mkdir -p /dev/block /dev/block/platform/mtk-msdc.0/by-name
    for d in /dev/mmcblk0 /dev/mmcblk0boot0 /dev/mmcblk0boot1 /dev/mmcblk0p* \
             /dev/mmcblk1 /dev/mmcblk1p*; do
        [ -e "$d" ] || continue
        ln -sfn "$d" "/dev/block/$(basename "$d")"
    done
    ln -sfn /dev/mmcblk0boot0 /dev/block/platform/mtk-msdc.0/mmcblk0boot0
    ln -sfn /dev/mmcblk0boot1 /dev/block/platform/mtk-msdc.0/mmcblk0boot1
    ln -sfn /dev/mmcblk0 /dev/block/platform/mtk-msdc.0/mmcblk0
    for u in /sys/block/mmcblk0/mmcblk0p*/uevent; do
        [ -f "$u" ] || continue
        devname=$(sed -n 's/^DEVNAME=//p' "$u")
        partname=$(sed -n 's/^PARTNAME=//p' "$u")
        if [ -n "$devname" ] && [ -n "$partname" ]; then
            ln -sfn "/dev/$devname" "/dev/block/platform/mtk-msdc.0/by-name/$partname"
        fi
    done

    # 4. Ensure property_service.py is running and mark upper modem services running
    if ! pgrep -f property_service.py >/dev/null 2>&1 && [ -f /usr/local/bin/property_service.py ]; then
        nohup python3 /usr/local/bin/property_service.py </dev/null >/var/log/property_service.log 2>&1 &
        sleep 1
    fi
    for svc in emdlogger1 gsm0710muxd ril-daemon-mtk ccci_fsd; do
        /system/bin/toolbox setprop "init.svc.$svc" running 2>/dev/null || true
    done
}

send_at() {
    CMD="$1"
    WAIT="${2:-3.0}"
    python3 -u - "$AT_PORT" "$CMD" "$WAIT" << 'PYEOF'
import os, select, sys, termios, time
port, cmd, wait = sys.argv[1], sys.argv[2], float(sys.argv[3])
fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
attrs = termios.tcgetattr(fd)
attrs[3] &= ~(termios.ECHO | termios.ICANON | termios.ISIG)
termios.tcsetattr(fd, termios.TCSANOW, attrs)
os.write(fd, (cmd + "\r").encode())
out = b""
end = time.time() + wait
while time.time() < end:
    r, _, _ = select.select([fd], [], [], 0.2)
    if r:
        c = os.read(fd, 4096)
        if c:
            out += c
            lines = [l.strip() for l in out.decode("ascii", errors="ignore").splitlines()]
            if "OK" in lines or "ERROR" in lines or any(l.startswith("+CME ERROR") for l in lines):
                break
os.close(fd)
print(out.decode("ascii", errors="ignore").strip())
PYEOF
}

case "$1" in
    start)
        prepare_env
        killall -9 gsm0710muxd ccci_mdinit ccci_fsd 2>/dev/null || true
        sleep 1
        nohup /system/bin/ccci_fsd 0 </dev/null >/var/log/ccci_fsd.log 2>&1 &
        sleep 1
        nohup /system/bin/ccci_mdinit 0 </dev/null >/var/log/ccci_mdinit.log 2>&1 &
        sleep 6
        nohup /system/bin/gsm0710muxd -s /dev/ttyC0 -f 512 -n 8 -m basic </dev/null >/var/log/muxd.log 2>&1 &
        sleep 2
        echo "Modem boot: $(cat /sys/kernel/ccci/boot 2>/dev/null)"
        echo "AT port:    $(ls -l "$AT_PORT" 2>/dev/null || echo missing)"
        ;;
    stop)
        killall -9 gsm0710muxd ccci_mdinit ccci_fsd 2>/dev/null || true
        echo "Modem daemons stopped"
        ;;
    status)
        echo "CCCI boot:  $(cat /sys/kernel/ccci/boot 2>/dev/null)"
        echo "MD status:  $(/system/bin/toolbox getprop mtk.md1.status 2>/dev/null)"
        ps w | grep -E 'ccci_fsd|ccci_mdinit|gsm0710muxd' | grep -v grep || true
        ;;
    rf-on)
        send_at "ATE0" 1.5 >/dev/null
        send_at "AT+CFUN=4" 4.0
        send_at "AT+EFUN=1" 5.0
        send_at "AT+CFUN=1" 5.0
        ;;
    rf-off)
        send_at "AT+CFUN=0" 4.0
        ;;
    scan)
        echo "=== CSQ ==="
        send_at "AT+CSQ" 2.0
        echo "=== CESQ ==="
        send_at "AT+CESQ" 2.0
        echo "=== ECELL ==="
        send_at "AT+ECELL" 3.0
        ;;
    at)
        shift
        send_at "$*" 5.0
        ;;
    *)
        echo "Usage: $0 {start|stop|status|rf-on|rf-off|scan|at <CMD>}"
        exit 1
        ;;
esac
