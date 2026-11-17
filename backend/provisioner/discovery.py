"""Auto-discovery: find Nokia gateways on the local network + try stored credentials."""
import concurrent.futures
import re
import subprocess

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CANDIDATE_IPS = [
    "192.168.1.254",   # Nokia WiFi gateway default
    "192.168.18.1",    # Nokia Beacon / bridge-mode fallback
    "192.168.0.1",
    "192.168.1.1",
    "192.168.100.1",
    "10.0.0.1",
]


def probe(ip, timeout=1.5):
    """Return ip if it answers the Nokia login CGI."""
    try:
        r = requests.get(f"https://{ip}/login_web_app.cgi?nonce",
                         verify=False, timeout=timeout)
        if "nonce" in r.text and "pubkey" in r.text:
            return ip
    except Exception:
        pass
    return None


def local_subnets():
    """/24 prefixes of this machine's IPv4 addresses (Windows ipconfig)."""
    subs = set()
    try:
        out = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=10).stdout
        for m in re.finditer(r"IPv4 Address[.\s]*:\s*(\d+)\.(\d+)\.(\d+)\.\d+", out):
            if m.group(1) != "169":  # skip APIPA
                subs.add(".".join(m.groups()[:3]))
    except Exception:
        pass
    return sorted(subs)


def discover(subnets=None, log=lambda m: None):
    """Probe well-known IPs first, then sweep local /24s. Returns ip or None."""
    subs = subnets if subnets is not None else local_subnets()
    targets = set(CANDIDATE_IPS)
    for s in subs:
        targets.update({f"{s}.1", f"{s}.254"})

    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as ex:
        for hit in ex.map(lambda i: probe(i, 2.0), targets):
            if hit:
                log(f"found Nokia gateway at {hit}")
                return hit

    # full /24 sweeps of local subnets
    for s in subs:
        log(f"sweeping {s}.0/24 ...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=96) as ex:
            found = [ip for ip in ex.map(lambda i: probe(f"{s}.{i}", 1.5),
                                         range(1, 255)) if ip]
            if found:
                log(f"found Nokia gateway at {found[0]}")
                return found[0]
    return None
