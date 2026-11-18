from django import forms


class AskForm(forms.Form):
    question = forms.CharField(
        label="Емхана деректері бойынша сұрағыңыз", max_length=300,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Мысалы: әр дәрігерде қанша қабылдау бар?", "maxlength": 300}),
        help_text="Тек деректерді қарау және статистика. Жеке деректерді енгізбеңіз.",
    )
