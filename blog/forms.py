import datetime
import re

from django import forms
from django.utils import timezone

from .models import Appointment, Doctor, Patient

DT_FORMATS = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"]


def clean_two_words(value):
    """Бос орындарды тазалап, кемінде екі сөзді талап етеді."""
    name = " ".join(value.split())
    if len(name.split()) < 2:
        raise forms.ValidationError("Аты-жөні кемінде екі сөзден тұруы керек.")
    return name


class AppointmentForm(forms.ModelForm):
    date = forms.DateTimeField(
        label="Қабылдау уақыты",
        input_formats=DT_FORMATS,
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"}, format=DT_FORMATS[0]),
    )

    class Meta:
        model = Appointment
        fields = ["doctor", "patient", "diagnoses", "date",
                  "price", "duration", "status"]
        widgets = {"diagnoses": forms.CheckboxSelectMultiple(attrs={"class": "checks"})}

    def clean_duration(self):
        duration = self.cleaned_data["duration"]
        if duration < 10:
            raise forms.ValidationError("Қабылдау кемінде 10 минут болуы керек.")
        if duration > 240:
            raise forms.ValidationError("Қабылдау 240 минуттан аспауы керек.")
        return duration

    def clean_date(self):
        date = self.cleaned_data["date"]
        if date > timezone.now() + datetime.timedelta(days=365):
            raise forms.ValidationError(
                "Қабылдауды 1 жылдан артық алдын ала жоспарлауға болмайды.")
        return date

    def clean(self):
        data = super().clean()
        status, date = data.get("status"), data.get("date")
        if status == Appointment.Status.DONE and date and date > timezone.now():
            raise forms.ValidationError(
                "Болашақтағы қабылдау «Өтті» күйінде бола алмайды.")
        return data


class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ["full_name", "birth_date", "doctors"]
        widgets = {
            "birth_date": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"),
            "doctors": forms.CheckboxSelectMultiple(attrs={"class": "checks"}),
        }

    def clean_full_name(self):
        return clean_two_words(self.cleaned_data["full_name"])

    def clean_birth_date(self):
        birth_date = self.cleaned_data["birth_date"]
        if birth_date > datetime.date.today():
            raise forms.ValidationError("Туған күні болашақта бола алмайды.")
        if birth_date.year < 1900:
            raise forms.ValidationError("Туған күні 1900 жылдан кейін болуы керек.")
        return birth_date


class DoctorForm(forms.ModelForm):
    class Meta:
        model = Doctor
        fields = ["full_name", "specialty", "phone"]

    def clean_full_name(self):
        return clean_two_words(self.cleaned_data["full_name"])

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        if phone and not re.fullmatch(r"\+?\d{10,15}", phone):
            raise forms.ValidationError(
                "Телефон нөмірі +77001234567 форматында болуы керек.")
        return phone


SORT_CHOICES = [
    ("newest", "Жаңалары алдымен"),
    ("oldest", "Ескілері алдымен"),
    ("price_desc", "Бағасы: қымбаттан арзанға"),
    ("price_asc", "Бағасы: арзаннан қымбатқа"),
]
SORT_FIELDS = {
    "newest": "-date", "oldest": "date",
    "price_desc": "-price", "price_asc": "price",
}


class AppointmentFilterForm(forms.Form):
    """GET параметрлерін тексереді: қате мән сайтты құлатпайды."""
    q = forms.CharField(
        required=False, label="Іздеу",
        widget=forms.TextInput(attrs={"placeholder": "Науқас немесе дәрігер"}))
    status = forms.ChoiceField(
        required=False, label="Күйі",
        choices=[("", "Барлық күй")] + list(Appointment.Status.choices))
    doctor = forms.ModelChoiceField(
        required=False, label="Дәрігер", queryset=Doctor.objects.all(),
        empty_label="Барлық дәрігер")
    sort = forms.ChoiceField(required=False, label="Сұрыптау", choices=SORT_CHOICES)
