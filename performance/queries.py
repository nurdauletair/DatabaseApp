from django.db.models import Count
from blog.access import visible_appointments
from blog.models import Appointment


def base_queryset(user):
    return visible_appointments(user, Appointment.objects.filter(is_training=True, status=Appointment.Status.PLANNED)).order_by("-date")


def slow_rows(user):
    return base_queryset(user)[:50]
