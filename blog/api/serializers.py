import datetime
import re

from django.utils import timezone
from rest_framework import serializers

from blog.models import Appointment, Diagnosis, Doctor, Patient


def two_words(value):
    """Аты-жөні кемінде екі сөзден тұруы керек (формадағы ереже сияқты)."""
    name = " ".join(value.split())
    if len(name.split()) < 2:
        raise serializers.ValidationError("Аты-жөні кемінде екі сөзден тұруы керек.")
    return name


class DiagnosisSerializer(serializers.ModelSerializer):
    class Meta:
        model = Diagnosis
        fields = ["id", "name"]


class DoctorShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = ["id", "full_name", "specialty"]


class PatientShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ["id", "full_name"]


class DoctorSerializer(serializers.ModelSerializer):
    appointments_count = serializers.SerializerMethodField()

    class Meta:
        model = Doctor
        fields = ["id", "full_name", "specialty", "phone", "appointments_count"]

    def get_appointments_count(self, obj):
        # ViewSet-те annotate бар болса — дайын мән, әйтпесе (POST жауабы) санаймыз
        count = getattr(obj, "n_appointments", None)
        return obj.appointments.count() if count is None else count

    def validate_full_name(self, value):
        return two_words(value)

    def validate_phone(self, value):
        value = value.strip()
        if value and not re.fullmatch(r"\+?\d{10,15}", value):
            raise serializers.ValidationError(
                "Телефон нөмірі +77001234567 форматында болуы керек.")
        return value


class PatientSerializer(serializers.ModelSerializer):
    # оқу мен жазу бөлек: жауапта — дәрігер объектілері, сұраныста — doctor_ids
    doctors = DoctorShortSerializer(many=True, read_only=True)
    doctor_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Doctor.objects.all(), source="doctors",
        write_only=True, required=False)
    appointments_count = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = ["id", "full_name", "birth_date", "doctors", "doctor_ids",
                  "appointments_count"]

    def get_appointments_count(self, obj):
        count = getattr(obj, "n_appointments", None)
        return obj.appointments.count() if count is None else count

    def validate_full_name(self, value):
        return two_words(value)

    def validate_birth_date(self, value):
        if value > datetime.date.today():
            raise serializers.ValidationError("Туған күні болашақта бола алмайды.")
        if value.year < 1900:
            raise serializers.ValidationError("Туған күні 1900 жылдан кейін болуы керек.")
        return value


class AppointmentSerializer(serializers.ModelSerializer):
    doctor = DoctorShortSerializer(read_only=True)
    doctor_id = serializers.PrimaryKeyRelatedField(
        queryset=Doctor.objects.all(), source="doctor", write_only=True)
    patient = PatientShortSerializer(read_only=True)
    patient_id = serializers.PrimaryKeyRelatedField(
        queryset=Patient.objects.all(), source="patient", write_only=True)
    diagnoses = serializers.SlugRelatedField(
        many=True, slug_field="name", queryset=Diagnosis.objects.all(),
        required=False)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Appointment
        fields = ["id", "doctor", "doctor_id", "patient", "patient_id",
                  "diagnoses", "date", "price", "duration", "status",
                  "status_display"]

    def validate_duration(self, value):
        if value < 10:
            raise serializers.ValidationError("Қабылдау кемінде 10 минут болуы керек.")
        if value > 240:
            raise serializers.ValidationError("Қабылдау 240 минуттан аспауы керек.")
        return value

    def validate_date(self, value):
        if value > timezone.now() + datetime.timedelta(days=365):
            raise serializers.ValidationError(
                "Қабылдауды 1 жылдан артық алдын ала жоспарлауға болмайды.")
        return value

    def validate(self, attrs):
        status = attrs.get("status", getattr(self.instance, "status", None))
        date = attrs.get("date", getattr(self.instance, "date", None))
        if status == Appointment.Status.DONE and date and date > timezone.now():
            raise serializers.ValidationError(
                "Болашақтағы қабылдау «Өтті» күйінде бола алмайды.")
        return attrs
