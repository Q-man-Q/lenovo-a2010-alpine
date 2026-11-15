#!/bin/sh
export DISPLAY=:0

DMENU='dmenu -i -l 10'

ensure_wifi() {
    ip link set wlan0 up 2>/dev/null || true
    if ! wpa_cli -i wlan0 ping >/dev/null 2>&1; then
        rm -f /var/run/wpa_supplicant/wlan0
        wpa_supplicant -B -i wlan0 -D nl80211 -c /etc/wpa_supplicant/wpa_supplicant.conf
        sleep 1
    fi
}

show_status() {
    st=$(wpa_cli -i wlan0 status 2>/dev/null)
    state=$(echo "$st" | awk -F= '/^wpa_state=/{print $2}')
    ssid=$(echo "$st" | awk -F= '/^ssid=/{print $2}')
    ip=$(ip -4 addr show wlan0 2>/dev/null | awk '/inet /{print $2}' | head -n1)
    notify-send "Wi-Fi Status" "State: ${state:-DOWN}\nSSID: ${ssid:-none}\nIP: ${ip:-none}"
}

ensure_wifi

while true; do
    notify-send "Wi-Fi" "Scanning 2.4 GHz..."
    wpa_cli -i wlan0 scan >/dev/null 2>&1
    sleep 3

    nets=$(wpa_cli -i wlan0 scan_results 2>/dev/null | tail -n +2 | awk -F'\t' '
        $5 != "" {
            if (!seen[$5] || $3 > sig[$5]) {
                seen[$5] = 1
                sig[$5] = $3
                sec[$5] = ($4 ~ /WPA|WEP|RSN/) ? "[SEC]" : "[OPEN]"
            }
        }
        END {
            for (s in seen) printf "%s  (%s dBm) %s\n", s, sig[s], sec[s]
        }
    ' | sort -t'(' -k2 -nr)

    if [ -z "$nets" ]; then
        menu="[Rescan]\n[Status]\n[Disconnect]\n(No 2.4 GHz networks found)"
    else
        menu="[Rescan]\n[Status]\n[Disconnect]\n$nets"
    fi

    choice=$(printf '%b\n' "$menu" | $DMENU -p "Wi-Fi:")
    [ -z "$choice" ] && exit 0

    case "$choice" in
        "[Rescan]")
            continue
            ;;
        "[Status]")
            show_status
            exit 0
            ;;
        "[Disconnect]")
            wpa_cli -i wlan0 disconnect >/dev/null 2>&1
            ip addr flush dev wlan0 2>/dev/null || true
            notify-send "Wi-Fi" "Disconnected"
            exit 0
            ;;
        "(No 2.4 GHz networks found)")
            continue
            ;;
    esac

    ssid=$(printf '%s' "$choice" | sed 's/  ([^)]*) \[.*$//')
    is_sec=$(printf '%s' "$choice" | grep -c '\[SEC\]')

    if [ "$is_sec" -gt 0 ]; then
        sxmo_keyboard.sh open >/dev/null 2>&1 || true
        pass=$(printf '' | dmenu -p "Pass ($ssid):")
        sxmo_keyboard.sh close >/dev/null 2>&1 || true
        [ -z "$pass" ] && exit 0
    fi

    net_id=$(wpa_cli -i wlan0 add_network | tail -n1)
    wpa_cli -i wlan0 set_network "$net_id" ssid "\"$ssid\"" >/dev/null
    if [ "$is_sec" -gt 0 ]; then
        wpa_cli -i wlan0 set_network "$net_id" psk "\"$pass\"" >/dev/null
    else
        wpa_cli -i wlan0 set_network "$net_id" key_mgmt NONE >/dev/null
    fi
    wpa_cli -i wlan0 enable_network "$net_id" >/dev/null
    wpa_cli -i wlan0 select_network "$net_id" >/dev/null
    wpa_cli -i wlan0 save_config >/dev/null 2>&1 || true

    notify-send "Wi-Fi" "Connecting to $ssid..."
    udhcpc -i wlan0 -n -q -t 6 >/dev/null 2>&1 || true
    show_status
    exit 0
done
