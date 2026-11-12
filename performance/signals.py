from django.db import transaction
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from blog.models import Appointment, AppointmentNote, Diagnosis, Doctor, Patient
from .cache import invalidate


@receiver([post_save, post_delete], sender=Appointment)
@receiver([post_save, post_delete], sender=AppointmentNote)
@receiver([post_save, post_delete], sender=Diagnosis)
@receiver([post_save, post_delete], sender=Doctor)
@receiver([post_save, post_delete], sender=Patient)
def changed(sender, **kwargs):
    # Avoid publishing a cache revision before the transaction is committed.
    transaction.on_commit(invalidate)


@receiver(m2m_changed, sender=Appointment.diagnoses.through)
def diagnoses_changed(sender, action, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"}:
        transaction.on_commit(invalidate)
