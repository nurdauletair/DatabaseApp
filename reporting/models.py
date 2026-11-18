from django.conf import settings
from django.db import models


class QueryLog(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Орындалуда"
        SUCCESS = "success", "Орындалды"
        REJECTED = "rejected", "Қабылданбады"
        ERROR = "error", "Қате"
        UNAVAILABLE = "unavailable", "Қосылмаған"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    question = models.CharField("Сұрақ", max_length=300)
    sql = models.TextField("SQL", blank=True)
    status = models.CharField("Күйі", max_length=16, choices=Status.choices, default=Status.PENDING)
    error = models.CharField("Хабарлама", max_length=300, blank=True)
    model = models.CharField(max_length=100, blank=True)
    prompt_version = models.CharField(max_length=16, default="enhanced")
    row_count = models.PositiveSmallIntegerField(default=0)
    duration_ms = models.PositiveIntegerField(default=0)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField("Уақыты", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "created_at"], name="report_user_created_idx")]
        verbose_name = "Есеп сұранысы"
        verbose_name_plural = "Есеп сұраныстары"

    def __str__(self):
        return f"#{self.pk} {self.status}"
