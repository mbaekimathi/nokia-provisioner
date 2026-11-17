# Nokia Hotspot Provisioner

Batch-provision Nokia WiFi gateways (G-1425G-E and similar ONT/Beacon models) as
open or password-protected hotspot access points — Django API + React UI.

## Run

Double-click `start.bat`, or manually:

```bat
cd backend   && python manage.py runserver 127.0.0.1:8000
cd frontend  && npm run dev
```

Open http://localhost:5173

## VPS deployment (WireGuard)

The packaged deployment runs Gunicorn + Nginx in Docker. WireGuard runs on the
VPS host, so the normal application code can route to the router LAN unchanged.

1. Configure the LAN-side WireGuard peer. For a Linux gateway on the router
   LAN, adapt `deploy/wireguard/wg0.lan-gateway.conf.example`; it forwards and
   NATs VPS traffic onto the Nokia subnet. The peer must accept the VPS tunnel
   IP and return traffic for the router LAN.
2. On the VPS, adapt `deploy/wireguard/wg0.client.conf.example` into
   `/etc/wireguard/wg0.conf`, set the keys/endpoint, and include the router LAN
   in `AllowedIPs` — for example `192.168.1.0/24` for `192.168.1.254` units:

   ```bash
   sudo install -m 600 deploy/wireguard/wg0.client.conf.example /etc/wireguard/wg0.conf
   sudoedit /etc/wireguard/wg0.conf
   sudo systemctl enable --now wg-quick@wg0
   ping -c1 192.168.1.254
   ```

3. Configure and start the app:

   ```bash
   cp .env.example .env
   # set DJANGO_SECRET_KEY and DJANGO_ALLOWED_HOSTS
   docker compose up -d --build
   ```

4. Open the UI and create the first account. New signups are pending; activate
   that account from the VPS, replacing `123456` with its 6-digit code:

   ```bash
   docker compose exec backend python manage.py shell -c "from provisioner.models import Employee; e=Employee.objects.get(code='123456'); e.status='active'; e.role='admin'; e.save(update_fields=['status','role'])"
   ```

   The UI binds to `127.0.0.1:8080` by default. Open it through SSH:

   ```bash
   ssh -L 8080:127.0.0.1:8080 user@vps
   ```

   Then visit http://localhost:8080. If browsers can reach the VPS through the
   WireGuard network instead, set `APP_BIND` to the VPS tunnel IP and add that
   IP to `DJANGO_ALLOWED_HOSTS`. Do not bind `0.0.0.0` publicly without adding
   server-side authorization — the login screen does not protect the API.

   On Linux, the subnet picker cannot auto-detect local subnets because it uses
   Windows `ipconfig`; enter the remote router subnet explicitly (for example
   `192.168.1`) or paste router IPs. The one-router auto flow still probes the
   built-in defaults such as `192.168.1.254`.

## Use

1. Connect the router's LAN port to this PC (or a reachable network).
2. Enter router IP (default `192.168.1.254`), `userAdmin` + the label password,
   the new SSID, optional WiFi password (blank = open network).
3. "Provision router" — it logs in via the router's encrypted CGI API, sets the
   SSID on 2.4/5 GHz, then switches the unit to bridge/AP mode (reboots; it
   picks up a new IP from your upstream router).
4. Track every unit in the list — success / failed tallies at the top,
   per-router live log expandable.

- **Scan subnet**: sweeps a /24 (or all local subnets) for Nokia gateways
  answering the login CGI.
- **Batch setup**: scan-found gateways or a pasted `IP,label password` list can
  be provisioned in one click — up to 32 units run in parallel, the rest queue
  as "pending". Each router needs its own IP (factory units all share
  `192.168.1.254`, so batch them once they're on the upstream network).
- **Retry** re-runs a failed router; **Delete** removes it.

## Notes / limits

- Requires the device's printed credentials (`userAdmin` + label password).
  The separate `admin` account is not needed — WiFi + work-mode endpoints are
  authorized for `userAdmin`. LAN/DHCP writes are NOT (ISP-locked) — that's why
  the system uses bridge mode instead of touching DHCP directly.
- LAN/DHCP-server toggle alone cannot be done via `userAdmin` on this firmware.
- Bridge mode makes the unit reboot; provision it while it is still at its
  factory IP, then it reappears on the upstream network.

## Layout

- `backend/`  — Django app (`provisioner/client.py` = crypto+API port)
- `frontend/` — Vite + React UI (dark, responsive)
- `deploy/`   — Docker, Nginx, and WireGuard deployment assets
- `C:\tmp\router_*.js` — original proof-of-concept Node scripts
