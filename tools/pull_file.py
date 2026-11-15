import pty, os, sys, time, select, base64

remote_path = sys.argv[1]
local_path = sys.argv[2]

cmd = f"base64 {remote_path}"
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

# Strip out ssh headers and prompt
text = raw_out.decode('utf-8', errors='ignore')
lines = text.splitlines()
b64_lines = []
collecting = False
for line in lines:
    clean = line.strip()
    if not clean:
        continue
    if "Warning:" in clean or "password:" in clean.lower() or "Permanently added" in clean:
        collecting = True
        continue
    if collecting:
        # Check if line looks like valid base64
        if all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=" for c in clean):
            b64_lines.append(clean)

data = base64.b64decode("".join(b64_lines))
with open(local_path, "wb") as f:
    f.write(data)
print(f"Successfully pulled {remote_path} to {local_path} ({len(data)} bytes)")
