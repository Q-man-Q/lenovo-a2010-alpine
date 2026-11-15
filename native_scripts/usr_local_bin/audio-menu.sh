#!/bin/sh
CUR=$(cat /tmp/audio_route 2>/dev/null || echo speaker)
CHOICE=$(printf '%s\n'     "Speaker (main)"     "Receiver (earpiece)"     "Headset (3.5mm)"     "Mute"     "Gain: 17Db (max)"     "Gain: 12Db"     "Gain: 8Db"     "Gain: 4Db"     "Test Beep" | dmenu -i -p "Audio [$CUR]:")

case "$CHOICE" in
    "Speaker (main)")
        /usr/local/bin/setup-audio speaker
        dunstify -r 999 "Audio: Speaker" 2>/dev/null || true
        ;;
    "Receiver (earpiece)")
        /usr/local/bin/setup-audio receiver
        dunstify -r 999 "Audio: Receiver" 2>/dev/null || true
        ;;
    "Headset (3.5mm)")
        /usr/local/bin/setup-audio headset
        dunstify -r 999 "Audio: Headset" 2>/dev/null || true
        ;;
    "Mute")
        /usr/local/bin/setup-audio mute
        dunstify -r 999 "Audio: Muted" 2>/dev/null || true
        ;;
    "Gain: 17Db (max)") amixer -c 0 sset Audio_Speaker_PGA_gain 17Db >/dev/null ;;
    "Gain: 12Db") amixer -c 0 sset Audio_Speaker_PGA_gain 12Db >/dev/null ;;
    "Gain: 8Db")  amixer -c 0 sset Audio_Speaker_PGA_gain 8Db >/dev/null ;;
    "Gain: 4Db")  amixer -c 0 sset Audio_Speaker_PGA_gain 4Db >/dev/null ;;
    "Test Beep")
        python3 -c 'import math,struct,wave; w=wave.open("/tmp/beep.wav","w"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000); w.writeframes(b"".join(struct.pack("<hh", int(22000*math.sin(2*math.pi*880*i/48000)), int(22000*math.sin(2*math.pi*880*i/48000))) for i in range(9600))); w.close()' && aplay /tmp/beep.wav && rm -f /tmp/beep.wav
        ;;
esac
