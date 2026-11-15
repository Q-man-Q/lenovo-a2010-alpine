#!/bin/sh
set -e

case "$1" in
  start)
    mkdir -p /data/misc /data/gps_mnl /data/agps_supl
    [ -f /data/misc/mnl.prop ] || printf 'debug.debug_nmea=1\n' > /data/misc/mnl.prop
    [ -f /dev/__properties__ ] || python3 /usr/local/bin/mk-android-props.py

    killall -9 gpsd mnld 2>/dev/null || true
    rm -f /data/gps_mnl/hal2mnld /var/run/gpsd.sock

    ANDROID_ROOT=/system LD_LIBRARY_PATH=/system/lib:/vendor/lib /system/xbin/mnld >/var/log/mnld.log 2>&1 &
    echo $! > /var/run/mnld.pid

    i=0
    while [ ! -S /data/gps_mnl/hal2mnld ] && [ $i -lt 30 ]; do
        sleep 0.1
        i=$((i + 1))
    done

    python3 -c '
import socket, struct, time
cli = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
cli.sendto(struct.pack("<iiii", 2, 0, 0, 0), "/data/gps_mnl/hal2mnld")
time.sleep(0.5)
cli.sendto(struct.pack("<iiii", 3, 0, 0, 0), "/data/gps_mnl/hal2mnld")
'
    sleep 1
    gpsd -n -F /var/run/gpsd.sock /dev/gps
    echo "GPS started (mnld + gpsd on /dev/gps)"
    ;;
  stop)
    python3 -c '
import socket, struct
try:
    cli = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    cli.sendto(struct.pack("<iiii", 4, 0, 0, 0), "/data/gps_mnl/hal2mnld")
    cli.sendto(struct.pack("<iiii", 5, 0, 0, 0), "/data/gps_mnl/hal2mnld")
except Exception:
    pass
' 2>/dev/null || true
    killall -9 gpsd mnld 2>/dev/null || true
    rm -f /var/run/mnld.pid /var/run/gpsd.sock
    echo "GPS stopped"
    ;;
  status)
    ps aux | grep -E 'mnld|gpsd' | grep -v grep || echo "GPS stopped"
    ;;
  *)
    echo "Usage: $0 {start|stop|status}"
    exit 1
    ;;
esac
