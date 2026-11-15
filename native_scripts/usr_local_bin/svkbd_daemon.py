#!/usr/bin/env python3
import subprocess, os, signal, sys

os.environ['DISPLAY'] = ':0'
p = subprocess.Popen(
    ['/usr/bin/svkbd-mobile-intl', '-d', '-g', '480x260+0+546'],
    stdin=subprocess.PIPE,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)

def cleanup(sig, frame):
    try:
        p.terminate()
    except Exception:
        pass
    sys.exit(0)

signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)

p.wait()
