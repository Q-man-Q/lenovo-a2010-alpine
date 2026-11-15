import pty, os, sys, time, select

cmd = sys.argv[1]
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
    out = b""
    sent_pw = False
    deadline = time.time() + 10
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 0.2)
        if fd in r:
            try:
                data = os.read(fd, 4096)
                if not data:
                    break
                out += data
                if not sent_pw and b"password:" in out.lower():
                    os.write(fd, b"root\n")
                    sent_pw = True
            except OSError:
                break
    os.close(fd)
    sys.stdout.buffer.write(out)
