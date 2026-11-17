"""
Nokia WiFi gateway (G-1425G-E and similar ONT/Beacon family) provisioning client.

Replicates the web-UI login + config protocol:
  - GET /login_web_app.cgi?nonce -> {nonce, randomKey, pubkey}
  - POST /login_web_app.cgi      -> body `encrypted=1&ct=..&ck=..`
        inner: userhash=<u>&RandomKeyhash=<rk>&response=<urlenc(p)>&nonce=<esc(nonce)>
               &enckey=<rnd>&enciv=<rnd>&nohash=1&hPassword=undefined
  - Config POSTs: `<params>&csrf_token=<token>` wrapped the same way.

Encryption (crypto_page in the firmware's JS):
  ct = AES-128-CBC(random key, random iv, plaintext) -> base64, then + -> -, / -> _, = -> .
  ck = RSA-PKCS1v15(pubkey, "b64(key) b64(iv)") -> base64, same url-escaping
"""
import base64
import json
import os
import time
import urllib.parse

import requests
import urllib3

from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.serialization import load_pem_public_key

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _esc(s: str) -> str:
    """crypto_page.base64url_escape: + -> -, / -> _, = -> ."""
    return s.replace("+", "-").replace("/", "_").replace("=", ".")


def _b64url_escape_bytes(b: bytes) -> str:
    return _esc(base64.b64encode(b).decode())


class _BadRead(Exception):
    """Device answered but the payload isn't usable yet — web backend mid-restart."""


# bump when the provisioning protocol changes — logged at run start so a
# stale backend process is obvious from the log
CLIENT_REV = 6


class NokiaClient:
    def __init__(self, host, username, password, timeout=20):
        self.host = host
        self.username = username
        self.password = password
        self.base = f"https://{host}"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NokiaProvisioner",
        })
        self.token = None
        self.pubkey = None
        self.nonce = None

    # ---------- crypto ----------
    def _encrypt_post_data(self, plaintext: str) -> str:
        pem = self.pubkey
        if "BEGIN" not in pem:
            pem = ("-----BEGIN PUBLIC KEY-----\n"
                   + "\n".join(pem[i:i + 64] for i in range(0, len(pem), 64))
                   + "\n-----END PUBLIC KEY-----")
        key = load_pem_public_key(pem.encode())

        aes_key, iv = os.urandom(16), os.urandom(16)
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
        enc = cipher.encryptor()
        pad_len = 16 - (len(plaintext.encode()) % 16)
        padded = plaintext.encode() + bytes([pad_len]) * pad_len
        ct = enc.update(padded) + enc.finalize()

        secret = base64.b64encode(aes_key).decode() + " " + base64.b64encode(iv).decode()
        ck = key.encrypt(secret.encode(), rsa_padding.PKCS1v15())

        return f"encrypted=1&ct={_b64url_escape_bytes(ct)}&ck={_b64url_escape_bytes(ck)}"

    # ---------- http helpers ----------
    def _post(self, path, params: str, encrypted=True):
        if self.token:
            body = params + f"&csrf_token={urllib.parse.quote(self.token)}" if params else f"csrf_token={urllib.parse.quote(self.token)}"
        else:
            body = params
        if encrypted:
            body = self._encrypt_post_data(body)
        r = self.session.post(self.base + path, data=body.encode(), timeout=self.timeout)
        r.raise_for_status()
        return r.text

    def _get(self, path):
        r = self.session.get(self.base + path, timeout=self.timeout)
        r.raise_for_status()
        return r.text

    def _json(self, text):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"_raw": text}

    # ---------- api ----------
    def login(self):
        # fresh jar each attempt — a failed login can leave a session cookie
        # that the device rejects on POST ("invalid parameter in the coookie")
        self.session.cookies.clear()
        n = self._json(self._get("/login_web_app.cgi?nonce"))
        self.nonce, self.pubkey = n["nonce"], n["pubkey"]
        inner = (
            f"userhash={urllib.parse.quote(self.username)}"
            f"&RandomKeyhash={urllib.parse.quote(n.get('randomKey', ''))}"
            f"&response={urllib.parse.quote(self.password)}"
            f"&nonce={_esc(self.nonce)}"
            f"&enckey={_b64url_escape_bytes(os.urandom(16))}"
            f"&enciv={_b64url_escape_bytes(os.urandom(16))}"
            "&nohash=1&hPassword=undefined"
        )
        r = self.session.post(
            self.base + "/login_web_app.cgi",
            data=self._encrypt_post_data(inner).encode(), timeout=self.timeout)
        res = self._json(r.text)
        if res.get("result") != 0:
            raise RuntimeError(f"login failed: {res}")
        self.token = res["token"]
        return res

    def get_json(self, path):
        return self._json(self._get(path))

    def _call_retry(self, fn, tries=8, delay=4.0, log=lambda m: None):
        """Retry reads/writes that race the web backend restarting.

        After a config POST the device drops connections for several seconds
        while it reinitializes — retry instead of failing the whole run.
        Junk-but-200 replies (login page, empty JSON) count as transient too,
        and midway through we re-login in case the restart killed the session."""
        last = None
        for i in range(tries):
            try:
                return fn()
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout) as e:
                last = e
                if i < tries - 1:
                    log(f"connection dropped, retrying ({i + 1}/{tries}) ...")
                    time.sleep(delay)
            except _BadRead as e:
                last = e
                if i >= 1:
                    # junk replies also mean a dead session — cheap to re-login
                    try:
                        self.login()
                        log("re-logged in (session likely dropped on restart)")
                    except Exception:
                        pass
                if i < tries - 1:
                    log(f"router not ready ({e}), retrying ({i + 1}/{tries}) ...")
                    time.sleep(delay)
        raise last

    # ---------- provisioning steps ----------
    def get_work_mode(self):
        return self.get_json("/whw_beacon_mode_app_status_web_app.cgi?getWorkMode")

    def set_bridge_mode(self, enable=True):
        return self._post("/whw_beacon_mode_app_web_app.cgi",
                          f"act=setWorkMode&brEnable={1 if enable else 0}")

    def get_wlan_24(self):
        return self._wlan_status("/wlan_config_status_web_app.cgi")

    def get_wlan_5(self, allow_empty=True):
        # empty list is legitimate for a fetch — single-band units report no
        # 5G SSID. During verify pass allow_empty=False: we know 5G exists,
        # so an empty reply is the backend mid-restart.
        return self._wlan_status("/wlan_config_status_web_app.cgi?v=11ac",
                                 allow_empty=allow_empty)

    def _wlan_status(self, path, allow_empty=False):
        """GET a wlan status CGI. The web backend answers 200 with a login
        page / error JSON / missing keys while it restarts — that's a
        _BadRead, not a real status."""
        d = self.get_json(path)
        if "_raw" in d:
            raise _BadRead(f"bad status reply: {str(d)[:140]}")
        # firmwares rename the entry list — wlan_config_glb, glb11ac, etc —
        # so collect per-SSID dicts from every wlan_config* key. Some builds
        # also prepend a radio/global dict with no SSID key; drop those.
        entries = []
        for k, v in d.items():
            if k.startswith("wlan_config"):
                if isinstance(v, dict):
                    v = [v]
                if isinstance(v, list):
                    entries += [e for e in v if isinstance(e, dict) and "SSID" in e]
        if not entries and not allow_empty:
            raise _BadRead(f"status reply has no SSID entries: {str(d)[:300]}")
        d["wlan_config_glb"] = entries
        return d

    def _ssid_params(self, cfg, band):
        """Current config dict for primary SSID of a band. Radio params may
        live at the response top level, so merge those in under the entry."""
        entries = cfg.get("wlan_config_glb", [])
        if not entries:
            return {}
        base = {k: v for k, v in cfg.items() if not isinstance(v, (dict, list))}
        return {**base, **entries[0]}

    def _wlan_body_24(self, c, ssid, open_wifi=True):
        """do_config_glb body for the 2.4GHz primary SSID."""
        acct = (c.get("Accounting_2Ghz") or [{}])[0]
        encmode = "None" if open_wifi else "Private"
        q = urllib.parse.quote
        b = (
            f"wl_mode={c.get('Standard', 'b,g,n')}"
            f"&wl_ofdma={c.get('X_ASB_COM_OfdmaEnable', 0)}"
            f"&wl_NChannelwidth={c.get('X_CT_COM_ChannelWidth', 0)}"
            f"&wl_channel={c.get('Channel', 'auto' if c.get('AutoChannelEnable') else 6)}"
            f"&wl_power={c.get('TransmitPower', 100)}"
            f"&wl_wmm={c.get('WMMEnable', 1)}"
            f"&total_max_user={c.get('X_ASB_COM_BaseCfg_GlobalMaxAssoc', 64)}"
            f"&wl_id={c.get('SSID_num', 1)}"
            f"&wl_ssid={q(ssid)}&wl_ssidname={q(ssid)}"
            f"&wl_en={c.get('Enable', 1)}&wl_broad={c.get('SSIDAdvertisementEnabled', 1)}"
            f"&port_mode={c.get('X_ASB_COM_routeMode', 2)}&isReboot=0"
            f"&max_user={c.get('X_ASB_COM_VirtualIfCfg_MaxAssoc', 64)}"
            f"&wl_encryptmode={encmode}&wl_weptype={c.get('BasicEncryptionModes', 'None')}"
            f"&wepKeyBit={c.get('WEPEncryptionLevel', '40-bit')}"
            f"&wepKey1={q((c.get('wepKeys') or [''])[0])}"
            f"&wpaenc={c.get('WPAEncryptionModes', 'AESEncryption')}"
            f"&radius_ser={c.get('radiusServerIp', '0.0.0.0')}&radius_port={c.get('radiusPort', 1812)}"
            f"&radius_pwd={c.get('radiusPassword', '')}"
            f"&radius_ser2={c.get('X_ASB_COM_radiusServerIp2', '0.0.0.0')}"
            f"&radius_port2={c.get('X_ASB_COM_radiusPort2', 1812)}"
            f"&radius_pwd2={c.get('X_ASB_COM_radiusPassword2', '')}"
            f"&account_port={acct.get('ServerPort', 1813)}&account_key={acct.get('Secret', '')}"
            f"&account_time={acct.get('InterimInterval', 0)}"
            f"&wl_wps={c.get('WPSEnable', 0)}&wl_wpsmode={c.get('WPSMode', 'pbc')}"
            f"&wl_pin=&wl_wpaver={c.get('BeaconType', '11i')}"
        )
        if c.get("Enable", 1):
            b += "&wl_enable=on"
        if not open_wifi:
            b += f"&wpaKey={q(c.get('_wpa_key', '12345678'))}"
        b += "&dnName=dfault&newDomain=&wanList=-2&nofIP=24"
        return b

    def _wlan_body_5(self, c, ssid, open_wifi=True):
        """do_config_glb11ac body for the 5GHz primary SSID."""
        acct = c.get("Accounting_5Ghz") or {}
        encmode = "None" if open_wifi else "Private2"
        q = urllib.parse.quote
        b = (
            f"wl_bandwidth={c.get('X_CT_COM_ChannelWidth', 2)}"
            f"&wl_ofdma={c.get('X_ASB_COM_OfdmaEnable', 0)}"
            f"&wl_channel={c.get('Channel', 'auto' if c.get('AutoChannelEnable') else 36)}"
            f"&wl_power={c.get('TransmitPower', 100)}"
            f"&wl_wmm={c.get('WMMEnable', 1)}&wl_mimo={c.get('X_ASB_COM_MuMimoEnable', 0)}"
            f"&total_max_user={c.get('X_ASB_COM_BaseCfg_GlobalMaxAssoc', 64)}"
            f"&wl_id={c.get('SSID_num', 5)}"
            f"&wl_ssid={q(ssid)}&wl_ssidname={q(ssid)}"
            f"&wl_en={c.get('Enable', 1)}&wl_broad={c.get('SSIDAdvertisementEnabled', 1)}"
            f"&port_mode={c.get('X_ASB_COM_routeMode', 2)}&isReboot=0"
            f"&max_user={c.get('X_ASB_COM_VirtualIfCfg_MaxAssoc', 64)}"
            f"&wl_encryptmode={encmode}&wl_weptype={c.get('BasicEncryptionModes', 'None')}"
            f"&wepKeyBit={c.get('WEPEncryptionLevel', '40-bit')}"
            f"&wepKey1={q((c.get('wepKeys') or [''])[0])}"
            f"&radius_ser={c.get('radiusServerIp', '0.0.0.0')}&radius_port={c.get('radiusPort', 1812)}"
            f"&radius_pwd={c.get('radiusPassword', '')}"
            f"&radius_ser2={c.get('X_ASB_COM_radiusServerIp2', '0.0.0.0')}"
            f"&radius_port2={c.get('X_ASB_COM_radiusPort2', 1812)}"
            f"&radius_pwd2={c.get('X_ASB_COM_radiusPassword2', '')}"
            f"&account_port={acct.get('ServerPort', 1813)}&account_key={acct.get('Secret', '')}"
            f"&account_time={acct.get('InterimInterval', 0)}"
            f"&wl_wps={c.get('WPSEnable', 0)}&wl_wpsmode={c.get('WPSMode', 'pbc')}"
            f"&wl_pin=&wl_wpaver={c.get('BeaconType', '11i')}"
            f"&wpaenc={c.get('WPAEncryptionModes', 'AESEncryption')}"
        )
        if c.get("Enable", 1):
            b += "&wl_enable=on"
        if not open_wifi:
            b += f"&wpaKey={q(c.get('_wpa_key', '12345678'))}"
        b += "&dnName=dfault&newDomain=&wanList=-2&nofIP=24"
        return b

    def set_ssid_24(self, c, ssid, open_wifi=True):
        r = self._json(self._post("/wlan_config_web_app.cgi?do_config_glb",
                                  self._wlan_body_24(c, ssid, open_wifi)))
        if "_raw" in r:
            raise _BadRead(f"non-JSON reply to 2.4G write: {r['_raw'][:120]}")
        return r

    def set_ssid_5(self, c, ssid, open_wifi=True):
        r = self._json(self._post("/wlan_config_web_app.cgi?do_config_glb11ac",
                                  self._wlan_body_5(c, ssid, open_wifi)))
        if "_raw" in r:
            raise _BadRead(f"non-JSON reply to 5G write: {r['_raw'][:120]}")
        return r

    def provision(self, ssid, ssid_5="", wifi_password="", bridge=True, band24=True, band5=True,
                  log=lambda m: None, already_logged_in=False):
        """Full flow. WiFi first (while reachable), bridge mode last. Returns summary dict."""
        open_wifi = not wifi_password
        ssid_5 = ssid_5 or ssid
        log(f"client rev {CLIENT_REV}")
        if not already_logged_in:
            log("login")
            self.login()
            log("login ok")

        mode = self.get_work_mode()
        log(f"workMode={mode.get('workMode')}")

        # each band: write then verify right away. The verify read rides out
        # the post-write bounce, so the next band's config read lands on a
        # backend that's confirmed healthy — an empty 5G reply then really
        # means "no 5G", not "still restarting".
        results = {"verify": {}}
        if band24:
            c = self._ssid_params(self._call_retry(self.get_wlan_24, log=log), "24")
            c["_wpa_key"] = wifi_password
            r = self._call_retry(lambda: self.set_ssid_24(c, ssid, open_wifi), log=log)
            results["band24"] = r
            log(f"2.4G set: {r}")
            if r.get("result") != 0:
                raise RuntimeError(f"2.4G config rejected: {r}")
            got = self._call_retry(self.get_wlan_24, log=log)["wlan_config_glb"][0]
            ok_ssid = got.get("SSID") == ssid
            ok_open = got.get("BeaconType") == "None" if open_wifi else True
            results["verify"].update({"ssid_24": got.get("SSID"), "beacon": got.get("BeaconType")})
            log(f"verify 2.4G ssid={got.get('SSID')} beacon={got.get('BeaconType')}")
            if not (ok_ssid and ok_open):
                raise RuntimeError(f"verify 2.4G failed: {results['verify']} entry={str(got)[:160]}")

        if band5:
            c5 = self._ssid_params(self._call_retry(self.get_wlan_5, log=log), "5")
            if c5:
                c5["_wpa_key"] = wifi_password
                r = self._call_retry(lambda: self.set_ssid_5(c5, ssid_5, open_wifi), log=log)
                results["band5"] = r
                log(f"5G set: {r}")
                if r.get("result") != 0:
                    raise RuntimeError(f"5G config rejected: {r}")
                got5 = self._call_retry(lambda: self.get_wlan_5(allow_empty=False),
                                        log=log)["wlan_config_glb"][0]
                ok5 = got5.get("SSID") == ssid_5
                results["verify"]["ssid_5"] = got5.get("SSID")
                log(f"verify 5G ssid={got5.get('SSID')}")
                if not ok5:
                    raise RuntimeError(f"verify 5G failed: expected {ssid_5!r} got {got5.get('SSID')!r}")
            else:
                log("no 5G SSID found (single-band unit or radio off), skipped")

        if bridge:
            # let the web backend settle after the last config write — its
            # restart window can outlive a fast retry loop
            time.sleep(6)

            def _bridge():
                r = self._json(self.set_bridge_mode(True))
                if "_raw" in r:
                    raise _BadRead(f"non-JSON reply to bridge write: {r['_raw'][:120]}")
                return r
            try:
                results["bridge"] = self._call_retry(_bridge, log=log)
                log(f"bridge mode set: {results['bridge']} (device will reboot)")
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                log("connection dropped during bridge switch — device is likely rebooting into AP mode")
            except _BadRead as e:
                results["bridge"] = {"error": str(e)}
                log(f"bridge switch not confirmed ({e}) — check AP mode manually")

        return results
