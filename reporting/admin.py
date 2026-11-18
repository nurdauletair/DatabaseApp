from django.contrib import admin
from .models import QueryLog


@admin.register(QueryLog)
class QueryLogAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "user", "status", "row_count", "duration_ms", "model")
    list_filter = ("status", "prompt_version", "created_at")
    readonly_fields = tuple(f.name for f in QueryLog._meta.fields)
    list_select_related = ("user",)

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
