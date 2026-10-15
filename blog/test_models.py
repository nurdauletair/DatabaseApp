from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from .models import Appointment, Diagnosis, Doctor, Patient


class ModelTests(TestCase):
    def setUp(self):
        self.doctor = Doctor.objects.create(
            full_name="Асқар Нұрлан", specialty=Doctor.Specialty.CARDIOLOGIST)
        self.patient = Patient.objects.create(
            full_name="Айгүл Серік", birth_date="1990-01-01")
        self.appointment = Appointment.objects.create(
            doctor=self.doctor, patient=self.patient, date=timezone.now())

    def test_str_methods(self):
        self.assertEqual(str(self.doctor), "Асқар Нұрлан")
        self.assertEqual(str(self.patient), "Айгүл Серік")
        self.assertEqual(str(Diagnosis(name="Грипп")), "Грипп")
        self.assertIn("Айгүл Серік → Асқар Нұрлан", str(self.appointment))

    def test_defaults(self):
        self.assertEqual(self.appointment.status, Appointment.Status.PLANNED)
        self.assertEqual(self.appointment.duration, 30)
        self.assertEqual(self.appointment.price, 0)

    def test_choices_display(self):
        self.assertEqual(self.doctor.get_specialty_display(), "Кардиолог")
        self.assertEqual(self.appointment.get_status_display(), "Жоспарланған")

    def test_appointments_ordered_newest_first(self):
        newer = Appointment.objects.create(
            doctor=self.doctor, patient=self.patient,
            date=timezone.now() + timedelta(days=1))
        self.assertEqual(Appointment.objects.first(), newer)

    def test_doctor_with_appointments_is_protected(self):
        with self.assertRaises(ProtectedError):
            self.doctor.delete()

    def test_deleting_patient_cascades_to_appointments(self):
        self.patient.delete()
        self.assertEqual(Appointment.objects.count(), 0)

    def test_many_to_many_diagnoses_and_related_names(self):
        flu = Diagnosis.objects.create(name="Грипп")
        self.appointment.diagnoses.add(flu)
        self.assertEqual(list(flu.appointments.all()), [self.appointment])
        self.assertEqual(list(self.doctor.appointments.all()), [self.appointment])

    def test_diagnosis_name_is_unique(self):
        Diagnosis.objects.create(name="Грипп")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Diagnosis.objects.create(name="Грипп")
