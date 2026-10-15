from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Appointment, Diagnosis, Doctor, Patient


class ApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.doctor = Doctor.objects.create(full_name="Асқар Нұрлан", specialty="surgeon")
        cls.patient = Patient.objects.create(full_name="Айгүл Серік", birth_date="1990-01-01")
        cls.flu = Diagnosis.objects.create(name="Грипп")
        for i in range(5):
            a = Appointment.objects.create(
                doctor=cls.doctor, patient=cls.patient, price=1000 * (i + 1),
                date=timezone.now() - timedelta(days=i))
            a.diagnoses.add(cls.flu)
        cls.user = get_user_model().objects.create_user("tester", password="pass12345")

    def setUp(self):
        self.anon = APIClient()
        self.auth = APIClient()
        self.auth.force_authenticate(self.user)

    def payload(self, **extra):
        data = {"doctor_id": self.doctor.pk, "patient_id": self.patient.pk,
                "diagnoses": ["Грипп"], "price": "4500.00", "duration": 30,
                "status": "planned",
                "date": (timezone.now() + timedelta(days=2)).isoformat()}
        data.update(extra)
        return data

    # --- оқу: бәріне ашық
    def test_list_is_public_and_paginated(self):
        r = self.anon.get("/api/appointments/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 5)
        self.assertIn("results", r.data)

    def test_detail_has_nested_doctor_and_diagnosis_names(self):
        a = Appointment.objects.first()
        r = self.anon.get(f"/api/appointments/{a.pk}/")
        self.assertEqual(r.data["doctor"]["full_name"], "Асқар Нұрлан")
        self.assertEqual(r.data["diagnoses"], ["Грипп"])

    def test_missing_object_404(self):
        self.assertEqual(self.anon.get("/api/appointments/9999/").status_code, 404)

    # --- рұқсаттар
    def test_anonymous_cannot_write(self):
        r = self.anon.post("/api/appointments/", self.payload(), format="json")
        self.assertIn(r.status_code, (401, 403))
        self.assertEqual(Appointment.objects.count(), 5)

    def test_anonymous_cannot_delete(self):
        a = Appointment.objects.first()
        r = self.anon.delete(f"/api/appointments/{a.pk}/")
        self.assertIn(r.status_code, (401, 403))
        self.assertEqual(Appointment.objects.count(), 5)

    # --- толық CRUD
    def test_create_201(self):
        r = self.auth.post("/api/appointments/", self.payload(), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Appointment.objects.count(), 6)

    def test_create_invalid_400_and_nothing_saved(self):
        r = self.auth.post("/api/appointments/", self.payload(duration=5), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("duration", r.data)
        self.assertEqual(Appointment.objects.count(), 5)

    def test_future_done_rejected(self):
        r = self.auth.post("/api/appointments/", self.payload(status="done"), format="json")
        self.assertEqual(r.status_code, 400)

    def test_patch_200(self):
        a = Appointment.objects.first()
        r = self.auth.patch(f"/api/appointments/{a.pk}/", {"price": "7777.00"}, format="json")
        self.assertEqual(r.status_code, 200)
        a.refresh_from_db()
        self.assertEqual(a.price, 7777)

    def test_delete_204(self):
        a = Appointment.objects.first()
        r = self.auth.delete(f"/api/appointments/{a.pk}/")
        self.assertEqual(r.status_code, 204)
        self.assertEqual(Appointment.objects.count(), 4)

    def test_doctor_with_appointments_delete_returns_409(self):
        r = self.auth.delete(f"/api/doctors/{self.doctor.pk}/")
        self.assertEqual(r.status_code, 409)
        self.assertTrue(Doctor.objects.filter(pk=self.doctor.pk).exists())

    def test_patient_create_one_word_name_rejected(self):
        r = self.auth.post("/api/patients/", {"full_name": "Жанар", "birth_date": "1990-01-01"},
                           format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("full_name", r.data)

    def test_patient_create_with_doctor_ids(self):
        r = self.auth.post("/api/patients/", {"full_name": "Жанар Бекова",
                           "birth_date": "1985-05-05", "doctor_ids": [self.doctor.pk]},
                           format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["doctors"][0]["full_name"], "Асқар Нұрлан")

    # --- сүзу, іздеу, сұрыптау, агрегаттау
    def test_filter_search_ordering(self):
        r = self.anon.get("/api/appointments/", {"ordering": "-price"})
        self.assertEqual(r.data["results"][0]["price"], "5000.00")
        r = self.anon.get("/api/appointments/", {"search": "Серік"})
        self.assertEqual(r.data["count"], 5)
        r = self.anon.get("/api/appointments/", {"status": "done"})
        self.assertEqual(r.data["count"], 0)

    def test_stats_endpoint(self):
        r = self.anon.get("/api/appointments/stats/")
        self.assertEqual(r.data["total"], 5)
        self.assertEqual(r.data["by_status"], {"planned": 5})

    # --- N+1 жоқ: сұраныстар саны деректер санына тәуелсіз
    def test_appointment_list_uses_3_queries(self):
        with self.assertNumQueries(3):      # COUNT + қабылдаулар(JOIN) + диагноздар
            self.anon.get("/api/appointments/")

    def test_patient_list_uses_3_queries(self):
        with self.assertNumQueries(3):      # COUNT + науқастар(annotate) + дәрігерлер
            self.anon.get("/api/patients/")
