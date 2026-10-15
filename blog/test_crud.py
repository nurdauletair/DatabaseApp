from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Appointment, Diagnosis, Doctor, Patient


class AppointmentCrudTests(TestCase):
    def setUp(self):
        self.doctor = Doctor.objects.create(full_name="Асқар Нұрлан")
        self.patient = Patient.objects.create(
            full_name="Айгүл Серік", birth_date="1990-01-01")
        self.diagnosis = Diagnosis.objects.create(name="Грипп")
        self.a = Appointment.objects.create(
            doctor=self.doctor, patient=self.patient,
            date=timezone.now() - timedelta(days=1), price=3000, duration=30)

    def data(self, **extra):
        data = {
            "doctor": self.doctor.pk,
            "patient": self.patient.pk,
            "diagnoses": [self.diagnosis.pk],
            "date": (timezone.localtime() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
            "price": "4500",
            "duration": "30",
            "status": "planned",
        }
        data.update(extra)
        return data

    def test_list_ok(self):
        r = self.client.get(reverse("appointment_list"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Айгүл Серік")

    def test_create_valid_redirects(self):
        r = self.client.post(reverse("appointment_create"), self.data())
        self.assertRedirects(r, reverse("appointment_list"))
        self.assertEqual(Appointment.objects.count(), 2)

    def test_create_invalid_shows_errors_and_saves_nothing(self):
        r = self.client.post(reverse("appointment_create"), self.data(duration="5"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("duration", r.context["form"].errors)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_future_done_is_rejected(self):
        r = self.client.post(reverse("appointment_create"), self.data(status="done"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"].non_field_errors())
        self.assertEqual(Appointment.objects.count(), 1)

    def test_update_redirects_to_detail(self):
        r = self.client.post(
            reverse("appointment_update", args=[self.a.pk]),
            self.data(price="9999", status="done",
                      date=(timezone.localtime() - timedelta(days=1))
                      .strftime("%Y-%m-%dT%H:%M")))
        self.assertRedirects(r, reverse("appointment_detail", args=[self.a.pk]))
        self.a.refresh_from_db()
        self.assertEqual(self.a.price, 9999)

    def test_delete_get_does_not_delete(self):
        r = self.client.get(reverse("appointment_delete", args=[self.a.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_delete_post_deletes(self):
        r = self.client.post(reverse("appointment_delete", args=[self.a.pk]))
        self.assertRedirects(r, reverse("appointment_list"))
        self.assertEqual(Appointment.objects.count(), 0)

    def test_missing_appointment_404(self):
        r = self.client.get(reverse("appointment_detail", args=[9999]))
        self.assertEqual(r.status_code, 404)


class PatientCrudTests(TestCase):
    def setUp(self):
        self.doctor = Doctor.objects.create(full_name="Асқар Нұрлан")
        self.patient = Patient.objects.create(
            full_name="Айгүл Серік", birth_date="1990-01-01")
        for i in range(2):
            Appointment.objects.create(
                doctor=self.doctor, patient=self.patient,
                date=timezone.now(), price=1000, duration=20)

    def data(self, **extra):
        data = {"full_name": "Жанар Бекова", "birth_date": "1985-05-05",
                "doctors": [self.doctor.pk]}
        data.update(extra)
        return data

    def test_list_shows_appointment_count(self):
        r = self.client.get(reverse("patient_list"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["patients"][0].n_appointments, 2)

    def test_create_valid_redirects(self):
        r = self.client.post(reverse("patient_create"), self.data())
        self.assertRedirects(r, reverse("patient_list"))
        self.assertEqual(Patient.objects.count(), 2)

    def test_create_one_word_name_rejected(self):
        r = self.client.post(reverse("patient_create"), self.data(full_name="Жанар"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("full_name", r.context["form"].errors)
        self.assertEqual(Patient.objects.count(), 1)

    def test_create_future_birth_date_rejected(self):
        future = (timezone.localdate() + timedelta(days=30)).isoformat()
        r = self.client.post(reverse("patient_create"), self.data(birth_date=future))
        self.assertIn("birth_date", r.context["form"].errors)

    def test_update(self):
        r = self.client.post(
            reverse("patient_update", args=[self.patient.pk]),
            self.data(full_name="Айгүл Серікқызы"))
        self.assertRedirects(r, reverse("patient_list"))
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.full_name, "Айгүл Серікқызы")

    def test_delete_page_warns_about_cascade(self):
        r = self.client.get(reverse("patient_delete", args=[self.patient.pk]))
        self.assertContains(r, "2 қабылдау да жойылады")
        self.assertEqual(Patient.objects.count(), 1)

    def test_delete_post_cascades(self):
        r = self.client.post(reverse("patient_delete", args=[self.patient.pk]))
        self.assertRedirects(r, reverse("patient_list"))
        self.assertEqual(Patient.objects.count(), 0)
        self.assertEqual(Appointment.objects.count(), 0)
