import secrets
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from blog.models import Appointment, Doctor, Patient


class Command(BaseCommand):
    help = "Create clinic demo accounts with generated passwords saved to a private local file."

    def add_arguments(self, parser):
        parser.add_argument("--credentials-file", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        target = Path(options["credentials_file"])
        if target.exists():
            raise CommandError("Credentials file already exists; choose another filename.")
        call_command("setup_roles", stdout=self.stdout)
        rows = []
        users = {}
        User = get_user_model()
        for role in ("patient", "doctor", "registrar", "admin"):
            username = f"demo_{role}"
            if User.objects.filter(username=username).exists():
                raise CommandError(f"{username} already exists; existing passwords have not been changed.")
            password = secrets.token_urlsafe(18)
            user = User.objects.create_user(username, password=password, is_staff=role != "patient",
                                            is_superuser=role == "admin")
            if role != "admin":
                user.groups.add(Group.objects.get(name=role))
            users[role] = user
            rows.append(f"{username}: {password}")
        doctor = Doctor.objects.filter(user__isnull=True).first()
        if doctor is None:
            doctor = Doctor.objects.create(full_name="Демо Дәрігер")
        doctor.user = users["doctor"]
        doctor.save(update_fields=["user"])
        patient = Patient.objects.create(user=users["patient"], full_name="Демо Науқас", birth_date="2000-01-01")
        Appointment.objects.create(doctor=doctor, patient=patient, date=timezone.now() + timedelta(days=1))
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8") as stream:
            target.chmod(0o600)
            stream.write("Учебные аккаунты клиники (локально, не добавлять в Git)\n\n" + "\n".join(rows) + "\n")
        self.stdout.write(self.style.SUCCESS(f"Created 4 accounts. Credentials: {target}"))
