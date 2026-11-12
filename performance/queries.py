from django.db.models import Count
from blog.access import visible_appointments
from blog.models import Appointment


def base_queryset(user):
    return visible_appointments(user, Appointment.objects.filter(is_training=True, status=Appointment.Status.PLANNED)).order_by("-date")


def slow_rows(user):
    return base_queryset(user)[:50]


def optimized_rows(user):
    from django.db.models import Subquery
    from blog.models import Appointment
    # Limit the inner query before grouping note counts: aggregate only 50 appointments.
    first_ids = base_queryset(user).values("pk")[:50]
    return (Appointment.objects.filter(pk__in=Subquery(first_ids)).order_by("-date").select_related("doctor", "patient")
            .prefetch_related("diagnoses").annotate(n_notes=Count("notes"))
            .defer("reason")[:50])
