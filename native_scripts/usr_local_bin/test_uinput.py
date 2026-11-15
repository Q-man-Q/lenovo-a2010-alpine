import struct, os, fcntl, time

UI_SET_EVBIT   = 0x40045564
UI_SET_KEYBIT  = 0x40045565
UI_SET_ABSBIT  = 0x40045567
UI_DEV_CREATE  = 0x5501
UI_DEV_DESTROY = 0x5502

EV_SYN = 0x00
EV_KEY = 0x01
EV_ABS = 0x03

BTN_TOUCH = 0x14a
BTN_LEFT  = 0x110
ABS_X     = 0x00
ABS_Y     = 0x01

fd = os.open('/dev/uinput', os.O_RDWR | os.O_NONBLOCK)
fcntl.ioctl(fd, UI_SET_EVBIT, EV_SYN)
fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
fcntl.ioctl(fd, UI_SET_EVBIT, EV_ABS)

fcntl.ioctl(fd, UI_SET_KEYBIT, BTN_TOUCH)
fcntl.ioctl(fd, UI_SET_KEYBIT, BTN_LEFT)

fcntl.ioctl(fd, UI_SET_ABSBIT, ABS_X)
fcntl.ioctl(fd, UI_SET_ABSBIT, ABS_Y)

# struct uinput_user_dev:
# char name[UINPUT_MAX_NAME_SIZE=80]
# struct input_id id (bustype=2, vendor=2, product=2, version=2 = 8 bytes)
# __u32 ff_effects_max (4 bytes)
# __s32 absmax[ABS_CNT=64]
# __s32 absmin[ABS_CNT=64]
# __s32 absfuzz[ABS_CNT=64]
# __s32 absflat[ABS_CNT=64]
name = b'virt-touch\x00' + b'\x00' * 70
id_data = struct.pack('HHHH', 0x03, 0x1234, 0x5678, 1) # USB, id
ff = struct.pack('I', 0)

absmax = [0] * 64
absmin = [0] * 64
absfuzz = [0] * 64
absflat = [0] * 64

absmax[ABS_X] = 480
absmax[ABS_Y] = 854

payload = name + id_data + ff + struct.pack('64i', *absmax) + struct.pack('64i', *absmin) + struct.pack('64i', *absfuzz) + struct.pack('64i', *absflat)
os.write(fd, payload)
fcntl.ioctl(fd, UI_DEV_CREATE)
print('uinput device created successfully!')
time.sleep(2)
fcntl.ioctl(fd, UI_DEV_DESTROY)
os.close(fd)
