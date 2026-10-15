from django.db import models


class Doctor(models.Model):
    class Specialty(models.TextChoices):
        THERAPIST = "therapist", "Терапевт"
        SURGEON = "surgeon", "Хирург"
        CARDIOLOGIST = "cardiologist", "Кардиолог"
        NEUROLOGIST = "neurologist", "Невролог"

    full_name = models.CharField("Аты-жөні", max_length=150)
    specialty = models.CharField(
        "Мамандығы",
        max_length=20,
        choices=Specialty.choices,
        default=Specialty.THERAPIST,
    )
    phone = models.CharField("Телефон", max_length=20, blank=True, default="")

    class Meta:
        ordering = ["full_name"]
        verbose_name = "Дәрігер"
        verbose_name_plural = "Дәрігерлер"

    def __str__(self):
        return self.full_name


class Patient(models.Model):
    full_name = models.CharField("Аты-жөні", max_length=150)
    birth_date = models.DateField("Туған күні")
    doctors = models.ManyToManyField(
        Doctor, blank=True, related_name="patients", verbose_name="Дәрігерлер"
    )

    class Meta:
        ordering = ["full_name"]
        verbose_name = "Науқас"
        verbose_name_plural = "Науқастар"

    def __str__(self):
        return self.full_name


class Diagnosis(models.Model):
    name = models.CharField("Диагноз", max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Диагноз"
        verbose_name_plural = "Диагноздар"

    def __str__(self):
        return self.name


class Appointment(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Жоспарланған"
        DONE = "done", "Өтті"
        CANCELLED = "cancelled", "Бас тартылды"

    doctor = models.ForeignKey(
        Doctor, on_delete=models.PROTECT, related_name="appointments",
        verbose_name="Дәрігер",
    )
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="appointments",
        verbose_name="Науқас",
    )
    diagnoses = models.ManyToManyField(
        Diagnosis, blank=True, related_name="appointments",
        verbose_name="Диагноздар",
    )
    date = models.DateTimeField("Қабылдау уақыты")
    price = models.DecimalField("Бағасы", max_digits=8, decimal_places=2, default=0)
    duration = models.PositiveIntegerField("Ұзақтығы (мин)", default=30)
    status = models.CharField(
        "Күйі", max_length=10, choices=Status.choices, default=Status.PLANNED
    )

    class Meta:
        ordering = ["-date"]
        verbose_name = "Қабылдау"
        verbose_name_plural = "Қабылдаулар"

    def __str__(self):
        return f"{self.patient} → {self.doctor} ({self.date:%d.%m.%Y})"