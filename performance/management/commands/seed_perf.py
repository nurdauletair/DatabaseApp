import random
from datetime import date, timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone
from blog.models import Appointment, AppointmentNote, Diagnosis, Doctor, Patient


class Command(BaseCommand):
    help = "Seed a NEW isolated lab database: 20,000 appointments, 60,000 notes."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.PERFORMANCE_LAB:
            raise CommandError("Enable PERFORMANCE_LAB=1 for the laboratory.")
        if Appointment.objects.filter(is_training=True).exists():
            raise CommandError("Training records already exist; no data was changed.")
        User = get_user_model()
        doctor_user = User.objects.get(username="demo_doctor")
        patient_user = User.objects.get(username="demo_patient")
        rng = random.Random(42)
        doctors = list(Doctor.objects.bulk_create([Doctor(full_name=f"Оқу Дәрігер {i:03}", specialty=rng.choice(Doctor.Specialty.values)) for i in range(199)]))
        doctors.append(Doctor.objects.get(user=doctor_user))
        patients = list(Patient.objects.bulk_create([Patient(full_name=f"Оқу Науқас {i:04}", birth_date=date(1980, 1, 1)+timedelta(days=i)) for i in range(1999)]))
        patients.append(Patient.objects.get(user=patient_user))
        diagnoses = Diagnosis.objects.bulk_create([Diagnosis(name=f"Оқу диагнозы {i:02}") for i in range(50)])
        now = timezone.now()
        appointments = Appointment.objects.bulk_create([
            Appointment(doctor=rng.choice(doctors), patient=rng.choice(patients), date=now-timedelta(minutes=i),
                        is_training=True, status=rng.choice(["planned", "done"]), price=3000+i%10*500,
                        reason="Оқу мақсатындағы синтетикалық дерек. " * 200)
            for i in range(20_000)], batch_size=500)
        Through = Appointment.diagnoses.through
        Through.objects.bulk_create([Through(appointment_id=a.pk, diagnosis_id=d.pk)
                                     for a in appointments for d in rng.sample(diagnoses, 3)], batch_size=2000)
        AppointmentNote.objects.bulk_create([AppointmentNote(appointment=rng.choice(appointments), text=f"Оқу жазбасы {i}") for i in range(60_000)], batch_size=2000)
        self.stdout.write(self.style.SUCCESS("Added 20,000 training appointments and 60,000 notes; original records and accounts preserved."))
