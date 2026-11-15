#!/bin/sh
# Toggle screen & touchscreen orientation between Portrait (480x854) and Landscape (854x480)
# Required because xf86-video-fbdev does not support runtime xrandr rotation.

CONF="/etc/X11/xorg.conf"
MODE="$1"

if [ -z "$MODE" ]; then
    if grep -q 'Option "Rotate" "CCW"' "$CONF"; then
        MODE="portrait"
    else
        MODE="landscape"
    fi
fi

if [ "$MODE" = "landscape" ]; then
    cat << 'XORG' > "$CONF"
Section "ServerFlags"
    Option "AutoAddDevices" "false"
    Option "AutoEnableDevices" "false"
    Option "DontVTSwitch" "true"
    Option "AIGLX" "off"
EndSection

Section "Extensions"
    Option "GLX" "Disable"
    Option "AIGLX" "Disable"
EndSection

Section "Device"
    Identifier "Card0"
    Driver "fbdev"
    Option "fbdev" "/dev/fb0"
    Option "Rotate" "CCW"
EndSection

Section "InputDevice"
    Identifier "touchscreen"
    Driver "evdev"
    Option "Device" "/dev/input/touch_pointer"
    Option "CorePointer" "true"
    Option "Calibration" "0 480 0 854"
    Option "TransformationMatrix" "0 -1 1 1 0 0 0 0 1"
    Option "EmulateThirdButton" "true"
    Option "EmulateThirdButtonTimeout" "550"
    Option "EmulateThirdButtonMoveThreshold" "25"
EndSection

Section "InputDevice"
    Identifier "virt_wheel"
    Driver "evdev"
    Option "Device" "/dev/input/virt_wheel"
    Option "SendCoreEvents" "true"
EndSection

Section "InputDevice"
    Identifier "keypad"
    Driver "evdev"
    Option "Device" "/dev/input/event0"
    Option "CoreKeyboard" "true"
EndSection

Section "Screen"
    Identifier "Screen0"
    Device "Card0"
    DefaultDepth 24
    SubSection "Display"
        Depth 24
    EndSubSection
EndSection

Section "ServerLayout"
    Identifier "Layout0"
    Screen "Screen0"
    InputDevice "touchscreen" "CorePointer"
    InputDevice "virt_wheel" "SendCoreEvents"
    InputDevice "keypad" "CoreKeyboard"
EndSection
XORG
else
    cat << 'XORG' > "$CONF"
Section "ServerFlags"
    Option "AutoAddDevices" "false"
    Option "AutoEnableDevices" "false"
    Option "DontVTSwitch" "true"
    Option "AIGLX" "off"
EndSection

Section "Extensions"
    Option "GLX" "Disable"
    Option "AIGLX" "Disable"
EndSection

Section "Device"
    Identifier "Card0"
    Driver "fbdev"
    Option "fbdev" "/dev/fb0"
EndSection

Section "InputDevice"
    Identifier "touchscreen"
    Driver "evdev"
    Option "Device" "/dev/input/touch_pointer"
    Option "CorePointer" "true"
    Option "Calibration" "0 480 0 854"
    Option "EmulateThirdButton" "true"
    Option "EmulateThirdButtonTimeout" "550"
    Option "EmulateThirdButtonMoveThreshold" "25"
EndSection

Section "InputDevice"
    Identifier "virt_wheel"
    Driver "evdev"
    Option "Device" "/dev/input/virt_wheel"
    Option "SendCoreEvents" "true"
EndSection

Section "InputDevice"
    Identifier "keypad"
    Driver "evdev"
    Option "Device" "/dev/input/event0"
    Option "CoreKeyboard" "true"
EndSection

Section "Screen"
    Identifier "Screen0"
    Device "Card0"
    DefaultDepth 24
    SubSection "Display"
        Depth 24
    EndSubSection
EndSection

Section "ServerLayout"
    Identifier "Layout0"
    Screen "Screen0"
    InputDevice "touchscreen" "CorePointer"
    InputDevice "virt_wheel" "SendCoreEvents"
    InputDevice "keypad" "CoreKeyboard"
EndSection
XORG
fi

rc-service cyberdeck restart
