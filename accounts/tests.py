from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.test import Client, TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from blog.models import Appointment, Diagnosis, Doctor, Patient

User = get_user_model()
PASSWORD = "Clinic-Testing-24680!"


class ClinicAuthTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("setup_roles", stdout=StringIO())
        def make(name, role):
            user = User.objects.create_user(name, password=PASSWORD, is_staff=role in ("doctor", "registrar"))
            user.groups.add(Group.objects.get(name=role))
            return user
        cls.patient_user = make("patient_one", "patient")
        cls.other_patient_user = make("patient_two", "patient")
        cls.doctor_user = make("doctor_one", "doctor")
        cls.other_doctor_user = make("doctor_two", "doctor")
        cls.registrar = make("registrar", "registrar")
        cls.doctor = Doctor.objects.create(full_name="Бірінші Дәрігер", user=cls.doctor_user)
        cls.other_doctor = Doctor.objects.create(full_name="Екінші Дәрігер", user=cls.other_doctor_user)
        cls.patient = Patient.objects.create(full_name="Бірінші Науқас", birth_date="1990-01-01", user=cls.patient_user)
        cls.other_patient = Patient.objects.create(full_name="Бөгде Науқас", birth_date="1995-01-01", user=cls.other_patient_user)
        cls.own = Appointment.objects.create(doctor=cls.doctor, patient=cls.patient,
                                            date=timezone.now() - timedelta(days=1), price=1000)
        cls.foreign = Appointment.objects.create(doctor=cls.other_doctor, patient=cls.other_patient,
                                                date=timezone.now() - timedelta(days=1), price=9000)
        # Same patient, different physician: patient detail must still scope appointments.
        cls.shared = Appointment.objects.create(doctor=cls.other_doctor, patient=cls.patient,
                                               date=timezone.now() - timedelta(days=2), price=5000)
        cls.diagnosis = Diagnosis.objects.create(name="Оқу диагнозы")

    def api(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_anonymous_html_redirect_and_api_401(self):
        for url in ("/", "/appointments/", "/patients/", "/doctors/", "/profile/", "/appointments/new/"):
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), f"/login/?next={url}", fetch_redirect_response=False)
        self.assertEqual(self.client.get("/api/appointments/").status_code, 401)

    def test_signup_creates_patient_and_ignores_privilege_fields(self):
        response = self.client.post("/signup/", {
            "username": "new_patient", "full_name": "Жаңа Науқас", "birth_date": "2001-02-03",
            "phone": "+77001234567", "password1": PASSWORD, "password2": PASSWORD,
            "is_staff": "on", "is_superuser": "on", "groups": [Group.objects.get(name="registrar").pk],
        })
        self.assertRedirects(response, "/profile/")
        user = User.objects.get(username="new_patient")
        self.assertEqual(user.role, "patient")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(user.patient_profile.full_name, "Жаңа Науқас")

    def test_weak_password_rejected(self):
        count = User.objects.count()
        response = self.client.post("/signup/", {"username": "weak", "full_name": "Жаңа Науқас",
            "birth_date": "2001-01-01", "password1": "12345678", "password2": "12345678"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("password2", response.context["form"].errors)
        self.assertEqual(User.objects.count(), count)

    def test_patient_list_and_stats_only_own(self):
        api = self.api(self.patient_user)
        response = api.get("/api/appointments/")
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(api.get("/api/appointments/stats/").data["total"], 2)
        self.assertEqual(api.get("/api/patients/").data["count"], 1)
        self.assertEqual(api.get(f"/api/appointments/{self.foreign.pk}/").status_code, 404)
        self.client.force_login(self.patient_user)
        self.assertNotContains(self.client.get("/appointments/"), "Бөгде Науқас")
        self.assertEqual(self.client.get("/").context["totals"]["n"], 2)
        self.assertEqual(self.client.get(f"/appointments/{self.foreign.pk}/").status_code, 403)
        self.assertEqual(self.client.get(f"/patients/{self.other_patient.pk}/").status_code, 404)

    def test_doctor_scoped_patient_detail_and_counts(self):
        self.client.force_login(self.doctor_user)
        response = self.client.get(f"/patients/{self.patient.pk}/")
        self.assertEqual(list(response.context["appointments"].values_list("pk", flat=True)), [self.own.pk])
        api = self.api(self.doctor_user)
        self.assertEqual(api.get("/api/appointments/stats/").data["total"], 1)
        self.assertEqual(api.get("/api/patients/").data["results"][0]["appointments_count"], 1)
        self.assertEqual(api.get(f"/api/doctors/{self.other_doctor.pk}/").data["appointments_count"], 0)

    def test_patient_cannot_create_edit_or_delete_generic_records(self):
        self.client.force_login(self.patient_user)
        for url in ("/appointments/new/", f"/appointments/{self.own.pk}/edit/",
                    f"/appointments/{self.own.pk}/delete/", "/patients/new/", "/doctors/new/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        api = self.api(self.patient_user)
        self.assertEqual(api.post("/api/appointments/", {}).status_code, 403)
        self.assertEqual(api.patch(f"/api/appointments/{self.own.pk}/", {"status": "done"}).status_code, 403)
        self.assertEqual(api.delete(f"/api/appointments/{self.own.pk}/").status_code, 403)
        self.assertEqual(api.get("/api/diagnoses/").status_code, 403)

    def test_patient_books_only_for_self_and_cannot_set_clinical_fields(self):
        self.client.force_login(self.patient_user)
        response = self.client.post("/appointments/book/", {
            "doctor": self.doctor.pk,
            "date": timezone.localtime(timezone.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
            "patient": self.other_patient.pk, "price": 999, "status": "done", "diagnoses": [self.diagnosis.pk],
        })
        self.assertEqual(response.status_code, 302)
        appointment = Appointment.objects.latest("pk")
        self.assertEqual(appointment.patient, self.patient)
        self.assertEqual(appointment.status, "planned")
        self.assertEqual(appointment.price, 0)
        self.assertEqual(appointment.diagnoses.count(), 0)

    def test_booking_rejects_past_date(self):
        self.client.force_login(self.patient_user)
        response = self.client.post("/appointments/book/", {"doctor": self.doctor.pk, "date": "2000-01-01T12:00"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("date", response.context["form"].errors)

    def test_doctor_edits_own_but_not_foreign(self):
        self.client.force_login(self.doctor_user)
        self.assertEqual(self.client.get(f"/appointments/{self.own.pk}/edit/").status_code, 200)
        self.assertEqual(self.client.get(f"/appointments/{self.foreign.pk}/edit/").status_code, 403)
        api = self.api(self.doctor_user)
        self.assertEqual(api.patch(f"/api/appointments/{self.own.pk}/", {"status": "done"}).status_code, 200)
        self.assertEqual(api.patch(f"/api/appointments/{self.foreign.pk}/", {"status": "done"}).status_code, 404)

    def test_doctor_cannot_reassign_reprice_reschedule_or_confirm(self):
        api = self.api(self.doctor_user)
        for payload in ({"doctor_id": self.other_doctor.pk}, {"patient_id": self.other_patient.pk},
                        {"price": "9999.00"}, {"date": (timezone.now()+timedelta(days=2)).isoformat()},
                        {"status": "confirmed"}):
            with self.subTest(payload=payload):
                response = api.patch(f"/api/appointments/{self.own.pk}/", payload)
                self.assertEqual(response.status_code, 403, response.data)
        self.own.refresh_from_db()
        self.assertEqual(self.own.patient, self.patient)
        self.assertEqual(self.own.price, 1000)

    def test_only_registrar_confirms_and_requires_post(self):
        for user in (self.patient_user, self.doctor_user):
            self.client.force_login(user)
            self.assertEqual(self.client.post(f"/appointments/{self.own.pk}/confirm/").status_code, 403)
            self.assertEqual(self.api(user).post(f"/api/appointments/{self.own.pk}/confirm/").status_code, 403)
        self.client.force_login(self.registrar)
        self.assertEqual(self.client.get(f"/appointments/{self.own.pk}/confirm/").status_code, 405)
        self.assertEqual(self.client.post(f"/appointments/{self.own.pk}/confirm/").status_code, 302)
        self.own.refresh_from_db()
        self.assertEqual(self.own.status, "confirmed")
        self.assertEqual(self.api(self.registrar).post(f"/api/appointments/{self.own.pk}/confirm/").status_code, 400)

    def test_registrar_can_create_and_see_all(self):
        api = self.api(self.registrar)
        self.assertEqual(api.get("/api/appointments/").data["count"], 3)
        response = api.post("/api/appointments/", {
            "doctor_id": self.doctor.pk, "patient_id": self.other_patient.pk,
            "date": (timezone.now()+timedelta(days=3)).isoformat(), "duration": 30, "price": "3000.00"})
        self.assertEqual(response.status_code, 201, response.data)

    def test_template_hides_unauthorized_actions(self):
        self.client.force_login(self.patient_user)
        response = self.client.get("/appointments/")
        self.assertContains(response, "/appointments/book/")
        self.assertNotContains(response, "/appointments/new/")
        self.assertNotContains(response, f"/appointments/{self.own.pk}/edit/")

    def test_login_creates_session_and_post_logout_flushes_it(self):
        self.assertTrue(self.client.login(username=self.patient_user.username, password=PASSWORD))
        key = self.client.session.session_key
        self.assertTrue(Session.objects.filter(session_key=key).exists())
        self.assertEqual(self.client.get("/logout/").status_code, 405)
        self.assertTrue(Session.objects.filter(session_key=key).exists())
        self.assertEqual(self.client.post("/logout/").status_code, 302)
        self.assertFalse(Session.objects.filter(session_key=key).exists())

    def test_profile_counter_and_cookie_settings(self):
        self.client.login(username=self.patient_user.username, password=PASSWORD)
        response = self.client.get("/profile/")
        self.assertEqual(response.context["visits"], 1)
        self.assertEqual(self.client.get("/profile/").context["visits"], 2)
        cookie = response.cookies["sessionid"]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(cookie["max-age"], 28800)

    def test_logout_all_preserves_other_users_sessions(self):
        second, stranger = Client(), Client()
        self.client.force_login(self.patient_user)
        second.force_login(self.patient_user)
        stranger.force_login(self.other_patient_user)
        stranger_key = stranger.session.session_key
        self.assertEqual(self.client.get("/logout-all/").status_code, 405)
        self.client.post("/logout-all/")
        self.assertEqual(second.get("/profile/").status_code, 302)
        self.assertTrue(Session.objects.filter(session_key=stranger_key).exists())

    def test_password_change_invalidates_old_browser_session(self):
        self.client.force_login(self.patient_user)
        self.patient_user.set_password("Another-Clinic-Password-246!")
        self.patient_user.save()
        self.assertEqual(self.client.get("/profile/").status_code, 302)

    def test_csrf_protects_state_changes(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.patient_user)
        for url in ("/logout/", "/logout-all/", "/appointments/book/"):
            self.assertEqual(client.post(url, {}).status_code, 403)

    def test_drf_token_authentication_and_revocation(self):
        api = APIClient()
        response = api.post("/api/token/", {"username": self.patient_user.username, "password": PASSWORD})
        self.assertEqual(response.status_code, 200)
        api.credentials(HTTP_AUTHORIZATION="Token " + response.data["token"])
        self.assertEqual(api.get("/api/me/").data["auth"], "TokenAuthentication")
        self.assertEqual(api.get("/api/appointments/").status_code, 200)
        self.assertEqual(api.post("/api/appointments/", {}).status_code, 403)
        self.assertEqual(api.post("/api/token/logout/").status_code, 204)
        self.assertEqual(api.get("/api/me/").status_code, 401)

    def test_jwt_access_refresh_blacklist_and_invalid_token(self):
        api = APIClient()
        response = api.post("/api/jwt/", {"username": self.doctor_user.username, "password": PASSWORD})
        self.assertEqual(response.status_code, 200)
        access, refresh = response.data["access"], response.data["refresh"]
        token = RefreshToken(refresh)
        self.assertEqual(token["exp"] - token["iat"], 7 * 86400)
        self.assertEqual(token.access_token["exp"] - token.access_token["iat"], 900)
        api.credentials(HTTP_AUTHORIZATION="Bearer " + access)
        self.assertEqual(api.get("/api/me/").data["auth"], "JWTAuthentication")
        self.assertEqual(api.post("/api/jwt/logout/", {"refresh": refresh}).status_code, 204)
        self.assertEqual(api.post("/api/jwt/refresh/", {"refresh": refresh}).status_code, 401)
        # Access tokens expire independently after 15 minutes.
        self.assertEqual(api.get("/api/me/").status_code, 200)
        api.credentials(HTTP_AUTHORIZATION="Bearer abc.def.ghi")
        self.assertEqual(api.get("/api/me/").status_code, 401)

    def test_jwt_refresh_rotates_and_blacklists_previous(self):
        api = APIClient()
        refresh = str(RefreshToken.for_user(self.patient_user))
        response = api.post("/api/jwt/refresh/", {"refresh": refresh})
        self.assertEqual(response.status_code, 200)
        self.assertIn("refresh", response.data)
        self.assertEqual(api.post("/api/jwt/refresh/", {"refresh": refresh}).status_code, 401)

    def test_cannot_blacklist_another_users_refresh(self):
        api = self.api(self.patient_user)
        refresh = str(RefreshToken.for_user(self.other_patient_user))
        self.assertEqual(api.post("/api/jwt/logout/", {"refresh": refresh}).status_code, 403)
        self.assertEqual(APIClient().post("/api/jwt/refresh/", {"refresh": refresh}).status_code, 200)

    def test_inactive_user_cannot_get_tokens(self):
        self.patient_user.is_active = False
        self.patient_user.save()
        for url in ("/api/token/", "/api/jwt/"):
            self.assertIn(APIClient().post(url, {"username": self.patient_user.username, "password": PASSWORD}).status_code, (400, 401))

    def test_admin_is_scoped_and_registrar_cannot_manage_users(self):
        self.client.force_login(self.doctor_user)
        response = self.client.get("/admin/blog/appointment/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["cl"].result_count, 1)
        self.assertEqual(self.client.get(f"/admin/blog/appointment/{self.foreign.pk}/change/").status_code, 302)
        self.assertNotContains(self.client.get("/admin/blog/patient/"), "Бөгде Науқас")
        self.client.force_login(self.registrar)
        self.assertEqual(self.client.get("/admin/accounts/user/").status_code, 403)
        self.assertEqual(self.client.get("/admin/auth/group/").status_code, 403)
        self.client.force_login(self.patient_user)
        self.assertEqual(self.client.get("/admin/").status_code, 302)

    def test_admin_doctor_cannot_confirm_via_post_or_bulk_action(self):
        self.client.force_login(self.doctor_user)
        response = self.client.post(f"/admin/blog/appointment/{self.own.pk}/change/", {
            "status": "confirmed", "duration": 30, "diagnoses": [], "_save": "Сақтау"})
        self.assertEqual(response.status_code, 200)
        self.own.refresh_from_db()
        self.assertEqual(self.own.status, "planned")
        self.client.post("/admin/blog/appointment/", {
            "action": "confirm_selected", "_selected_action": [self.own.pk]})
        self.own.refresh_from_db()
        self.assertEqual(self.own.status, "planned")

    def test_setup_roles_is_repeatable_and_grants_no_user_management(self):
        call_command("setup_roles", stdout=StringIO())
        self.assertEqual(Group.objects.filter(name__in=["patient", "doctor", "registrar"]).count(), 3)
        self.assertFalse(self.registrar.has_perm("accounts.change_user"))
        self.assertTrue(self.registrar.has_perm("blog.confirm_appointment"))
        self.assertFalse(self.doctor_user.has_perm("blog.confirm_appointment"))
