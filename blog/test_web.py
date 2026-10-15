from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Appointment, Doctor, Patient


def make_appointment(doctor, patient, **kw):
    kw.setdefault("date", timezone.now())
    kw.setdefault("price", 1000)
    return Appointment.objects.create(doctor=doctor, patient=patient, **kw)


class HomeTests(TestCase):
    def test_home_shows_totals(self):
        d = Doctor.objects.create(full_name="Асқар Нұрлан")
        p = Patient.objects.create(full_name="Айгүл Серік", birth_date="1990-01-01")
        make_appointment(d, p, price=2500)
        r = self.client.get(reverse("home"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["totals"]["n"], 1)
        self.assertContains(r, "Асқар Нұрлан")


class DoctorCrudTests(TestCase):
    def setUp(self):
        self.doctor = Doctor.objects.create(full_name="Асқар Нұрлан")
        self.patient = Patient.objects.create(
            full_name="Айгүл Серік", birth_date="1990-01-01")

    def data(self, **extra):
        data = {"full_name": "Бақыт Серіков", "specialty": "surgeon",
                "phone": "+77001234567"}
        data.update(extra)
        return data

    def test_list_and_detail(self):
        make_appointment(self.doctor, self.patient)
        r = self.client.get(reverse("doctor_list"))
        self.assertEqual(r.context["doctors"][0].n_appointments, 1)
        r = self.client.get(reverse("doctor_detail", args=[self.doctor.pk]))
        self.assertEqual(r.status_code, 200)

    def test_create_valid(self):
        r = self.client.post(reverse("doctor_create"), self.data())
        self.assertRedirects(r, reverse("doctor_list"))
        self.assertEqual(Doctor.objects.count(), 2)

    def test_create_bad_phone_rejected(self):
        r = self.client.post(reverse("doctor_create"), self.data(phone="abc"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("phone", r.context["form"].errors)
        self.assertEqual(Doctor.objects.count(), 1)

    def test_update(self):
        r = self.client.post(reverse("doctor_update", args=[self.doctor.pk]),
                             self.data(full_name="Асқар Нұрланов"))
        self.assertRedirects(r, reverse("doctor_list"))
        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.full_name, "Асқар Нұрланов")

    def test_delete_without_appointments(self):
        r = self.client.post(reverse("doctor_delete", args=[self.doctor.pk]))
        self.assertRedirects(r, reverse("doctor_list"))
        self.assertEqual(Doctor.objects.count(), 0)

    def test_delete_blocked_when_doctor_has_appointments(self):
        make_appointment(self.doctor, self.patient)
        r = self.client.post(reverse("doctor_delete", args=[self.doctor.pk]))
        self.assertRedirects(r, reverse("doctor_detail", args=[self.doctor.pk]))
        self.assertEqual(Doctor.objects.count(), 1)


class PatientDetailTests(TestCase):
    def test_detail_shows_appointments(self):
        d = Doctor.objects.create(full_name="Асқар Нұрлан")
        p = Patient.objects.create(full_name="Айгүл Серік", birth_date="1990-01-01")
        make_appointment(d, p)
        r = self.client.get(reverse("patient_detail", args=[p.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Асқар Нұрлан")


class AppointmentListFilterTests(TestCase):
    def setUp(self):
        self.d1 = Doctor.objects.create(full_name="Асқар Нұрлан")
        self.d2 = Doctor.objects.create(full_name="Бақыт Серіков")
        self.p = Patient.objects.create(full_name="Айгүл Серік", birth_date="1990-01-01")
        for i in range(20):
            make_appointment(self.d1, self.p, date=timezone.now() - timedelta(days=i))
        make_appointment(self.d2, self.p, status="done", price=9000)

    def test_pagination_15_per_page(self):
        r = self.client.get(reverse("appointment_list"))
        self.assertEqual(len(r.context["page_obj"]), 15)
        r = self.client.get(reverse("appointment_list"), {"page": 2})
        self.assertEqual(len(r.context["page_obj"]), 6)

    def test_filter_by_status_and_doctor(self):
        r = self.client.get(reverse("appointment_list"), {"status": "done"})
        self.assertEqual(r.context["stats"]["total"], 1)
        r = self.client.get(reverse("appointment_list"), {"doctor": self.d1.pk})
        self.assertEqual(r.context["stats"]["total"], 20)

    def test_search_by_name(self):
        r = self.client.get(reverse("appointment_list"), {"q": "Серіков"})
        self.assertEqual(r.context["stats"]["total"], 1)

    def test_invalid_filter_value_does_not_crash(self):
        r = self.client.get(reverse("appointment_list"), {"status": "hack", "page": "abc"})
        self.assertEqual(r.status_code, 200)

    def test_aggregate_stats(self):
        r = self.client.get(reverse("appointment_list"), {"status": "done"})
        self.assertEqual(r.context["stats"]["sum_price"], 9000)

    def test_list_query_count_is_constant(self):
        # 3 сұраныс: COUNT, қабылдаулар (JOIN), диагноздар (prefetch) + doctor-select
        with self.assertNumQueries(5):
            self.client.get(reverse("appointment_list"))
