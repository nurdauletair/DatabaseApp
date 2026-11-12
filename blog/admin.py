from django.contrib import admin
from django.db.models import Count
from django.utils import timezone

from .access import manages_clinic, visible_appointments, visible_patients
from .forms import AppointmentForm

from .models import Appointment, AppointmentNote, Diagnosis, Doctor, Patient


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ["full_name", "specialty", "phone"]
    list_filter = ["specialty"]
    search_fields = ["full_name", "phone"]

    def get_readonly_fields(self, request, obj=None):
        return [] if request.user.is_superuser else ["user"]


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ["full_name", "birth_date"]
    list_filter = ["birth_date"]
    search_fields = ["full_name"]
    filter_horizontal = ["doctors"]

    def get_queryset(self, request):
        return visible_patients(request.user, super().get_queryset(request))

    def get_readonly_fields(self, request, obj=None):
        return [] if request.user.is_superuser else ["user"]


@admin.register(Diagnosis)
class DiagnosisAdmin(admin.ModelAdmin):
    list_display = ["name", "appointments_count"]
    search_fields = ["name"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _n=Count("appointments"))

    @admin.display(description="Қабылдау саны", ordering="_n")
    def appointments_count(self, obj):
        return obj._n


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    form = AppointmentForm
    list_display = ["patient", "doctor", "date", "price", "status"]
    list_filter = ["status", "doctor", "date"]
    search_fields = ["patient__full_name", "doctor__full_name"]
    list_select_related = ["patient", "doctor"]      # N+1 жоқ
    filter_horizontal = ["diagnoses"]
    date_hierarchy = "date"
    actions = ["mark_done", "confirm_selected"]

    def get_queryset(self, request):
        return visible_appointments(request.user, super().get_queryset(request))

    def get_form(self, request, obj=None, **kwargs):
        base_form = super().get_form(request, obj, **kwargs)

        class ScopedForm(base_form):
            def __init__(self, *args, **form_kwargs):
                form_kwargs["user"] = request.user
                super().__init__(*args, **form_kwargs)

        return ScopedForm

    def get_readonly_fields(self, request, obj=None):
        return [] if manages_clinic(request.user) else ["doctor", "patient", "date", "price"]

    @admin.action(description="Таңдалғандарды «Өтті» деп белгілеу", permissions=["change"])
    def mark_done(self, request, queryset):
        updated = queryset.filter(date__lte=timezone.now()).update(status=Appointment.Status.DONE)
        self.message_user(request, f"{updated} қабылдау аяқталды")

    def has_confirm_permission(self, request):
        return request.user.has_perm("blog.confirm_appointment")

    @admin.action(description="Жоспарланған қабылдауларды растау", permissions=["confirm"])
    def confirm_selected(self, request, queryset):
        updated = queryset.filter(status=Appointment.Status.PLANNED).update(status=Appointment.Status.CONFIRMED)
        self.message_user(request, f"{updated} қабылдау расталды")


admin.site.site_header = "Емхана әкімшілігі"
admin.site.site_title = "Емхана"
admin.site.index_title = "Басқару панелі"


@admin.register(AppointmentNote)
class AppointmentNoteAdmin(admin.ModelAdmin):
    list_display = ["id", "appointment", "text"]
    list_select_related = ["appointment__doctor", "appointment__patient"]
    search_fields = ["text"]

    def get_queryset(self, request):
        ids = visible_appointments(request.user, Appointment.objects.all()).values("pk")
        return super().get_queryset(request).filter(appointment_id__in=ids)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "appointment":
            kwargs["queryset"] = visible_appointments(request.user, Appointment.objects.all()).select_related("doctor", "patient")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
