import json
import os
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import MagicMock, patch
import httpx
import psycopg
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from openai import AuthenticationError
from blog.models import Appointment, Doctor, Patient
from .executor import run_readonly
from .guard import NoAnswer, ReportError, UnsafeSQL, extract_sql, validate_sql
from .llm import SQLAnswer, ask_sql
from .models import QueryLog
from .prompts import system_prompt


class GuardTests(SimpleTestCase):
    def test_limits_and_qualifies_only_approved_schema(self):
        self.assertEqual(validate_sql("SELECT id FROM report_doctors"), "SELECT id FROM clinic_reports.report_doctors LIMIT 100")
        self.assertTrue(validate_sql("SELECT id FROM report_doctors LIMIT 100000").endswith("LIMIT 100"))
        self.assertTrue(validate_sql("SELECT id FROM report_doctors LIMIT 5;").endswith("LIMIT 5"))

    def test_extracts_complete_markdown_only(self):
        self.assertEqual(extract_sql("```sql\nSELECT COUNT(*) FROM report_patients\n```"), "SELECT COUNT(*) FROM report_patients")
        with self.assertRaises(UnsafeSQL):
            validate_sql(extract_sql("Here is SQL: SELECT id FROM report_doctors"))

    def test_blocks_mutations_and_multistatement(self):
        for sql in ("DELETE FROM blog_appointment", "DROP TABLE blog_patient", "UPDATE blog_doctor SET full_name='x'",
                    "SELECT id FROM report_doctors; DELETE FROM blog_doctor", "COPY blog_patient TO STDOUT",
                    "WITH x AS (DELETE FROM blog_patient RETURNING *) SELECT * FROM x",
                    "SELECT id INTO stolen FROM report_doctors", "SELECT id FROM report_doctors FOR UPDATE"):
            with self.subTest(sql=sql), self.assertRaises(UnsafeSQL):
                validate_sql(sql)

    def test_blocks_data_exfiltration_and_function_side_effects(self):
        for sql in ("SELECT password FROM accounts_user", "SELECT full_name FROM report_patients",
                    "SELECT phone FROM report_doctors", "SELECT reason FROM report_appointments",
                    "SELECT id FROM public.report_doctors", "SELECT id FROM pg_catalog.pg_authid",
                    "SELECT pg_read_file('/etc/passwd') FROM report_doctors",
                    "SELECT pg_sleep(5) FROM report_doctors", "SELECT nextval('x') FROM report_doctors",
                    "SELECT set_config('transaction_read_only','off',false) FROM report_doctors",
                    "SELECT public.count(id) FROM report_doctors", "SELECT id::regclass FROM report_doctors",
                    "SELECT current_user FROM report_doctors", "SELECT id FROM report_doctors -- comment",
                    "SELECT * FROM report_doctors", "SELECT id FROM report_doctors LIMIT ALL"):
            with self.subTest(sql=sql), self.assertRaises(UnsafeSQL):
                validate_sql(sql)

    def test_blocks_nested_queries_unknown_columns_and_complexity(self):
        for sql in ("SELECT (SELECT password FROM accounts_user) FROM report_doctors",
                    "SELECT id FROM report_doctors UNION SELECT id FROM report_patients",
                    "WITH x AS (SELECT id FROM report_doctors) SELECT id FROM x",
                    "SELECT made_up FROM report_doctors", "SELECT id FROM report_doctors d JOIN report_appointments a ON d.id=a.doctor_id",
                    "SELECT d.id FROM report_doctors d CROSS JOIN report_patients p"):
            with self.subTest(sql=sql), self.assertRaises(UnsafeSQL):
                validate_sql(sql)

    def test_ordinary_literals_are_not_mistaken_for_commands(self):
        sql = validate_sql("SELECT full_name FROM report_doctors WHERE full_name = 'DROP DELETE; UPDATE'")
        self.assertIn("'DROP DELETE; UPDATE'", sql)

    def test_refusal(self):
        with self.assertRaises(NoAnswer):
            validate_sql("SELECT 'NO_ANSWER'")

    def test_all_ten_references_and_both_prompts(self):
        cases = json.loads((settings.BASE_DIR / "reporting/golden.json").read_text())
        self.assertEqual(len(cases), 10)
        self.assertEqual([sum(c["difficulty"] == d for c in cases) for d in ("easy", "medium", "hard")], [3, 4, 3])
        for case in cases:
            with self.subTest(case=case["id"]):
                checked = validate_sql(case["sql"])
                self.assertEqual(validate_sql(checked), checked)
        self.assertNotIn("Статусы приёма:", system_prompt("baseline"))
        self.assertIn("Статусы приёма:", system_prompt("enhanced"))


@override_settings(OPENAI_API_KEY="test-key-do-not-use", OPENAI_MODEL="gpt-5.4-mini")
class LLMTests(SimpleTestCase):
    @patch("reporting.llm.OpenAI")
    def test_official_endpoint_no_storage_retries_or_tools(self, factory):
        client = factory.return_value.__enter__.return_value
        client.responses.create.return_value = SimpleNamespace(status="completed", output_text="SELECT COUNT(*) FROM report_patients", usage=SimpleNamespace(input_tokens=100, output_tokens=20))
        answer = ask_sql("Сколько пациентов?")
        self.assertEqual(answer.input_tokens, 100)
        self.assertIn("LIMIT 100", answer.sql)
        factory.assert_called_once_with(api_key="test-key-do-not-use", base_url="https://api.openai.com/v1", timeout=20.0, max_retries=0)
        params = client.responses.create.call_args.kwargs
        self.assertFalse(params["store"])
        self.assertEqual(params["max_output_tokens"], 700)
        self.assertNotIn("tools", params)
        self.assertNotIn("test-key-do-not-use", params["instructions"])

    @override_settings(OPENAI_API_KEY="")
    @patch("reporting.llm.OpenAI")
    def test_missing_key_never_calls_provider(self, factory):
        with self.assertRaises(ReportError):
            ask_sql("Пациенты?")
        factory.assert_not_called()

    @patch("reporting.llm.OpenAI")
    def test_rejects_malicious_llm_response(self, factory):
        factory.return_value.__enter__.return_value.responses.create.return_value = SimpleNamespace(status="completed", output_text="DELETE FROM blog_patient")
        with self.assertRaises(UnsafeSQL):
            ask_sql("Удалить всё")

    @patch("reporting.llm.OpenAI")
    def test_authentication_errors_do_not_leak_key_or_provider_text(self, factory):
        response = httpx.Response(401, request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
        factory.return_value.__enter__.return_value.responses.create.side_effect = AuthenticationError("SECRET PROVIDER TEXT test-key-do-not-use", response=response, body={})
        with self.assertRaises(ReportError) as error:
            ask_sql("Врачи?")
        self.assertNotIn("SECRET", str(error.exception))
        self.assertNotIn("test-key", str(error.exception))


@override_settings(OPENAI_API_KEY="test-key-do-not-use", REPORT_DATABASE={"password": "fake-local-only"})
class ReportViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("setup_roles", stdout=StringIO())
        User = get_user_model()
        cls.admin = User.objects.create_superuser("report_admin", password="Test-Report-123!")
        cls.registrar = User.objects.create_user("report_registrar", is_staff=True)
        cls.registrar.groups.add(Group.objects.get(name="registrar"))
        cls.doctor = User.objects.create_user("report_doctor", is_staff=True)
        cls.doctor.groups.add(Group.objects.get(name="doctor"))
        cls.patient = User.objects.create_user("report_patient")
        cls.patient.groups.add(Group.objects.get(name="patient"))

    def test_access_and_navigation_permissions(self):
        self.assertEqual(self.client.get("/report/").status_code, 302)
        for user in (self.doctor, self.patient):
            self.client.force_login(user)
            self.assertEqual(self.client.get("/report/").status_code, 403)
            self.assertNotContains(self.client.get("/"), 'href="/report/"')
        for user in (self.admin, self.registrar):
            self.client.force_login(user)
            response = self.client.get("/report/")
            self.assertContains(response, "Есептер")
            self.assertNotContains(response, "test-key-do-not-use")
            self.assertIn("no-store", response["Cache-Control"])

    @override_settings(OPENAI_API_KEY="")
    @patch("reporting.views.ask_sql")
    def test_setup_state_has_no_key_form_or_api_call(self, ask):
        self.client.force_login(self.admin)
        response = self.client.get("/report/")
        self.assertContains(response, "әзірге қосылмаған")
        self.assertNotContains(response, "OPENAI_API_KEY")
        response = self.client.post("/report/", {"question": "Врачи?"})
        self.assertEqual(response.status_code, 200)
        ask.assert_not_called()
        self.assertEqual(QueryLog.objects.get().status, "unavailable")

    @patch("reporting.views.run_readonly", return_value=(["total"], [(12,)]))
    @patch("reporting.views.ask_sql", return_value=SQLAnswer("SELECT COUNT(*) FROM clinic_reports.report_patients LIMIT 100", 10, 5))
    def test_post_shows_table_sql_and_audit(self, ask, execute):
        self.client.force_login(self.registrar)
        response = self.client.post("/report/", {"question": "Сколько пациентов?"})
        self.assertContains(response, "12")
        self.assertContains(response, "SELECT COUNT(*)")
        log = QueryLog.objects.get()
        self.assertEqual((log.user, log.status, log.row_count, log.input_tokens), (self.registrar, "success", 1, 10))

    @patch("reporting.views.run_readonly", return_value=(["id"], []))
    @patch("reporting.views.ask_sql", return_value=SQLAnswer("SELECT id FROM clinic_reports.report_patients LIMIT 100"))
    def test_empty_result_and_get_never_generates(self, ask, execute):
        self.client.force_login(self.admin)
        self.client.get("/report/")
        ask.assert_not_called()
        self.assertFalse(QueryLog.objects.exists())
        response = self.client.post("/report/", {"question": "Пациенты?"})
        self.assertContains(response, "Деректер табылмады")

    @patch("reporting.views.run_readonly")
    @patch("reporting.views.ask_sql", side_effect=UnsafeSQL("Тек бір SELECT сұранысына рұқсат."))
    def test_unsafe_answer_never_reaches_executor(self, ask, execute):
        self.client.force_login(self.admin)
        response = self.client.post("/report/", {"question": "Удалить всё"})
        self.assertContains(response, "Тек бір SELECT")
        execute.assert_not_called()
        self.assertEqual(QueryLog.objects.get().status, "rejected")

    @patch("reporting.views.ask_sql")
    def test_blank_and_oversized_input_never_calls_api(self, ask):
        self.client.force_login(self.admin)
        for question in ("  ", "x" * 301):
            self.assertEqual(self.client.post("/report/", {"question": question}).status_code, 200)
        ask.assert_not_called()

    @override_settings(REPORT_REQUESTS_PER_MINUTE=1)
    @patch("reporting.views.run_readonly", return_value=(["total"], [(0,)]))
    @patch("reporting.views.ask_sql", return_value=SQLAnswer("SELECT COUNT(*) FROM clinic_reports.report_patients LIMIT 100"))
    def test_persistent_rate_limit_and_csrf(self, ask, execute):
        self.client.force_login(self.admin)
        self.client.post("/report/", {"question": "Сколько пациентов?"})
        response = self.client.post("/report/", {"question": "Сколько пациентов?"})
        self.assertContains(response, "лимиті")
        self.assertEqual(ask.call_count, 1)
        from django.test import Client
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.admin)
        self.assertEqual(protected.post("/report/", {"question": "Врачи?"}).status_code, 403)

    @patch("reporting.views.run_readonly", return_value=(["name"], [("<script>alert(1)</script>",)]))
    @patch("reporting.views.ask_sql", return_value=SQLAnswer("SELECT full_name FROM clinic_reports.report_doctors LIMIT 100"))
    def test_results_are_html_escaped(self, ask, execute):
        self.client.force_login(self.admin)
        response = self.client.post("/report/", {"question": "Имена врачей?"})
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")


class ExecutorFailClosedTests(SimpleTestCase):
    @override_settings(REPORT_DATABASE={"password": ""})
    @patch("reporting.executor.psycopg.connect")
    def test_missing_reader_does_not_fall_back_to_owner(self, connect):
        with self.assertRaises(ReportError):
            run_readonly("SELECT COUNT(*) FROM report_patients")
        connect.assert_not_called()

    @patch("reporting.executor.psycopg.connect")
    def test_validates_even_direct_calls(self, connect):
        with self.assertRaises(UnsafeSQL):
            run_readonly("DELETE FROM blog_patient")
        connect.assert_not_called()


@skipUnless(os.environ.get("REPORT_INTEGRATION_TESTS") == "1", "Enable REPORT_INTEGRATION_TESTS=1 with a provisioned local reader")
class PostgreSQLReaderTests(TransactionTestCase):
    def setUp(self):
        from django.db import connection
        from psycopg import sql
        self.config = {**settings.REPORT_DATABASE, "dbname": connection.settings_dict["NAME"]}
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA clinic_reports TO {}").format(sql.Identifier(self.config["user"])))
            cursor.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA clinic_reports TO {}").format(sql.Identifier(self.config["user"])))
        self.doctor = Doctor.objects.create(full_name="Integration Doctor")
        self.patient = Patient.objects.create(full_name="PRIVATE PATIENT", birth_date="1990-01-01")
        for training in (False, True):
            Appointment.objects.create(doctor=self.doctor, patient=self.patient, date=timezone.now(), is_training=training, status="done", price=1000)

    def test_real_executor_reads_views_excludes_training_and_no_private_fields(self):
        with override_settings(REPORT_DATABASE=self.config):
            cols, rows = run_readonly("SELECT COUNT(*) AS total FROM report_appointments")
        self.assertEqual((cols, rows), (["total"], [(1,)]))
        with psycopg.connect(**self.config) as conn:
            columns = [c.name for c in conn.execute("SELECT * FROM clinic_reports.report_patients").description]
            self.assertEqual(columns, ["id"])

    def test_database_rejects_writes_and_source_reads_even_without_guard(self):
        for query in ("SELECT password FROM public.accounts_user", "SELECT reason FROM public.blog_appointment",
                      "UPDATE public.blog_doctor SET full_name=full_name WHERE FALSE",
                      "DELETE FROM clinic_reports.report_appointments WHERE FALSE",
                      "CREATE TABLE public.report_test_forbidden(id int)"):
            with self.subTest(query=query), psycopg.connect(**self.config, autocommit=True) as conn:
                # Disable the default transaction flag on purpose: GRANTs must protect data independently.
                conn.execute("SET default_transaction_read_only=off")
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    conn.execute(query)
