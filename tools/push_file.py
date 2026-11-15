import pty, os, sys, time, select, base64

local_path = sys.argv[1]
remote_path = sys.argv[2]

with open(local_path, "rb") as f:
    b64_data = base64.b64encode(f.read()).decode("ascii")

cmd = f"sh -c 'echo \"{b64_data}\" | base64 -d > {remote_path} && chmod +x {remote_path} && ls -la {remote_path}'"
pid, fd = pty.fork()
if pid == 0:
    os.execvp("ssh", [
        "ssh", "-F", "/dev/null",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "PreferredAuthentications=password,keyboard-interactive",
        "root@10.42.0.2", cmd
    ])
else:
    raw_out = b""
    sent_pw = False
    deadline = time.time() + 15
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 0.2)
        if fd in r:
            try:
                data = os.read(fd, 8192)
                if not data:
                    break
                raw_out += data
                if not sent_pw and b"password:" in raw_out.lower():
                    os.write(fd, b"root\n")
                    sent_pw = True
            except OSError:
                break
    os.close(fd)
    sys.stdout.buffer.write(raw_out)
