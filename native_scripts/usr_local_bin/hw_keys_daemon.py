#!/usr/bin/env python3
"""
Lenovo A2010 Hardware & Capacitive Keys Daemon (postmarketOS Sxmo + Android style)
- Power Button (event0, code 116): Screen Sleep / Wake toggle (backlight 0 <-> 255)
- Volume Up (event0, code 115):
    * Short press: Switch to next open window (bspc node -f next.local.!hidden.window)
    * Long press (>0.6s): Open Quick Settings Shade (cyberdeck-qs)
- Volume Down (event0, code 114):
    * Short press: Toggle On-Screen Keyboard (toggle-keyboard)
    * Long press (>0.6s): Switch keyboard language RU/EN (toggle-keyboard-lang)
- Capacitive Softkeys (event3): Menu (139), Home (172), Back (158)
"""
import os
import select
import struct
import time
import subprocess

KEY_VOLUMEDOWN = 114
KEY_VOLUMEUP   = 115
KEY_POWER      = 116
KEY_MENU       = 139
KEY_BACK       = 158
KEY_HOMEPAGE   = 172

EV_KEY = 0x01
EVENT_FORMAT = 'iiHHi'
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

os.environ['DISPLAY'] = ':0'
os.environ['PATH'] = '/root/.config/sxmo/hooks:/usr/share/sxmo/default_hooks:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
os.environ['HOME'] = '/root'
os.environ['USER'] = 'root'
os.environ['SXMO_DEVICE_NAME'] = 'lenovo_a2010'
os.environ['SXMO_WM'] = 'dwm'
os.environ['XDG_CURRENT_DESKTOP'] = 'dwm'
os.environ['KEYBOARD'] = 'svkbd-mobile-intl'

def run_action(cmd):
    try:
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=os.environ)
    except Exception:
        pass

def set_cpu_governor(gov):
    for cpu in ('cpu0', 'cpu1', 'cpu2', 'cpu3'):
        p = f'/sys/devices/system/cpu/{cpu}/cpufreq/scaling_governor'
        if os.path.exists(p):
            try:
                with open(p, 'w') as gf:
                    gf.write(gov)
            except Exception:
                pass

def vibrate(ms=25):
    try:
        with open('/sys/class/timed_output/vibrator/enable', 'w') as vf:
            vf.write(str(ms))
    except Exception:
        pass

BL_PATH = '/sys/class/leds/lcd-backlight/brightness'
SAVED_BL_FILE = '/tmp/saved_brightness'
TIMEOUT_FILE = '/tmp/screen_timeout'

dimmed = False
last_activity = time.time()

def get_brightness():
    try:
        with open(BL_PATH, 'r') as f:
            return int(f.read().strip() or '255')
    except Exception:
        return 255

def set_brightness(val):
    try:
        with open(BL_PATH, 'w') as f:
            f.write(str(int(val)))
    except Exception:
        pass

def get_saved_brightness():
    try:
        with open(SAVED_BL_FILE, 'r') as sf:
            return max(30, int(sf.read().strip()))
    except Exception:
        return 255

def save_brightness(val):
    if val >= 30:
        try:
            with open(SAVED_BL_FILE, 'w') as sf:
                sf.write(str(int(val)))
        except Exception:
            pass

def get_timeout_sec():
    # 0 disables automatic screen sleep during debugging
    try:
        if os.path.exists(TIMEOUT_FILE):
            with open(TIMEOUT_FILE, 'r') as tf:
                return int(tf.read().strip())
    except Exception:
        pass
    return 0

def is_video_playing():
    try:
        return subprocess.call('/bin/busybox pgrep -f /usr/local/bin/cyberplay >/dev/null 2>&1', shell=True) == 0
    except Exception:
        return False

def wake_from_dim():
    global dimmed
    if dimmed:
        dimmed = False
        if get_brightness() > 0:
            set_brightness(get_saved_brightness())

def toggle_screen_power():
    global dimmed, last_activity
    cur = get_brightness()
    if cur > 0:
        if not dimmed:
            save_brightness(cur)
        dimmed = False
        set_brightness(0)
        set_cpu_governor('powersave')
        run_action('/usr/bin/sxmo_state.sh set screenoff')
    else:
        dimmed = False
        last_activity = time.time()
        set_brightness(get_saved_brightness())
        set_cpu_governor('interactive')
        run_action('/usr/bin/sxmo_state.sh set unlock')
        vibrate(20)

fds = {}
press_times = {}

def open_inputs():
    for dev in ('/dev/input/event0', '/dev/input/event2', '/dev/input/event3'):
        if dev not in fds and os.path.exists(dev):
            try:
                fds[dev] = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
            except Exception:
                pass

while True:
    try:
        open_inputs()
        if not fds:
            time.sleep(0.5)
            continue

        rlist, _, _ = select.select(list(fds.values()), [], [], 1.0)
        now = time.time()

        # Check auto screen timeout when idle
        if not rlist:
            timeout_sec = get_timeout_sec()
            if timeout_sec > 0:
                cur_bl = get_brightness()
                if cur_bl > 0:
                    if is_video_playing():
                        last_activity = now
                    else:
                        idle = now - last_activity
                        if idle >= timeout_sec:
                            if not dimmed:
                                save_brightness(cur_bl)
                            dimmed = False
                            set_brightness(0)
                            set_cpu_governor('powersave')
                        elif idle >= max(15, timeout_sec - 12) and not dimmed:
                            save_brightness(cur_bl)
                            dimmed = True
                            set_brightness(20)

        for fd in rlist:
            dev_path = None
            for k, v in fds.items():
                if v == fd:
                    dev_path = k
                    break
            try:
                data = os.read(fd, EVENT_SIZE * 16)
            except OSError:
                if dev_path:
                    try:
                        os.close(fd)
                    except Exception:
                        pass
                    del fds[dev_path]
                continue

            if not data:
                continue

            # Touchscreen activity on event2 resets idle timer & wakes from dim
            if dev_path == '/dev/input/event2':
                if get_brightness() > 0:
                    last_activity = now
                    wake_from_dim()
                continue

            for i in range(0, len(data), EVENT_SIZE):
                chunk = data[i:i+EVENT_SIZE]
                if len(chunk) < EVENT_SIZE:
                    break
                _, _, ev_type, ev_code, ev_value = struct.unpack(EVENT_FORMAT, chunk)
                if ev_type != EV_KEY:
                    continue

                if get_brightness() > 0:
                    last_activity = now
                    wake_from_dim()

                if ev_value == 1:  # Key Down
                    press_times[ev_code] = now

                elif ev_value == 0:  # Key Up
                    t0 = press_times.pop(ev_code, now)
                    held = now - t0
                    if ev_code == KEY_POWER:
                        if held >= 1.2:
                            if get_brightness() == 0:
                                toggle_screen_power()
                            run_action('/usr/local/bin/poweroff-dialog')
                        else:
                            toggle_screen_power()
                    elif get_brightness() > 0:
                        if ev_code == KEY_VOLUMEUP:
                            vibrate(20)
                            if held >= 0.6:
                                print("Vol+ long -> sys menu", flush=True)
                                run_action('/usr/bin/sxmo_appmenu.sh sys')
                            else:
                                print("Vol+ short -> app menu", flush=True)
                                run_action('/usr/bin/sxmo_appmenu.sh')
                        elif ev_code == KEY_VOLUMEDOWN:
                            vibrate(20)
                            if held >= 0.6:
                                print("Vol- long -> kill window", flush=True)
                                run_action('/usr/bin/sxmo_killwindow.sh')
                            else:
                                print("Vol- short -> toggle keyboard", flush=True)
                                run_action('/usr/bin/sxmo_keyboard.sh toggle')
                        elif ev_code == KEY_BACK:
                            vibrate(25)
                            print("Softkey BACK -> dismiss menu / dismiss kb / kill window", flush=True)
                            run_action('if sxmo_dmenu.sh isopen; then sxmo_dmenu.sh close; elif sxmo_keyboard.sh isopen; then sxmo_keyboard.sh close; else sxmo_killwindow.sh; fi')
                        elif ev_code == KEY_HOMEPAGE:
                            vibrate(25)
                            print("Softkey HOME -> toggle app menu", flush=True)
                            run_action('if sxmo_dmenu.sh isopen; then sxmo_dmenu.sh close; else sxmo_appmenu.sh; fi')
                        elif ev_code == KEY_MENU:
                            vibrate(25)
                            print("Softkey MENU -> toggle keyboard", flush=True)
                            run_action('/usr/bin/sxmo_keyboard.sh toggle')
    except Exception:
        time.sleep(0.5)
