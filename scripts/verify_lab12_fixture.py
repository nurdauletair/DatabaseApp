"""Replay saved model SQL on a disposable PostgreSQL database; never calls an LLM."""
import argparse
from collections import Counter
from datetime import timedelta
from decimal import Decimal
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.conf import settings
from django.db import connection
from django.test import override_settings
from django.test.runner import DiscoverRunner
from django.utils import timezone
from psycopg import sql
from blog.models import Appointment, Doctor, Patient
from reporting.executor import run_readonly
from reporting.guard import ReportError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation", default=".local-backups/report-evaluation.json")
    parser.add_argument("--output", default="evidence/lab12/fixture-check.json")
    options = parser.parse_args()
    source = ROOT / options.evaluation
    evaluation = json.loads(source.read_text())
    if not evaluation.get("complete") or not evaluation.get("llm_evaluated"):
        raise SystemExit("A completed real evaluation is required; no API will be called.")
    if connection.vendor != "postgresql":
        raise SystemExit("PostgreSQL required")
    live_name = connection.settings_dict["NAME"]
    previous_test_name = connection.settings_dict["TEST"].get("NAME")
    temporary_name = "lab12_eval_" + uuid.uuid4().hex[:12]
    connection.settings_dict["TEST"]["NAME"] = temporary_name
    runner = DiscoverRunner(verbosity=0, interactive=False)
    old_config = runner.setup_databases(aliases={"default"})
    result = {"checked_at": timezone.now().isoformat(), "api_calls_made": 0,
              "dataset": "Synthetic fixture in a newly created disposable PostgreSQL database",
              "purpose": "Detect vacuous passes on empty production reference results",
              "production_accuracy": evaluation["accuracy"], "cases": [], "accuracy": {}}
    try:
        assert connection.settings_dict["NAME"] == temporary_name
        doctors = Doctor.objects.bulk_create([
            Doctor(full_name=f"Сынақ Дәрігер {i+1}", specialty=Doctor.Specialty.values[i % 4])
            for i in range(7)
        ])
        patients = Patient.objects.bulk_create([
            Patient(full_name=f"Сынақ Науқас {i+1}", birth_date="1990-01-01") for i in range(7)
        ])
        month = timezone.localtime(timezone.now()).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        previous = (month - timedelta(days=1)).replace(day=1)
        older = (previous - timedelta(days=1)).replace(day=1)
        appointments = []

        def add(doctor, day, status, price, training=False):
            appointments.append(Appointment(doctor=doctors[doctor], patient=patients[doctor],
                date=day + timedelta(hours=12), status=status, price=Decimal(str(price)), is_training=training))

        for i in range(6):
            add(i, month + timedelta(days=i), "done", 1000 + i * 137)
            add(i, month + timedelta(days=i), "planned", 90000)
            add(i, month + timedelta(days=i), "cancelled", 80000)
            for day in range(i + 1):
                add(i, previous + timedelta(days=day), "done", 500 + i * 83)
            add(i, previous, "confirmed", 70000)
            add(i, older, "done", 60000)
        add(0, month, "done", 99000, training=True)
        Appointment.objects.bulk_create(appointments)
        role = settings.REPORT_DATABASE["user"]
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA clinic_reports TO {}").format(sql.Identifier(role)))
            cursor.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA clinic_reports TO {}").format(sql.Identifier(role)))
        config = {**settings.REPORT_DATABASE, "dbname": temporary_name}
        with override_settings(REPORT_DATABASE=config):
            totals = {"baseline": 0, "enhanced": 0}
            for case in evaluation["cases"]:
                _, expected = run_readonly(case["reference_sql"])
                assert expected, f"Reference #{case['id']} unexpectedly empty"
                row = {"id": case["id"], "reference_rows": len(expected), "empty_reference": False}
                for version in totals:
                    generated = case[version].get("sql", "")
                    try:
                        _, actual = run_readonly(generated)
                        good = Counter(actual) == Counter(expected)
                        row[version] = {"correct": good, "result_rows": len(actual),
                                        "error_type": "" if good else "result_mismatch"}
                    except ReportError as error:
                        good = False
                        row[version] = {"correct": False, "error_type": type(error).__name__, "error": str(error)}
                    totals[version] += int(good)
                result["cases"].append(row)
            result["accuracy"] = {v: {"correct": n, "total": len(evaluation["cases"]), "percent": n * 10}
                                  for v, n in totals.items()}
        result["fixture"] = {"doctors": len(doctors), "patients": len(patients),
            "appointments": len(appointments), "training_appointments": 1,
            "cases": ["Current month and previous calendar month", "Older month outlier", "All four statuses",
                      "One doctor without appointments", "Training visit excluded", "Unequal appointment counts and prices"]}
    finally:
        runner.teardown_databases(old_config)
        connection.settings_dict["TEST"]["NAME"] = previous_test_name
    assert connection.settings_dict["NAME"] == live_name
    result["temporary_database_removed"] = True
    result["production_database_unchanged"] = True
    output = ROOT / options.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"fixture_accuracy": result["accuracy"], "temporary_database_removed": True, "api_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
