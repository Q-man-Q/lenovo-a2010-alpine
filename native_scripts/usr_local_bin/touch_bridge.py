#!/usr/bin/env python3
import os, stat, struct, fcntl, time, ctypes, subprocess

os.environ['DISPLAY'] = ':0'
os.environ['PATH'] = '/root/.config/sxmo/hooks:/usr/share/sxmo/default_hooks:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
os.environ['HOME'] = '/root'
os.environ['USER'] = 'root'
os.environ['SXMO_DEVICE_NAME'] = 'lenovo_a2010'
os.environ['SXMO_WM'] = 'dwm'
os.environ['XDG_CURRENT_DESKTOP'] = 'dwm'
os.environ['KEYBOARD'] = 'svkbd-mobile-intl'

class input_id(ctypes.Structure):
    _fields_ = [
        ('bustype', ctypes.c_uint16),
        ('vendor', ctypes.c_uint16),
        ('product', ctypes.c_uint16),
        ('version', ctypes.c_uint16)
    ]

class uinput_user_dev(ctypes.Structure):
    _fields_ = [
        ('name', ctypes.c_char * 80),
        ('id', input_id),
        ('ff_effects_max', ctypes.c_uint32),
        ('absmax', ctypes.c_int32 * 64),
        ('absmin', ctypes.c_int32 * 64),
        ('absfuzz', ctypes.c_int32 * 64),
        ('absflat', ctypes.c_int32 * 64)
    ]

EV_SYN = 0x00
EV_KEY = 0x01
EV_REL = 0x02
EV_ABS = 0x03

SYN_REPORT = 0x00
BTN_TOUCH  = 0x14a
REL_WHEEL  = 0x08

ABS_X      = 0x00
ABS_Y      = 0x01
ABS_MT_POSITION_X  = 0x35
ABS_MT_POSITION_Y  = 0x36
ABS_MT_TRACKING_ID = 0x39

UI_SET_EVBIT   = 0x40045564
UI_SET_KEYBIT  = 0x40045565
UI_SET_RELBIT  = 0x40045566
UI_SET_ABSBIT  = 0x40045567
UI_SET_PROPBIT = 0x4004556e
UI_DEV_CREATE  = 0x5501
UI_DEV_DESTROY = 0x5502
INPUT_PROP_DIRECT = 0x01

# --- Device 1: Pure Calibrated TOUCHSCREEN (BTN_TOUCH ONLY) ---
ptr_fd = os.open('/dev/uinput', os.O_RDWR)
fcntl.ioctl(ptr_fd, UI_SET_EVBIT, EV_SYN)
fcntl.ioctl(ptr_fd, UI_SET_EVBIT, EV_KEY)
fcntl.ioctl(ptr_fd, UI_SET_EVBIT, EV_ABS)
fcntl.ioctl(ptr_fd, UI_SET_PROPBIT, INPUT_PROP_DIRECT)
fcntl.ioctl(ptr_fd, UI_SET_KEYBIT, BTN_TOUCH)
fcntl.ioctl(ptr_fd, UI_SET_ABSBIT, ABS_X)
fcntl.ioctl(ptr_fd, UI_SET_ABSBIT, ABS_Y)

dev_ptr = uinput_user_dev()
dev_ptr.name = b'touch_pointer'
dev_ptr.id.bustype = 0x03
dev_ptr.id.vendor = 0x1234
dev_ptr.id.product = 0x5678
dev_ptr.id.version = 1
dev_ptr.absmin[0] = 0; dev_ptr.absmax[0] = 480
dev_ptr.absmin[1] = 0; dev_ptr.absmax[1] = 854

os.write(ptr_fd, bytes(dev_ptr))
fcntl.ioctl(ptr_fd, UI_DEV_CREATE)

# --- Device 2: Virtual Scroll Wheel ---
wheel_fd = os.open('/dev/uinput', os.O_RDWR)
fcntl.ioctl(wheel_fd, UI_SET_EVBIT, EV_SYN)
fcntl.ioctl(wheel_fd, UI_SET_EVBIT, EV_REL)
fcntl.ioctl(wheel_fd, UI_SET_RELBIT, REL_WHEEL)

dev_wheel = uinput_user_dev()
dev_wheel.name = b'virt_wheel'
dev_wheel.id.bustype = 0x03
dev_wheel.id.vendor = 0x1234
dev_wheel.id.product = 0x5679
dev_wheel.id.version = 1

os.write(wheel_fd, bytes(dev_wheel))
fcntl.ioctl(wheel_fd, UI_DEV_CREATE)
time.sleep(0.15)

# Create device nodes and symlinks directly without slow mdev -s
for entry in os.listdir('/sys/class/input'):
    name_file = f'/sys/class/input/{entry}/device/name'
    dev_file = f'/sys/class/input/{entry}/dev'
    if os.path.exists(name_file) and os.path.exists(dev_file):
        try:
            with open(name_file, 'r') as f:
                dev_name = f.read().strip()
            if dev_name in ('touch_pointer', 'virt_wheel'):
                target = f'/dev/input/{entry}'
                if not os.path.exists(target):
                    with open(dev_file, 'r') as df:
                        maj, min_ = map(int, df.read().strip().split(':'))
                    os.mknod(target, 0o660 | stat.S_IFCHR, os.makedev(maj, min_))
                link_path = f'/dev/input/{dev_name}'
                try:
                    os.unlink(link_path)
                except OSError:
                    pass
                os.symlink(target, link_path)
                print(f'Ready: {target} -> {link_path}', flush=True)
        except Exception as e:
            print(f'Error setting up {entry}: {e}', flush=True)

EVENT_FORMAT = 'iiHHi'
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

def emit_ptr(ev_type, ev_code, ev_value):
    pkt = struct.pack('iiHHi', 0, 0, ev_type, ev_code, ev_value)
    os.write(ptr_fd, pkt)

def emit_wheel(rel_code, rel_value):
    pkt = struct.pack('iiHHi', 0, 0, EV_REL, rel_code, rel_value)
    os.write(wheel_fd, pkt)
    pkt_syn = struct.pack('iiHHi', 0, 0, EV_SYN, SYN_REPORT, 0)
    os.write(wheel_fd, pkt_syn)

def vibrate(ms=25):
    try:
        with open('/sys/class/timed_output/vibrator/enable', 'w') as vf:
            vf.write(str(ms))
    except Exception:
        pass

_screen_off_cache = False
_screen_off_ts = 0.0

def is_screen_off():
    global _screen_off_cache, _screen_off_ts
    now = time.time()
    if now - _screen_off_ts < 0.4:
        return _screen_off_cache
    _screen_off_ts = now
    try:
        with open('/sys/class/leds/lcd-backlight/brightness', 'r') as bf:
            _screen_off_cache = (int(bf.read().strip() or '255') == 0)
    except Exception:
        _screen_off_cache = False
    return _screen_off_cache

def trigger_softkey(px):
    vibrate(25)
    print(f"Softkey touch detected at px={px}", flush=True)
    try:
        if px >= 200:
            # ПРАВАЯ КНОПКА (Назад, px=250):
            # 1. Если открыто dmenu -> закрываем его
            # 2. Иначе если открыта клавиатура -> закрываем клавиатуру
            # 3. Иначе закрываем текущее окно (sxmo_killwindow.sh)
            cmd = 'if sxmo_dmenu.sh isopen; then sxmo_dmenu.sh close; elif sxmo_keyboard.sh isopen; then sxmo_keyboard.sh close; else sxmo_killwindow.sh; fi'
            subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=os.environ)
        elif px >= 100:
            # СРЕДНЯЯ КНОПКА (Домой, px=150):
            # Если меню открыто -> закрываем, иначе открываем главное меню приложений Sxmo
            cmd = 'if sxmo_dmenu.sh isopen; then sxmo_dmenu.sh close; else sxmo_appmenu.sh; fi'
            subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=os.environ)
        else:
            # ЛЕВАЯ КНОПКА (Меню, px=50):
            # Переключение экранной клавиатуры svkbd-mobile-intl
            subprocess.Popen('sxmo_keyboard.sh toggle', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=os.environ)
    except Exception as e:
        print(f"Error triggering softkey: {e}", flush=True)

cur_xs = []
cur_ys = []
btn_touch_val = None
is_softkey = False
softkey_pressed = False

last_x = 240
last_y = 427
down_x = 240
down_y = 427
touch_down = False
scroll_mode = False
prev_mid_y = 0.0
scroll_acc = 0.0

phys_fd = None

while True:
    try:
        if phys_fd is None:
            phys_fd = os.open('/dev/input/event2', os.O_RDONLY)
            print('Connected to /dev/input/event2', flush=True)

        data = os.read(phys_fd, EVENT_SIZE * 32)
        if not data:
            time.sleep(0.05)
            continue

        for i in range(0, len(data), EVENT_SIZE):
            chunk = data[i:i+EVENT_SIZE]
            if len(chunk) < EVENT_SIZE:
                break
            _, _, ev_type, ev_code, ev_value = struct.unpack(EVENT_FORMAT, chunk)

            if ev_type == EV_ABS:
                if ev_code in (ABS_X, ABS_MT_POSITION_X):
                    cur_xs.append(max(0, min(480, ev_value)))
                elif ev_code in (ABS_Y, ABS_MT_POSITION_Y):
                    # Active LCD screen is Y=0..853.
                    # Capacitive softkeys are at Y=904.
                    if ev_value < 854:
                        cur_ys.append(ev_value)
                    else:
                        is_softkey = True

                elif ev_code == ABS_MT_TRACKING_ID:
                    if ev_value == -1:
                        btn_touch_val = 0

            elif ev_type == EV_KEY and ev_code == BTN_TOUCH:
                btn_touch_val = ev_value

            elif ev_type == EV_SYN and ev_code == SYN_REPORT:
                # Pocket-lock: ignore all touchscreen/softkey inputs when LCD backlight is off
                if is_screen_off():
                    if touch_down:
                        touch_down = False
                        emit_ptr(EV_KEY, BTN_TOUCH, 0)
                        emit_ptr(EV_SYN, SYN_REPORT, 0)
                    scroll_mode = False
                    scroll_acc = 0.0
                    softkey_pressed = False
                    cur_xs.clear()
                    cur_ys.clear()
                    is_softkey = False
                    btn_touch_val = None
                    continue

                # If touched on capacitive softkeys (below LCD):
                if is_softkey:
                    if touch_down:
                        touch_down = False
                        emit_ptr(EV_KEY, BTN_TOUCH, 0)
                        emit_ptr(EV_SYN, SYN_REPORT, 0)
                    scroll_mode = False
                    scroll_acc = 0.0

                    if not softkey_pressed and btn_touch_val != 0:
                        softkey_pressed = True
                        px = cur_xs[0] if cur_xs else 250
                        trigger_softkey(px)

                    if btn_touch_val == 0:
                        softkey_pressed = False

                    cur_xs.clear()
                    cur_ys.clear()
                    is_softkey = False
                    btn_touch_val = None
                    continue

                if btn_touch_val == 0:
                    softkey_pressed = False

                n_fingers = max(len(cur_xs), len(cur_ys))

                if btn_touch_val == 0:
                    n_fingers = 0

                if n_fingers == 1:
                    # Single finger: pure 1:1 direct touchscreen tap inside LCD
                    px = cur_xs[0] if cur_xs else last_x
                    py = cur_ys[0] if cur_ys else last_y

                    if scroll_mode:
                        scroll_mode = False
                        scroll_acc = 0.0

                    if not touch_down:
                        # First touch-down frame: warp cursor FIRST so X11 delivers EnterNotify/MotionNotify
                        down_x, down_y = px, py
                        last_x, last_y = px, py
                        emit_ptr(EV_ABS, ABS_X, px)
                        emit_ptr(EV_ABS, ABS_Y, py)
                        emit_ptr(EV_SYN, SYN_REPORT, 0)
                        time.sleep(0.008)
                        touch_down = True
                        emit_ptr(EV_KEY, BTN_TOUCH, 1)
                        emit_ptr(EV_SYN, SYN_REPORT, 0)
                    else:
                        # Jitter filter: ignore tiny thumb roll (<12px) so taps don't become drags
                        if abs(px - down_x) < 12 and abs(py - down_y) < 12:
                            px, py = down_x, down_y
                        last_x, last_y = px, py
                        emit_ptr(EV_ABS, ABS_X, px)
                        emit_ptr(EV_ABS, ABS_Y, py)
                        emit_ptr(EV_SYN, SYN_REPORT, 0)

                elif n_fingers >= 2:
                    # Two fingers: smooth vertical scroll wheel
                    if touch_down:
                        touch_down = False
                        emit_ptr(EV_KEY, BTN_TOUCH, 0)
                        emit_ptr(EV_SYN, SYN_REPORT, 0)

                    mid_y = sum(cur_ys) / float(len(cur_ys)) if cur_ys else last_y

                    if not scroll_mode:
                        scroll_mode = True
                        prev_mid_y = mid_y
                        scroll_acc = 0.0
                    else:
                        dy = mid_y - prev_mid_y
                        scroll_acc += dy
                        SCROLL_THRESHOLD = 15.0
                        while scroll_acc >= SCROLL_THRESHOLD:
                            emit_wheel(REL_WHEEL, 1)
                            scroll_acc -= SCROLL_THRESHOLD
                        while scroll_acc <= -SCROLL_THRESHOLD:
                            emit_wheel(REL_WHEEL, -1)
                            scroll_acc += SCROLL_THRESHOLD
                        prev_mid_y = mid_y

                elif n_fingers == 0:
                    # Finger lifted (either BTN_TOUCH=0 or empty MT SYN_REPORT)
                    if touch_down:
                        touch_down = False
                        emit_ptr(EV_KEY, BTN_TOUCH, 0)
                        emit_ptr(EV_SYN, SYN_REPORT, 0)
                    scroll_mode = False
                    scroll_acc = 0.0
                    softkey_pressed = False

                cur_xs.clear()
                cur_ys.clear()
                btn_touch_val = None

    except Exception as e:
        time.sleep(0.1)
        try:
            if phys_fd is not None:
                os.close(phys_fd)
        except:
            pass
        phys_fd = None
