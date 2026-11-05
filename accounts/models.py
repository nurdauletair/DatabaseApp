from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    phone = models.CharField("Телефон", max_length=20, blank=True)

    @property
    def role(self):
        if self.is_superuser:
            return "admin"
        names = set(self.groups.values_list("name", flat=True))
        return next((name for name in ("registrar", "doctor", "patient") if name in names), "—")

    @property
    def role_label(self):
        return {"admin": "Әкімші", "registrar": "Тіркеуші", "doctor": "Дәрігер",
                "patient": "Науқас"}.get(self.role, "Рөл тағайындалмаған")
