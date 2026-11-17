import json

from django.contrib.auth.hashers import check_password, make_password
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .discovery import CANDIDATE_IPS, local_subnets, probe
from .models import Employee, Router, Setting
from .worker import start_provision


def _body(request):
    try:
        return json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return {}


@csrf_exempt
@require_http_methods(["POST"])
def signup(request):
    """Create an account: two names, email, 6-digit code, password + confirm.
    New accounts start pending_activation with the employee role."""
    data = _body(request)
    first = (data.get("first_name") or "").strip()
    last = (data.get("last_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    code = (data.get("code") or "").strip()
    password = data.get("password") or ""
    confirm = data.get("confirm_password") or ""

    if not first or not last:
        return JsonResponse({"error": "first and last name are required"}, status=400)
    if not email or "@" not in email:
        return JsonResponse({"error": "a valid email is required"}, status=400)
    if len(code) != 6 or not code.isdigit():
        return JsonResponse({"error": "code must be exactly 6 digits"}, status=400)
    if not password:
        return JsonResponse({"error": "password is required"}, status=400)
    if password != confirm:
        return JsonResponse({"error": "passwords do not match"}, status=400)
    if Employee.objects.filter(email=email).exists():
        return JsonResponse({"error": "an account with that email already exists"}, status=409)
    if Employee.objects.filter(code=code).exists():
        return JsonResponse({"error": "that code is already in use"}, status=409)

    e = Employee.objects.create(
        first_name=first,
        last_name=last,
        email=email,
        code=code,
        password=make_password(password),
    )
    return JsonResponse({"employee": e.to_dict()}, status=201)


@csrf_exempt
@require_http_methods(["POST"])
def login(request):
    """Log in with the 6-digit code and password."""
    data = _body(request)
    code = (data.get("code") or "").strip()
    password = data.get("password") or ""
    try:
        e = Employee.objects.get(code=code)
    except Employee.DoesNotExist:
        return JsonResponse({"error": "invalid code or password"}, status=401)
    if not check_password(password, e.password):
        return JsonResponse({"error": "invalid code or password"}, status=401)
    if e.status == "pending_activation":
        return JsonResponse({"error": "account is pending activation"}, status=403)
    if e.status == "suspended":
        return JsonResponse({"error": "account is suspended"}, status=403)
    return JsonResponse({"employee": e.to_dict()})


@require_http_methods(["GET"])
def employees(request):
    return JsonResponse({"employees": [e.to_dict() for e in Employee.objects.all()]})


@csrf_exempt
@require_http_methods(["PATCH", "POST"])
def employee_detail(request, pk):
    try:
        e = Employee.objects.get(pk=pk)
    except Employee.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)
    data = _body(request)
    changed = []
    for field in ("first_name", "last_name"):
        if field in data:
            value = (data.get(field) or "").strip()
            if not value:
                return JsonResponse({"error": f"{field.replace('_', ' ')} cannot be blank"}, status=400)
            setattr(e, field, value)
            changed.append(field)
    if "email" in data:
        email = (data.get("email") or "").strip().lower()
        if not email or "@" not in email:
            return JsonResponse({"error": "a valid email is required"}, status=400)
        if Employee.objects.filter(email=email).exclude(pk=pk).exists():
            return JsonResponse({"error": "an account with that email already exists"}, status=409)
        e.email = email
        changed.append("email")
    if "code" in data:
        code = (data.get("code") or "").strip()
        if len(code) != 6 or not code.isdigit():
            return JsonResponse({"error": "code must be exactly 6 digits"}, status=400)
        if Employee.objects.filter(code=code).exclude(pk=pk).exists():
            return JsonResponse({"error": "that code is already in use"}, status=409)
        e.code = code
        changed.append("code")
    if data.get("password"):
        e.password = make_password(data["password"])
        changed.append("password")
    if data.get("status") in dict(Employee.STATUS):
        e.status = data["status"]
        changed.append("status")
    if data.get("role") in dict(Employee.ROLE):
        e.role = data["role"]
        changed.append("role")
    if changed:
        e.save(update_fields=changed + ["updated_at"])
    return JsonResponse({"employee": e.to_dict()})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def routers(request):
    if request.method == "GET":
        return JsonResponse({"routers": [r.to_dict() for r in Router.objects.all()]})

    data = _body(request)
    if isinstance(data, list):
        data = {"routers": data}
    items = data.get("routers") or [data]
    created = []
    seen = set()
    for item in items:
        try:
            ip = item["ip"].strip()
            key = ip.lower()
            if key in seen:
                created.append({"error": f"duplicate ip {ip} in request"})
                continue
            seen.add(key)
            if key != "auto" and Router.objects.filter(
                    ip=ip, status__in=["pending", "running"]).exists():
                created.append({"error": f"{ip} already queued or running"})
                continue
            r = Router.objects.create(
                ip=ip,
                username=(item.get("username") or "userAdmin").strip(),
                password=(item.get("password") or ""),
                ssid=item["ssid"].strip(),
                ssid_5=(item.get("ssid_5") or "").strip(),
                wifi_password=item.get("wifi_password", ""),
                bridge_mode=bool(item.get("bridge_mode", True)),
                band_24=bool(item.get("band_24", True)),
                band_5=bool(item.get("band_5", True)),
            )
            if item.get("auto_provision", True):
                start_provision(r.id)
                r.refresh_from_db()
            created.append(r.to_dict())
        except (KeyError, ValueError) as e:
            created.append({"error": f"invalid entry: {e}"})
    return JsonResponse({"created": created}, status=201)


@csrf_exempt
@require_http_methods(["GET", "DELETE", "POST"])
def router_detail(request, pk):
    try:
        r = Router.objects.get(pk=pk)
    except Router.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(r.to_dict(with_log=True))
    if request.method == "DELETE":
        r.delete()
        return JsonResponse({"deleted": pk})
    # POST = retry/provision (optionally with a corrected label password)
    if r.status == "running":
        return JsonResponse({"error": "already running"}, status=409)
    data = _body(request)
    if data.get("admin_password"):
        r.password = data["admin_password"].strip()
        r.save(update_fields=["password", "updated_at"])
    start_provision(r.id)
    return JsonResponse({"started": pk})


@require_http_methods(["GET"])
def stats(request):
    qs = Router.objects.all()
    return JsonResponse({
        "total": qs.count(),
        "success": qs.filter(status="success").count(),
        "failed": qs.filter(status="failed").count(),
        "running": qs.filter(status="running").count(),
        "pending": qs.filter(status="pending").count(),
    })


@csrf_exempt
@require_http_methods(["POST"])
def auto(request):
    """One-shot: user only gives SSID (+optional wifi password).
    System discovers the router, tries stored credentials, provisions."""
    data = _body(request)
    ssid = (data.get("ssid") or "").strip()
    if not ssid:
        return JsonResponse({"error": "ssid is required"}, status=400)
    r = Router.objects.create(
        ip=(data.get("ip") or "auto").strip(),
        username=(data.get("username") or Setting.get("default_username", "userAdmin")).strip(),
        password=(data.get("admin_password") or "").strip(),
        ssid=ssid,
        ssid_5=(data.get("ssid_5") or "").strip(),
        wifi_password=data.get("wifi_password", ""),
        bridge_mode=True,
        band_24=True,
        band_5=True,
    )
    start_provision(r.id)
    return JsonResponse({"created": r.to_dict()}, status=201)


@csrf_exempt
@require_http_methods(["GET", "POST", "PUT"])
def settings_view(request):
    if request.method == "GET":
        try:
            pwds = json.loads(Setting.get("admin_passwords", "[]"))
        except json.JSONDecodeError:
            pwds = []
        return JsonResponse({
            "admin_passwords": pwds,
            "default_username": Setting.get("default_username", "userAdmin"),
        })
    data = _body(request)
    if "admin_passwords" in data:
        Setting.set("admin_passwords", json.dumps([str(p) for p in data["admin_passwords"] if p]))
    if "default_username" in data:
        Setting.set("default_username", str(data["default_username"]))
    return JsonResponse({"saved": True})


@require_http_methods(["GET"])
def subnets(request):
    """/24 prefixes of this machine's IPv4 addresses — for the scan picker."""
    return JsonResponse({"subnets": local_subnets()})


@csrf_exempt
@require_http_methods(["POST"])
def scan(request):
    """Sweep a /24 — or every local subnet plus well-known IPs when the subnet
    is blank/"auto" — for devices answering the Nokia login CGI."""
    data = _body(request)
    subnet = (data.get("subnet") or "").strip()
    if subnet and subnet.lower() != "auto":
        if subnet.count(".") != 2 or not all(
                p.isdigit() and int(p) < 256 for p in subnet.split(".")):
            return JsonResponse({"error": "subnet must be like 192.168.0"}, status=400)
        subnets = [subnet]
    else:
        subnets = local_subnets()
        if not subnets:
            return JsonResponse(
                {"error": "no local networks detected — enter a subnet like 192.168.0"},
                status=400)

    import concurrent.futures

    targets = set(CANDIDATE_IPS)
    for s in subnets:
        targets.update(f"{s}.{i}" for i in range(1, 255))

    found = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=96) as ex:
        for hit in ex.map(lambda ip: probe(ip, 1.5), targets):
            if hit:
                found.add(hit)
    found = sorted(found, key=lambda ip: tuple(int(p) for p in ip.split(".")))
    return JsonResponse({"found": found})
