from django.apps import AppConfig


class PerformanceConfig(AppConfig):
    name = "performance"
    verbose_name = "Жүйе күйі"

    def ready(self):
        from . import signals  # noqa: F401
