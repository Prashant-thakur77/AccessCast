import socket
import subprocess
import sys


def test_guard_blocks_dns_connect_udp_and_allows_loopback():
    code = r'''
import socket, json
from accesscast.guard import network as g
g.install()
out = {}
try:
    socket.getaddrinfo("example.com", 80); out["dns"] = "leak"
except socket.gaierror:
    out["dns"] = "blocked"
s = socket.socket()
out["connect_ex"] = s.connect_ex(("93.184.216.34", 80))
u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    u.sendto(b"x", ("8.8.8.8", 53)); out["udp"] = "leak"
except OSError:
    out["udp"] = "blocked"
srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1)
c = socket.socket(); c.connect(("127.0.0.1", srv.getsockname()[1])); out["loopback"] = "ok"
out["count"] = len(g.BLOCKED)
print(json.dumps(out))
'''
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    import json

    out = json.loads(p.stdout.strip().splitlines()[-1])
    assert out == {"dns": "blocked", "connect_ex": 111, "udp": "blocked", "loopback": "ok", "count": 3}
    assert socket.getaddrinfo is not None  # this test process itself is untouched
