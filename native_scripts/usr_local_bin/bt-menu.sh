#!/bin/sh
# Sxmo Bluetooth wrapper for Lenovo A2010-a (MT6625L / /dev/stpbt + Google Bumble)

export DISPLAY="${DISPLAY:-:0}"
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

LOG_FILE="/var/log/bt-server.log"
BT_SERVER="/usr/local/bin/bt-server.py"

ensure_dev() {
    if [ ! -c /dev/stpbt ] || [ "$(stat -c '%t:%T' /dev/stpbt 2>/dev/null)" != "c0:0" ]; then
        rm -f /dev/stpbt
        mknod /dev/stpbt c 192 0
        chmod 660 /dev/stpbt
    fi
}

is_running() {
    pgrep -f "$BT_SERVER" >/dev/null 2>&1
}

notify() {
    if command -v sxmo_notify_user.sh >/dev/null 2>&1; then
        sxmo_notify_user.sh "$1" >/dev/null 2>&1 &
    elif command -v notify-send >/dev/null 2>&1; then
        notify-send "Bluetooth" "$1" >/dev/null 2>&1 &
    fi
}

start_bt() {
    ensure_dev
    if is_running; then
        echo "Bluetooth already running"
        return 0
    fi
    nohup python3 -u "$BT_SERVER" </dev/null >"$LOG_FILE" 2>&1 &
    sleep 3
    if is_running; then
        notify "Bluetooth ON: Lenovo-A2010-Alpine"
    DISPLAY=:0 SXMO_WM=dwm XDG_RUNTIME_DIR=/dev/shm/user/0 SXMO_STATE=/dev/shm/user/0/sxmo.state /usr/bin/sxmo_hook_statusbar.sh periodics >/dev/null 2>&1 &
        echo "Bluetooth started"
    else
        notify "Bluetooth failed to start (see $LOG_FILE)"
    DISPLAY=:0 SXMO_WM=dwm XDG_RUNTIME_DIR=/dev/shm/user/0 SXMO_STATE=/dev/shm/user/0/sxmo.state /usr/bin/sxmo_hook_statusbar.sh periodics >/dev/null 2>&1 &
        echo "Bluetooth failed to start"
        return 1
    fi
}

stop_bt() {
    if is_running; then
        pkill -f "$BT_SERVER" 2>/dev/null || true
        sleep 1
    fi
    notify "Bluetooth OFF"
    DISPLAY=:0 SXMO_WM=dwm XDG_RUNTIME_DIR=/dev/shm/user/0 SXMO_STATE=/dev/shm/user/0/sxmo.state /usr/bin/sxmo_hook_statusbar.sh periodics >/dev/null 2>&1 &
    echo "Bluetooth stopped"
}

scan_ble() {
    WAS_RUNNING=0
    if is_running; then
        WAS_RUNNING=1
        pkill -f "$BT_SERVER" 2>/dev/null || true
        sleep 1
    fi
    ensure_dev
    RESULTS=$(python3 -c '
import os, select, time

def parse_name(adv):
    i = 0
    while i + 1 < len(adv):
        ln = adv[i]
        if ln == 0 or i + 1 + ln > len(adv):
            break
        ad_type = adv[i + 1]
        if ad_type in (0x08, 0x09):
            return adv[i + 2 : i + 1 + ln].decode("utf-8", errors="ignore").strip()
        i += 1 + ln
    return ""

fd = os.open("/dev/stpbt", os.O_RDWR)
def send(b):
    os.write(fd, bytes(b))
    r, _, _ = select.select([fd], [], [], 1.0)
    return os.read(fd, 512) if r else b""

send([0x01, 0x03, 0x0c, 0x00])
send([0x01, 0x01, 0x0c, 0x08, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0x3f])
send([0x01, 0x01, 0x20, 0x08, 0x1f, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
send([0x01, 0x0b, 0x20, 0x07, 0x01, 0x10, 0x00, 0x10, 0x00, 0x00, 0x00])
send([0x01, 0x0c, 0x20, 0x02, 0x01, 0x00])

seen = {}
end = time.time() + 4.0
while time.time() < end:
    r, _, _ = select.select([fd], [], [], 0.25)
    if not r:
        continue
    pkt = os.read(fd, 512)
    if len(pkt) > 14 and pkt[0] == 0x04 and pkt[1] == 0x3e and pkt[3] == 0x02:
        mac = ":".join(f"{x:02X}" for x in reversed(pkt[7:13]))
        dlen = pkt[13]
        adv = pkt[14 : 14 + dlen]
        rssi = pkt[-1] - 256 if pkt[-1] > 127 else pkt[-1]
        name = parse_name(adv)
        prev_name, _ = seen.get(mac, ("", -127))
        seen[mac] = (name or prev_name, rssi)

send([0x01, 0x0c, 0x20, 0x02, 0x00, 0x00])
os.close(fd)
for mac, (name, rssi) in sorted(seen.items(), key=lambda kv: kv[1][1], reverse=True):
    label = f"{name} " if name else ""
    print(f"{label}[{mac}] ({rssi} dBm)")
' 2>/dev/null)

    if [ "$WAS_RUNNING" = "1" ]; then
        nohup python3 -u "$BT_SERVER" </dev/null >"$LOG_FILE" 2>&1 &
    fi

    if [ -z "$RESULTS" ]; then
        printf "No BLE devices found\n"
    else
        printf "%s\n" "$RESULTS"
    fi
}

case "$1" in
    status)
        if is_running; then
            echo "on"
        else
            echo "off"
        fi
        exit 0
        ;;
    start)
        start_bt
        exit $?
        ;;
    stop)
        stop_bt
        exit 0
        ;;
    toggle)
        if is_running; then
            stop_bt
        else
            start_bt
        fi
        exit $?
        ;;
    scan)
        scan_ble
        exit 0
        ;;
esac

# Interactive Sxmo dmenu UI
DMENU="dmenu -i -l 10"
if command -v sxmo_dmenu.sh >/dev/null 2>&1; then
    DMENU="sxmo_dmenu.sh"
fi

if is_running; then
    TOGGLE_LINE="Bluetooth: ON -> Turn OFF"
else
    TOGGLE_LINE="Bluetooth: OFF -> Turn ON"
fi

CHOICE=$(printf "%s\n%s\n%s\n%s\n" \
    "$TOGGLE_LINE" \
    "Scan BLE devices (4s)" \
    "Status & Log (Lenovo-A2010-Alpine)" \
    "Close" | $DMENU -p "Bluetooth")

case "$CHOICE" in
    "Bluetooth: ON -> Turn OFF")
        stop_bt >/dev/null
        ;;
    "Bluetooth: OFF -> Turn ON")
        start_bt >/dev/null
        ;;
    "Scan BLE devices (4s)")
        notify "Scanning BLE (4s)..."
        scan_ble | $DMENU -p "BLE Devices" >/dev/null
        ;;
    "Status & Log"*)
        if [ -f "$LOG_FILE" ]; then
            tail -n 12 "$LOG_FILE" | $DMENU -p "BT Log" >/dev/null
        else
            printf "No log yet\n" | $DMENU -p "BT Log" >/dev/null
        fi
        ;;
esac
