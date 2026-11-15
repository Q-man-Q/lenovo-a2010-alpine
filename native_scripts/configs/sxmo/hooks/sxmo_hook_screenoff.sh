#!/bin/sh
# configversion: 6547d89cee221bcd21a4724f3a2e268f
# Lenovo A2010 Screen Off Hook
. sxmo_common.sh

# 1. Turn off LCD backlight completely
echo 0 > /sys/class/leds/lcd-backlight/brightness 2>/dev/null || true

# 2. Put CPU into powersave governor
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo powersave > "$cpu" 2>/dev/null || true
done

# 3. Call standard Sxmo screenoff hook
if [ -f /usr/share/sxmo/default_hooks/sxmo_hook_screenoff.sh ]; then
    /usr/share/sxmo/default_hooks/sxmo_hook_screenoff.sh "$@"
fi
