"""Only this explicit projection of the clinic schema is exposed to the model."""
from blog.models import Appointment, Doctor, Patient

SCHEMA = "clinic_reports"
VIEW_MODELS = {
    "report_doctors": (Doctor, ("id", "full_name", "specialty")),
    "report_patients": (Patient, ("id",)),
    "report_appointments": (Appointment, ("id", "doctor_id", "patient_id", "date", "price", "duration", "status")),
}


def allowed_columns():
    return {view: set(columns) for view, (_, columns) in VIEW_MODELS.items()}


def schema_text():
    lines = []
    for view, (model, columns) in VIEW_MODELS.items():
        fields = {field.column: field for field in model._meta.concrete_fields}
        lines.append(view + "(" + ", ".join(
            f"{column}: {fields[column].get_internal_type()}" for column in columns
        ) + ")")
    lines += [
        "report_appointments.doctor_id -> report_doctors.id",
        "report_appointments.patient_id -> report_patients.id",
    ]
    return "\n".join(lines)
