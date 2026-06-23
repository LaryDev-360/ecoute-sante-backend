from django.contrib import admin

from apps.audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "resource_label", "actor", "facility")
    list_filter = ("action", "resource_type", "facility")
    search_fields = ("summary", "resource_label", "actor__username")
    readonly_fields = (
        "actor",
        "action",
        "resource_type",
        "resource_id",
        "resource_label",
        "summary",
        "metadata",
        "facility",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
