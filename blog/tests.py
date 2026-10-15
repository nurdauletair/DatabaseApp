from django.test import TestCase
from django.utils import timezone

from .models import Appointment, Diagnosis, Doctor, Patient


class AppointmentQueryTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        doctors = [Doctor.objects.create(full_name=f"Дәрігер {i}") for i in range(3)]
        patient = Patient.objects.create(full_name="Науқас", birth_date="1990-01-01")
        tags = [Diagnosis.objects.create(name=f"Диагноз {i}") for i in range(2)]
        for i in range(5):
            a = Appointment.objects.create(
                doctor=doctors[i % 3], patient=patient, date=timezone.now())
            a.diagnoses.set(tags)

    def test_n_plus_one(self):
        # 1 тізім + 5 қабылдауға 5 сұраныс
        with self.assertNumQueries(6):
            for a in Appointment.objects.all():
                a.doctor.full_name

    def test_select_related(self):
        with self.assertNumQueries(1):
            for a in Appointment.objects.select_related("doctor"):
                a.doctor.full_name

    def test_prefetch_related(self):
        with self.assertNumQueries(2):
            for a in Appointment.objects.prefetch_related("diagnoses"):
                [d.name for d in a.diagnoses.all()]

    def test_both(self):
        with self.assertNumQueries(2):
            qs = Appointment.objects.select_related("doctor").prefetch_related("diagnoses")
            for a in qs:
                a.doctor.full_name
                [d.name for d in a.diagnoses.all()]