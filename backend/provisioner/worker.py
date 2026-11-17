import json
import threading
import traceback
from datetime import datetime

from django.db import connection

from .client import NokiaClient
from .discovery import discover

_running = {}

# cap simultaneous provisioning jobs — extra routers stay "pending" until a
# slot frees, so a large batch can be submitted at once without a network storm
MAX_PARALLEL = 32
_slots = threading.Semaphore(MAX_PARALLEL)


def _stamp(msg):
    return f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"


def provision_router(router_id):
    """Run in a background thread. Django gives each thread its own DB connection."""
    from .models import Router, Setting

    router = Router.objects.get(pk=router_id)
    if _running.get(router_id):
        return
    _running[router_id] = True
    _slots.acquire()
    try:
        router.status = "running"
        router.error = ""
        router.log = ""
        router.save(update_fields=["status", "error", "log", "updated_at"])

        def log(m):
            router.refresh_from_db(fields=["log"])
            router.log = (router.log or "") + _stamp(m) + "\n"
            router.save(update_fields=["log", "updated_at"])

        # --- resolve target IP (auto-discovery when ip is blank/"auto") ---
        ip = router.ip.strip()
        if not ip or ip.lower() == "auto":
            log("auto-discovering router ...")
            found = discover(log=log)
            if not found:
                raise RuntimeError("no Nokia gateway found on the network")
            ip = found
            router.ip = ip
            router.save(update_fields=["ip", "updated_at"])
        log(f"target: {ip}")

        # --- credentials: pasted label password first, then the WiFi
        # password heuristic (label key often = admin pwd), then stored list ---
        candidates = [router.password] if router.password else []
        if router.wifi_password and router.wifi_password not in candidates:
            candidates.append(router.wifi_password)
        try:
            stored = json.loads(Setting.get("admin_passwords", "[]"))
            candidates += [p for p in stored if p and p not in candidates]
        except json.JSONDecodeError:
            pass
        if not candidates:
            candidates = ["admin"]

        client = NokiaClient(ip, router.username, router.password or candidates[0],
                             timeout=15)

        # grab model (needs no auth on some builds, harmless otherwise)
        try:
            info = client.get_json("/main_web_app.cgi")
            router.detected_model = info.get("gwmodel", "")
            if router.detected_model:
                router.save(update_fields=["detected_model", "updated_at"])
                log(f"model: {router.detected_model}")
        except Exception:
            pass

        # --- login, trying candidate passwords ---
        logged = False
        last_err = None
        for pw in candidates[:4]:  # cap attempts to avoid lockout
            client.password = pw
            try:
                client.login()
                logged = True
                if pw != router.password:
                    log("logged in with a stored password")
                break
            except Exception as e:
                last_err = e
                log(f"login attempt failed")
        if not logged:
            raise RuntimeError(f"could not log in (tried {min(len(candidates),4)} passwords): {last_err}")
        log("login ok")

        # bind the credential that actually worked to THIS router, and keep it
        # in the shared list so future units on other stickers can match too
        if pw != router.password:
            router.password = pw
            router.save(update_fields=["password", "updated_at"])
        try:
            stored = json.loads(Setting.get("admin_passwords", "[]"))
            if pw not in stored:
                Setting.set("admin_passwords", json.dumps(stored + [pw]))
        except json.JSONDecodeError:
            pass

        client.provision(
            ssid=router.ssid,
            ssid_5=router.ssid_5,
            wifi_password=router.wifi_password,
            bridge=router.bridge_mode,
            band24=router.band_24,
            band5=router.band_5,
            log=log,
            already_logged_in=True,
        )
        router.status = "success"
        log("done")
    except Exception as e:
        try:
            router.status = "failed"
            router.error = str(e)[:500]
            router.log = (router.log or "") + _stamp(f"ERROR: {e}") + "\n"
            router.save(update_fields=["status", "error", "log", "updated_at"])
        except Exception:
            traceback.print_exc()
    finally:
        router.save()
        _running.pop(router_id, None)
        _slots.release()
        connection.close()


def start_provision(router_id):
    t = threading.Thread(target=provision_router, args=(router_id,), daemon=True)
    t.start()
    return t
