from django import forms
from django.contrib.auth.forms import UserCreationForm

from blog.forms import clean_two_words, PatientForm, DoctorForm
from .models import User


class SignUpForm(UserCreationForm):
    full_name = forms.CharField(label="Аты-жөні", max_length=150)
    birth_date = forms.DateField(label="Туған күні", widget=forms.DateInput(attrs={"type": "date"}))

    class Meta:
        model = User
        fields = ["username", "full_name", "birth_date", "email", "phone", "password1", "password2"]

    def clean_full_name(self):
        return clean_two_words(self.cleaned_data["full_name"])

    def clean_birth_date(self):
        return PatientForm.clean_birth_date(self)

    def clean_phone(self):
        return DoctorForm.clean_phone(self)
