#!/usr/bin/env python3
"""
Runs `apk` commands on the phone (root@10.42.0.2) over an SSH reverse port forward (-R 18080:127.0.0.1:18080)
backed by an in-process HTTP proxy so the phone needs no host NAT/iptables or root permissions.
"""
import http.server
import os
import pty
import select
import socketserver
import sys
import threading
import time
import urllib.request

PROXY_PORT = 18089

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            req = urllib.request.Request(self.path, headers={"User-Agent": "apk-tools"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                self.send_response(resp.status)
                for k, v in resp.getheaders():
                    if k.lower() in ("content-type", "content-length"):
                        self.send_header(k, v)
                self.end_headers()
                self.wfile.write(data)
        except Exception as e:
            self.send_error(502, str(e))

    def log_message(self, format, *args):
        pass

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

def main():
    pkgs = " ".join(sys.argv[1:]) or "sxmo-utils sxmo-utils-dwm sxmo-utils-x11 sxmo-dwm sxmo-dmenu sxmo-st lisgd superd alsa-utils"
def ssh_exec(args, timeout=180):
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp("ssh", [
            "ssh", "-F", "/dev/null",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "PreferredAuthentications=password,keyboard-interactive",
        ] + args)
    else:
        sent_pw = False
        deadline = time.time() + timeout
        while time.time() < deadline:
            r, _, _ = select.select([fd], [], [], 0.2)
            if fd in r:
                try:
                    data = os.read(fd, 4096)
                    if not data:
                        break
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                    if not sent_pw and b"password:" in data.lower():
                        os.write(fd, b"root\n")
                        sent_pw = True
                except OSError:
                    break
        os.close(fd)

def main():
    pkgs = " ".join(sys.argv[1:]) or "sxmo-utils sxmo-utils-dwm sxmo-utils-x11 sxmo-dwm sxmo-dmenu sxmo-st lisgd superd alsa-utils"
    srv = ThreadedHTTPServer(("127.0.0.1", PROXY_PORT), ProxyHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    # Run apk with -R reverse tunnel
    remote_cmd = (
        "sed -i 's|https://|http://|g' /etc/apk/repositories && "
        f"export http_proxy=http://127.0.0.1:{PROXY_PORT} HTTP_PROXY=http://127.0.0.1:{PROXY_PORT} && "
        f"apk update && apk add {pkgs}"
    )
    ssh_exec(["-R", f"{PROXY_PORT}:127.0.0.1:{PROXY_PORT}", "root@10.42.0.2", remote_cmd], timeout=180)
    srv.shutdown()

if __name__ == "__main__":
    main()
