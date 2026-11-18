from django.db import migrations


def create_views(apps, schema_editor):
    postgres = schema_editor.connection.vendor == "postgresql"
    prefix = "clinic_reports." if postgres else ""
    if postgres:
        schema_editor.execute("CREATE SCHEMA clinic_reports")
    definitions = {
        "report_doctors": "SELECT id, full_name, specialty FROM blog_doctor",
        "report_patients": "SELECT id FROM blog_patient",
        "report_appointments": "SELECT id, doctor_id, patient_id, date, price, duration, status FROM blog_appointment WHERE NOT is_training",
    }
    for name, query in definitions.items():
        schema_editor.execute(f"CREATE VIEW {prefix}{name} AS {query}")


def drop_views(apps, schema_editor):
    postgres = schema_editor.connection.vendor == "postgresql"
    prefix = "clinic_reports." if postgres else ""
    for name in ("report_appointments", "report_patients", "report_doctors"):
        schema_editor.execute(f"DROP VIEW {prefix}{name}")
    if postgres:
        schema_editor.execute("DROP SCHEMA clinic_reports")


class Migration(migrations.Migration):
    dependencies = [("reporting", "0001_initial"), ("blog", "0006_appointment_status_date_idx")]
    operations = [migrations.RunPython(create_views, drop_views)]
