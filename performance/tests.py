from datetime import timedelta
from io import StringIO
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from blog.models import Appointment, AppointmentNote, Diagnosis, Doctor, Patient
from .queries import slow_rows, optimized_rows

@override_settings(PERFORMANCE_LAB=True)
class PerformanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("setup_roles", stdout=StringIO())
        cls.admin = get_user_model().objects.create_superuser("perf_admin", password="Perf-Test-Only-246!")
        cls.patient_user = get_user_model().objects.create_user("perf_patient")
        cls.patient_user.groups.add(Group.objects.get(name="patient"))
        cls.other_user = get_user_model().objects.create_user("perf_other")
        cls.other_user.groups.add(Group.objects.get(name="patient"))
        cls.doctor = Doctor.objects.create(full_name="Оқу Дәрігер")
        cls.patient = Patient.objects.create(full_name="Оқу Науқас", birth_date="1990-01-01", user=cls.patient_user)
        cls.other_patient = Patient.objects.create(full_name="Бөгде Науқас", birth_date="1990-01-01", user=cls.other_user)
        diagnosis = Diagnosis.objects.create(name="Оқу диагнозы")
        for i in range(10):
            a = Appointment.objects.create(doctor=cls.doctor, patient=cls.patient if i < 5 else cls.other_patient,
                 date=timezone.now()-timedelta(minutes=i), is_training=True, reason="long text "*100)
            a.diagnoses.add(diagnosis)
            AppointmentNote.objects.create(appointment=a, text="Оқу жазбасы")

    def consume(self, queryset, optimized=False):
        return [(a.pk,a.doctor.full_name,a.patient.full_name,[d.name for d in a.diagnoses.all()],
                 a.n_notes if optimized else a.notes.count()) for a in queryset]

    def test_slow_page_shows_n_plus_one(self):
        with self.assertNumQueries(41):
            self.consume(slow_rows(self.admin))

    def test_optimized_is_two_queries_with_identical_results(self):
        expected = self.consume(slow_rows(self.admin))
        with self.assertNumQueries(2):
            actual = self.consume(optimized_rows(self.admin), optimized=True)
        self.assertEqual(actual, expected)

    def test_patient_cannot_see_foreign_rows(self):
        rows = list(optimized_rows(self.patient_user))
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(a.patient_id == self.patient.pk for a in rows))

    def test_long_reason_is_not_loaded(self):
        self.assertIn("reason", optimized_rows(self.admin)[0].get_deferred_fields())

    def test_feature_is_disabled_outside_lab(self):
        self.client.force_login(self.admin)
        with override_settings(PERFORMANCE_LAB=False):
            self.assertEqual(self.client.get("/lab11/slow/").status_code, 404)

    def test_cached_results_are_isolated_and_warm_hit_has_no_data_sql(self):
        from django.test import RequestFactory
        from django.contrib.sessions.backends.db import SessionStore
        from django.core.cache import cache
        from .views import cached
        cache.clear()
        request = RequestFactory().get("/lab11/cached/")
        request.user, request.session = self.admin, SessionStore()
        cached(request)
        with self.assertNumQueries(0):
            response = cached(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("private", response["Cache-Control"])
        self.client.force_login(self.patient_user)
        response = self.client.get("/lab11/cached/")
        self.assertContains(response, "Оқу Науқас")
        self.assertNotContains(response, "Бөгде Науқас")
        self.client.force_login(self.other_user)
        response = self.client.get("/lab11/cached/")
        self.assertContains(response, "Бөгде Науқас")
        self.assertNotContains(response, "Оқу Науқас")

    def test_stats_and_page_revision_refresh_after_committed_changes(self):
        from django.core.cache import cache
        from .cache import clinic_stats, revision
        cache.clear()
        before = clinic_stats(self.admin)
        old_revision = revision()
        with self.captureOnCommitCallbacks(execute=True):
            note = AppointmentNote.objects.create(appointment=Appointment.objects.first(), text="New note")
        self.assertNotEqual(revision(), old_revision)
        self.assertEqual(clinic_stats(self.admin)["notes"], before["notes"]+1)
        with self.captureOnCommitCallbacks(execute=True):
            note.delete()
        self.assertEqual(clinic_stats(self.admin)["notes"], before["notes"])

    def test_diagnosis_m2m_invalidates_cache(self):
        from .cache import revision
        before = revision()
        with self.captureOnCommitCallbacks(execute=True):
            Appointment.objects.first().diagnoses.clear()
        self.assertNotEqual(revision(), before)

    def test_permission_revocation_blocks_a_previously_cached_page(self):
        from django.core.cache import cache
        cache.clear()
        self.client.force_login(self.patient_user)
        self.assertEqual(self.client.get("/lab11/cached/").status_code, 200)
        self.patient_user.groups.clear()
        self.assertEqual(self.client.get("/lab11/cached/").status_code, 403)
