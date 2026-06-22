from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.models import OTPVerification, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "role", "phone", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "email", "phone", "first_name", "last_name")
    ordering = ("username",)

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Santé Écoute", {"fields": ("phone", "role")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Santé Écoute", {"fields": ("phone", "role")}),
    )


@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "channel", "expires_at", "is_used", "attempts", "created_at")
    list_filter = ("purpose", "channel", "is_used")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("code_hash", "created_at")
