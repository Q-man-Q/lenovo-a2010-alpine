#!/bin/sh
if pidof mnld >/dev/null 2>&1 && pidof gpsd >/dev/null 2>&1; then
    ST="ON"
else
    ST="OFF"
fi

CHOICE=$(printf '%s\n'     "Start GPS"     "Stop GPS"     "Live NMEA (gpspipe)"     "Status" | dmenu -i -p "GPS [$ST]:")

case "$CHOICE" in
    "Start GPS")
        /usr/local/bin/mtk-gps.sh start
        dunstify -r 998 "GPS Started" 2>/dev/null || true
        ;;
    "Stop GPS")
        /usr/local/bin/mtk-gps.sh stop
        dunstify -r 998 "GPS Stopped" 2>/dev/null || true
        ;;
    "Live NMEA (gpspipe)")
        sxmo_terminal.sh sh -c 'gpspipe -r'
        ;;
    "Status")
        sxmo_terminal.sh sh -c '/usr/local/bin/mtk-gps.sh status; echo; read -p "Press Enter..." _'
        ;;
esac
