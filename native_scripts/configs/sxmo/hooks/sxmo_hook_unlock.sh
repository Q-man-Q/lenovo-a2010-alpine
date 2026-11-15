#!/bin/sh
# configversion: c3c6fd13bb040fca12861b9ead18302d
# Lenovo A2010 Unlock Hook
. sxmo_common.sh

# 1. Call standard Sxmo unlock hook
if [ -f /usr/share/sxmo/default_hooks/sxmo_hook_unlock.sh ]; then
    /usr/share/sxmo/default_hooks/sxmo_hook_unlock.sh "$@"
fi

# 2. Restore LCD backlight to full
echo 255 > /sys/class/leds/lcd-backlight/brightness 2>/dev/null || true

# 3. Restore CPU governor to interactive
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo interactive > "$cpu" 2>/dev/null || true
done

# 4. Short vibration feedback on unlock
echo 20 > /sys/class/timed_output/vibrator/enable 2>/dev/null || true
