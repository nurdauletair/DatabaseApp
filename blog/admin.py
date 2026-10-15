from django.contrib import admin
from django.db.models import Count

from .models import Appointment, Diagnosis, Doctor, Patient


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ["full_name", "specialty", "phone"]
    list_filter = ["specialty"]
    search_fields = ["full_name", "phone"]


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ["full_name", "birth_date"]
    list_filter = ["birth_date"]
    search_fields = ["full_name"]
    filter_horizontal = ["doctors"]


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
    list_display = ["patient", "doctor", "date", "price", "status"]
    list_filter = ["status", "doctor", "date"]
    search_fields = ["patient__full_name", "doctor__full_name"]
    list_select_related = ["patient", "doctor"]      # N+1 жоқ
    filter_horizontal = ["diagnoses"]
    date_hierarchy = "date"
    actions = ["mark_done"]

    @admin.action(description="Таңдалғандарды «Өтті» деп белгілеу")
    def mark_done(self, request, queryset):
        updated = queryset.update(status=Appointment.Status.DONE)
        self.message_user(request, f"{updated} қабылдау аяқталды")


admin.site.site_header = "Емхана әкімшілігі"
admin.site.site_title = "Емхана"
admin.site.index_title = "Басқару панелі"
