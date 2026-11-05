from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Емхана рөлдері мен рұқсаттарын құру/жаңарту (қайта іске қосуға болады)."

    @transaction.atomic
    def handle(self, *args, **options):
        roles = {
            "patient": ["view_doctor", "view_patient", "view_appointment", "book_appointment"],
            "doctor": ["view_doctor", "view_patient", "view_appointment", "change_appointment", "view_diagnosis"],
            "registrar": list(Permission.objects.filter(content_type__app_label="blog").exclude(codename="book_appointment")
                              .values_list("codename", flat=True)),
        }
        for name, codenames in roles.items():
            group, _ = Group.objects.get_or_create(name=name)
            group.permissions.set(Permission.objects.filter(
                content_type__app_label="blog", codename__in=codenames))
            self.stdout.write(self.style.SUCCESS(f"{name}: {group.permissions.count()} рұқсат"))
