#!/bin/sh
export PATH=/sbin:/bin:/usr/sbin:/usr/bin

/bin/busybox mount -t proc proc /proc 2>/dev/null
/bin/busybox mount -t sysfs sysfs /sys 2>/dev/null
/bin/busybox mount -t tmpfs -o mode=0755 tmpfs /dev 2>/dev/null

/bin/busybox mkdir -p /dev/pts /dev/shm /dev/graphics /dev/input /dev/block
/bin/busybox mount -t devpts -o gid=5,mode=0620 devpts /dev/pts 2>/dev/null
/bin/busybox mount -t tmpfs tmpfs /dev/shm 2>/dev/null

[ -e /dev/console ] || /bin/busybox mknod -m 600 /dev/console c 5 1
[ -e /dev/null ]    || /bin/busybox mknod -m 666 /dev/null c 1 3
[ -e /dev/zero ]    || /bin/busybox mknod -m 666 /dev/zero c 1 5
[ -e /dev/kmsg ]    || /bin/busybox mknod -m 666 /dev/kmsg c 1 11
[ -e /dev/tty ]     || /bin/busybox mknod -m 666 /dev/tty c 5 0
[ -e /dev/tty0 ]    || /bin/busybox mknod -m 660 /dev/tty0 c 4 0
[ -e /dev/tty1 ]    || /bin/busybox mknod -m 660 /dev/tty1 c 4 1
[ -e /dev/ptmx ]    || /bin/busybox mknod -m 666 /dev/ptmx c 5 2
[ -e /dev/uinput ]  || /bin/busybox mknod -m 666 /dev/uinput c 10 223
[ -e /dev/fb0 ]     || /bin/busybox mknod -m 660 /dev/fb0 c 29 0
[ -e /dev/graphics/fb0 ] || /bin/busybox mknod -m 660 /dev/graphics/fb0 c 29 0

[ -e /proc/wdk ] && echo "0 20 30" > /proc/wdk 2>/dev/null
[ -e /proc/bootprof ] && echo "INIT:Mount_START" > /proc/bootprof 2>/dev/null
[ -e /proc/bootprof ] && echo "INIT:Mount_END" > /proc/bootprof 2>/dev/null
[ -e /proc/bootprof ] && echo "0" > /proc/bootprof 2>/dev/null

/bin/busybox mdev -s 2>/dev/null

USB=/sys/class/android_usb/android0
if [ -d "$USB" ]; then
    echo 0 > "$USB/enable" 2>/dev/null
    echo 17EF > "$USB/idVendor" 2>/dev/null
    echo 2004 > "$USB/idProduct" 2>/dev/null
    echo "Lenovo" > "$USB/f_rndis/manufacturer" 2>/dev/null
    echo "17EF" > "$USB/f_rndis/vendorID" 2>/dev/null
    echo "1" > "$USB/f_rndis/wceis" 2>/dev/null
    echo rndis > "$USB/functions" 2>/dev/null
    echo 1 > "$USB/enable" 2>/dev/null
fi
/bin/busybox ip link set lo up 2>/dev/null
/bin/busybox ip link set rndis0 up 2>/dev/null
/bin/busybox ip addr add 10.42.0.2/24 dev rndis0 2>/dev/null
/bin/busybox ip addr add 192.168.42.129/24 dev rndis0 2>/dev/null

i=0
while [ $i -lt 50 ]; do
    /bin/busybox mdev -s 2>/dev/null
    if [ ! -b /dev/mmcblk0p22 ] && [ -f /sys/class/block/mmcblk0p22/dev ]; then
        DEVNUM=$(/bin/busybox cat /sys/class/block/mmcblk0p22/dev 2>/dev/null)
        MAJ=${DEVNUM%:*}
        MIN=${DEVNUM#*:}
        if [ -n "$MAJ" ] && [ -n "$MIN" ]; then
            /bin/busybox mknod /dev/mmcblk0p22 b "$MAJ" "$MIN" 2>/dev/null
        fi
    fi
    if [ -b /dev/mmcblk0p22 ]; then
        break
    fi
    /bin/busybox sleep 0.2
    i=$((i + 1))
done

/bin/busybox mkdir -p /newroot
if /bin/busybox mount -t ext4 -o rw,noatime /dev/mmcblk0p22 /newroot 2>/dev/null; then
    /bin/busybox mkdir -p /newroot/var/log /newroot/proc /newroot/sys /newroot/dev /newroot/run /newroot/tmp
    {
        echo "=== Early Initramfs Boot Log ==="
        /bin/busybox date
        echo "cmdline: $(/bin/busybox cat /proc/cmdline)"
        /bin/busybox ls -la /dev/mmcblk0*
        /bin/busybox mount
    } > /newroot/var/log/early_initramfs.log 2>&1
    /bin/busybox sync

    /bin/busybox mount -o move /proc /newroot/proc 2>/dev/null
    /bin/busybox mount -o move /sys /newroot/sys 2>/dev/null
    /bin/busybox mount -o move /dev /newroot/dev 2>/dev/null

    exec </newroot/dev/console >/newroot/dev/console 2>&1

    /bin/busybox chroot /newroot /bin/sh -c '
        export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
        export HOME=/root
        [ -e /proc/wdk ] && echo "0 20 30" > /proc/wdk 2>/dev/null
        /bin/busybox mount -a 2>/dev/null
        /bin/busybox mkdir -p /dev/pts /dev/shm /dev/graphics /dev/input /run/sshd /var/empty /tmp
        /bin/busybox chmod 1777 /tmp /dev/shm 2>/dev/null
        /bin/busybox mdev -s 2>/dev/null
        [ -e /dev/uinput ] || /bin/busybox mknod -m 666 /dev/uinput c 10 223 2>/dev/null
        [ -e /dev/fb0 ] || /bin/busybox mknod -m 660 /dev/fb0 c 29 0 2>/dev/null
        [ -e /dev/graphics/fb0 ] || /bin/busybox mknod -m 660 /dev/graphics/fb0 c 29 0 2>/dev/null
        /bin/sh /usr/local/bin/usbnet-daemon >/var/log/usbnet.log 2>&1 &
        /usr/sbin/sshd -E /var/log/sshd.log 2>/dev/null
        /bin/busybox telnetd -l /bin/sh -p 2323 2>/dev/null &
        /bin/busybox sleep 3
        if ! /bin/busybox pidof Xorg >/dev/null 2>&1; then
            /bin/sh /usr/local/bin/phone-desktop >/var/log/phone_desktop.log 2>&1 &
            /usr/bin/python3 /usr/local/bin/hw_keys_daemon.py >/var/log/hw_keys.log 2>&1 &
        fi
        while true; do
            [ -e /proc/wdk ] && echo "0 20 30" > /proc/wdk 2>/dev/null
            /bin/busybox sleep 10
        done
    ' </newroot/dev/null >/newroot/dev/null 2>&1 &

    exec /bin/busybox switch_root /newroot /sbin/init
fi

/bin/busybox telnetd -l /bin/sh -p 23 2>/dev/null &
while true; do
    [ -e /proc/wdk ] && echo "0 20 30" > /proc/wdk 2>/dev/null
    /bin/busybox ip link set rndis0 up 2>/dev/null
    /bin/busybox ip addr add 10.42.0.2/24 dev rndis0 2>/dev/null
    /bin/busybox sleep 2
done
