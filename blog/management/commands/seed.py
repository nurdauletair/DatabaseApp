import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from blog.models import Appointment, Diagnosis, Doctor, Patient

DIAGNOSES = ["Грипп", "Гипертония", "Гастрит", "Мигрень", "Бронхит"]


class Command(BaseCommand):
    help = "20 дәрігер, 100 қабылдау, 5 диагноз (bulk_create)"

    @transaction.atomic
    def handle(self, *args, **options):
        # ескі деректерді тазалау (алдымен тәуелділері)
        Appointment.objects.all().delete()
        Patient.objects.all().delete()
        Doctor.objects.all().delete()
        Diagnosis.objects.all().delete()

        specialties = [s for s, _ in Doctor.Specialty.choices]
        Doctor.objects.bulk_create([
            Doctor(full_name=f"Дәрігер {i}", specialty=specialties[i % 4],
                   phone=f"+7700000{i:04d}")
            for i in range(1, 21)
        ])
        Diagnosis.objects.bulk_create([Diagnosis(name=n) for n in DIAGNOSES])
        Patient.objects.bulk_create([
            Patient(full_name=f"Науқас {i}", birth_date=f"19{60 + i % 40}-01-15")
            for i in range(1, 31)
        ])

        doctors = list(Doctor.objects.all())
        patients = list(Patient.objects.all())
        diagnoses = list(Diagnosis.objects.all())
        now = timezone.now()

        Appointment.objects.bulk_create([
            Appointment(
                doctor=random.choice(doctors),
                patient=random.choice(patients),
                date=now - timedelta(days=i),
                price=Decimal(random.randrange(1500, 9000, 100)),
                duration=random.choice([15, 20, 30, 45, 60]),
                status=random.choice(Appointment.Status.values),
            )
            for i in range(100)
        ])

        # көп-көп байланыс: әр қабылдауға 2 диагноз (аралық кестеге bulk_create)
        Through = Appointment.diagnoses.through
        Through.objects.bulk_create([
            Through(appointment_id=a.id, diagnosis_id=d.id)
            for a in Appointment.objects.all()
            for d in random.sample(diagnoses, 2)
        ])

        self.stdout.write(self.style.SUCCESS(
            f"Дайын: {Doctor.objects.count()} дәрігер, "
            f"{Patient.objects.count()} науқас, "
            f"{Appointment.objects.count()} қабылдау, "
            f"{Diagnosis.objects.count()} диагноз"
        ))