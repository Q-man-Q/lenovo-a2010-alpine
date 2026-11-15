#!/usr/bin/env python3
"""
Lenovo A2010 Native Alpine — Fast Live Sync over USB RNDIS SSH (root@10.42.0.2)
Pushes all native-adapted scripts, camera stubs/jars, and desktop files to the running phone.
Usage:
    ./deploy_native.sh            # Deploy all scripts without restarting Xorg
    ./deploy_native.sh --restart  # Deploy all scripts and restart phone-desktop
"""
import os
import sys
import pty
import time
import select
import tarfile
import io
import base64

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(BASE_DIR, "native_scripts")

def build_tar_b64():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        # 1. /usr/local/bin/*
        bin_dir = os.path.join(SCRIPTS_DIR, "usr_local_bin")
        for fn in os.listdir(bin_dir):
            full = os.path.join(bin_dir, fn)
            if os.path.isfile(full):
                ti = tf.gettarinfo(full, arcname=f"usr/local/bin/{fn}")
                ti.uid = 0
                ti.gid = 0
                ti.mode = 0o755
                with open(full, "rb") as f:
                    tf.addfile(ti, f)

        # 2. /data/* (camera jars & run_stub_services.sh)
        data_dir = os.path.join(SCRIPTS_DIR, "data")
        for fn in os.listdir(data_dir):
            full = os.path.join(data_dir, fn)
            if os.path.isfile(full):
                ti = tf.gettarinfo(full, arcname=f"data/{fn}")
                ti.uid = 0
                ti.gid = 0
                ti.mode = 0o755 if fn.endswith(".sh") else 0o644
                with open(full, "rb") as f:
                    tf.addfile(ti, f)

        # 3. /usr/local/share/applications/*
        app_dir = os.path.join(SCRIPTS_DIR, "applications")
        for fn in os.listdir(app_dir):
            full = os.path.join(app_dir, fn)
            if os.path.isfile(full):
                ti = tf.gettarinfo(full, arcname=f"usr/local/share/applications/{fn}")
                ti.uid = 0
                ti.gid = 0
                ti.mode = 0o644
                with open(full, "rb") as f:
                    tf.addfile(ti, f)

        # 4. /root/.config/* (tint2, bspwm, rofi, xfce4, gtk-3.0)
        cfg_dir = os.path.join(SCRIPTS_DIR, "configs")
        if os.path.isdir(cfg_dir):
            for root_d, _, files in os.walk(cfg_dir):
                for fn in files:
                    full = os.path.join(root_d, fn)
                    rel = os.path.relpath(full, cfg_dir)
                    ti = tf.gettarinfo(full, arcname=f"root/.config/{rel}")
                    ti.uid = 0
                    ti.gid = 0
                    ti.mode = 0o755 if (fn == "bspwmrc" or fn.endswith(".sh") or "hooks" in root_d or fn == "xinit" or fn == "profile") else 0o644
                    with open(full, "rb") as f:
                        tf.addfile(ti, f)

    return base64.b64encode(buf.getvalue()).decode("ascii")

def run_ssh(remote_cmd, timeout=20):
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp("ssh", [
            "ssh", "-F", "/dev/null",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=5",
            "-o", "PreferredAuthentications=password,keyboard-interactive",
            "root@10.42.0.2", remote_cmd
        ])
    else:
        out = b""
        sent_pw = False
        deadline = time.time() + timeout
        while time.time() < deadline:
            r, _, _ = select.select([fd], [], [], 0.2)
            if fd in r:
                try:
                    data = os.read(fd, 8192)
                    if not data:
                        break
                    out += data
                    if not sent_pw and b"password:" in out.lower():
                        os.write(fd, b"root\n")
                        sent_pw = True
                except OSError:
                    break
        os.close(fd)
        _, status = os.waitpid(pid, 0)
        return os.WEXITSTATUS(status), out.decode("utf-8", errors="replace")

def main():
    restart = "--restart" in sys.argv
    print("[*] Упаковка нативных скриптов и JAR-заглушек камеры...")
    b64_payload = build_tar_b64()
    print(f"[*] Размер архива: {len(b64_payload)} байт (base64). Отправка на root@10.42.0.2...")

    remote_cmd = (
        f"echo '{b64_payload}' | base64 -d | tar -xzf - -C / && "
        "ln -sf /usr/local/bin/android-start /usr/local/bin/start && "
        "ln -sf /usr/local/bin/android-stop /usr/local/bin/stop && "
        "ln -sf /usr/local/bin/sxmo_deviceprofile_lenovo_a2010.sh /usr/bin/sxmo_deviceprofile_lenovo_a2010.sh && "
        "for f in /usr/share/sxmo/default_hooks/*.sh; do ln -sf \"$f\" /usr/bin/\"$(basename \"$f\")\"; done && "
        "find /root/.config/sxmo/ -name '*.needs-migration' -delete 2>/dev/null; "
        "sync && echo 'DEPLOY_OK'"
    )
    if restart:
        remote_cmd += " && (: > /var/log/phone_desktop.log; nohup /usr/local/bin/phone-desktop </dev/null >/var/log/phone_desktop.log 2>&1 & sleep 1; echo 'RESTART_OK')"

    code, out = run_ssh(remote_cmd)
    if "DEPLOY_OK" in out:
        print("[+] Все нативные скрипты и файлы камеры успешно обновлены на телефоне!")
        if restart and "RESTART_OK" in out:
            print("[+] Графическая сессия phone-desktop перезапущена!")
    else:
        print("[-] Не удалось подключиться к 10.42.0.2 (телефон выключен или кабель не подключён).")
        print(out.strip())
        sys.exit(1)

if __name__ == "__main__":
    main()
