#!/bin/sh
LED="/sys/class/leds/torch/brightness"
[ -w "$LED" ] || exit 1
CUR=$(cat "$LED" 2>/dev/null || echo 0)
if [ "$CUR" = "0" ]; then
    echo 255 > "$LED"
else
    echo 0 > "$LED"
fi
