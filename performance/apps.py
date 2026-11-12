from django.apps import AppConfig


class PerformanceConfig(AppConfig):
    name = "performance"
    verbose_name = "11-ЗС · Өнімділік"

    def ready(self):
        from . import signals  # noqa: F401
