import uuid
from django.core.cache import cache
from django.db.models import Count, Subquery
from blog.access import manages_clinic, visible_appointments
from blog.models import Appointment, AppointmentNote, Diagnosis


def revision():
    return cache.get_or_set("clinic:revision", lambda: uuid.uuid4().hex, timeout=None)


def invalidate():
    cache.set("clinic:revision", uuid.uuid4().hex, timeout=None)


def scope_key(user):
    return f"{revision()}:{user.pk}:{int(manages_clinic(user))}"


def clinic_stats(user):
    def compute():
        appointments = visible_appointments(user, Appointment.objects.filter(is_training=True))
        ids = appointments.order_by().values("pk")
        return {
            "appointments": appointments.count(),
            "notes": AppointmentNote.objects.filter(appointment_id__in=Subquery(ids)).count(),
            "top_diagnoses": list(Diagnosis.objects.filter(appointments__pk__in=Subquery(ids))
                                  .values("name").annotate(n=Count("appointments"))
                                  .order_by("-n", "name")[:10]),
        }
    return cache.get_or_set("clinic:stats:" + scope_key(user), compute, timeout=600)
