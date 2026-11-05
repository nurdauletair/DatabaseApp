from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "email", "phone", "role_label", "is_active", "is_staff"]
    fieldsets = BaseUserAdmin.fieldsets + (("Емхана", {"fields": ("phone",)}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (("Емхана", {"fields": ("phone", "email")}),)
