from django.db import models


class Router(models.Model):
    STATUS = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    ip = models.GenericIPAddressField()
    username = models.CharField(max_length=64, default="userAdmin")
    password = models.CharField(max_length=128)
    ssid = models.CharField(max_length=64)
    ssid_5 = models.CharField(max_length=64, blank=True, default="")
    wifi_password = models.CharField(max_length=128, blank=True, default="")
    bridge_mode = models.BooleanField(default=True)
    band_24 = models.BooleanField(default=True)
    band_5 = models.BooleanField(default=True)

    status = models.CharField(max_length=16, choices=STATUS, default="pending")
    log = models.TextField(blank=True, default="")
    error = models.CharField(max_length=512, blank=True, default="")
    detected_model = models.CharField(max_length=64, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def to_dict(self, with_log=False):
        d = {
            "id": self.id,
            "ip": self.ip,
            "username": self.username,
            "ssid": self.ssid,
            "ssid_5": self.ssid_5,
            "bridge_mode": self.bridge_mode,
            "status": self.status,
            "error": self.error,
            "detected_model": self.detected_model,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if with_log:
            d["log"] = self.log
        return d


class Employee(models.Model):
    STATUS = [
        ("pending_activation", "Pending activation"),
        ("active", "Active"),
        ("suspended", "Suspended"),
    ]
    ROLE = [
        ("admin", "Admin"),
        ("cashier", "Cashier"),
        ("employee", "Employee"),
    ]

    first_name = models.CharField(max_length=64)
    last_name = models.CharField(max_length=64)
    email = models.EmailField(unique=True)
    code = models.CharField(max_length=6, unique=True)
    password = models.CharField(max_length=128)
    status = models.CharField(max_length=20, choices=STATUS, default="pending_activation")
    role = models.CharField(max_length=16, choices=ROLE, default="employee")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    def to_dict(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "code": self.code,
            "status": self.status,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
        }


class Setting(models.Model):
    key = models.CharField(max_length=64, unique=True)
    value = models.TextField(blank=True, default="")

    @classmethod
    def get(cls, key, default=""):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set(cls, key, value):
        cls.objects.update_or_create(key=key, defaults={"value": value})
