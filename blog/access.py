"""Shared data visibility rules for HTML, API, aggregates and admin."""
from django.core.exceptions import PermissionDenied
from django.db.models import Q


def manages_clinic(user):
    return user.is_authenticated and user.has_perm("blog.manage_clinic")


def appointment_condition(user, prefix=""):
    if not user.is_authenticated:
        return Q(**{prefix + "pk__in": []})
    if manages_clinic(user):
        return Q()
    return (Q(**{prefix + "doctor__user_id": user.pk}) |
            Q(**{prefix + "patient__user_id": user.pk}))


def visible_appointments(user, queryset):
    return queryset.filter(appointment_condition(user))


def visible_patients(user, queryset):
    if manages_clinic(user):
        return queryset
    return queryset.filter(Q(user_id=user.pk) | Q(appointments__doctor__user_id=user.pk)).distinct()


def check_appointment(user, appointment):
    if not visible_appointments(user, type(appointment).objects.filter(pk=appointment.pk)).exists():
        raise PermissionDenied("Бұл қабылдауға қол жеткізуге рұқсат жоқ.")


def check_clinical_changes(user, original, cleaned):
    """Doctors can update clinical fields of their appointments, never reassign or confirm."""
    if manages_clinic(user):
        return
    if "doctor" in cleaned and cleaned["doctor"].pk != original.doctor_id:
        raise PermissionDenied("Қабылдаудың дәрігерін өзгертуге болмайды.")
    if "patient" in cleaned and cleaned["patient"].pk != original.patient_id:
        raise PermissionDenied("Қабылдаудың науқасын өзгертуге болмайды.")
    for field in ("price", "date"):
        if field in cleaned and cleaned[field] != getattr(original, field):
            raise PermissionDenied("Қабылдау уақыты мен бағасын тіркеуші өзгертеді.")
    if cleaned.get("status") == "confirmed" and original.status != "confirmed":
        raise PermissionDenied("Қабылдауды тек тіркеуші растайды.")
