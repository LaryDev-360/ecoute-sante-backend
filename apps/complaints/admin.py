from django.contrib import admin

from apps.complaints.models import (
    Complaint,
    ComplaintAssignment,
    ComplaintAttachment,
    ComplaintCategory,
    ComplaintComment,
    ComplaintStatusHistory,
)


@admin.register(ComplaintCategory)
class ComplaintCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "active")
    list_filter = ("active",)
    search_fields = ("name",)


class ComplaintAttachmentInline(admin.TabularInline):
    model = ComplaintAttachment
    extra = 0


class ComplaintCommentInline(admin.TabularInline):
    model = ComplaintComment
    extra = 0
    readonly_fields = ("created_at",)


class ComplaintStatusHistoryInline(admin.TabularInline):
    model = ComplaintStatusHistory
    extra = 0
    readonly_fields = ("old_status", "new_status", "changed_by", "reason", "created_at")


class ComplaintAssignmentInline(admin.TabularInline):
    model = ComplaintAssignment
    extra = 0
    readonly_fields = ("assigned_at",)


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "title",
        "submitter_profile",
        "facility",
        "current_status",
        "severity",
        "complaint_type",
        "created_at",
    )
    list_filter = (
        "current_status",
        "severity",
        "complaint_type",
        "submission_type",
        "submitter_profile",
        "facility",
    )
    search_fields = ("reference", "title", "phone", "email")
    readonly_fields = ("reference", "created_at", "updated_at")
    autocomplete_fields = ("submitted_by", "reported_agent")
    inlines = [
        ComplaintStatusHistoryInline,
        ComplaintCommentInline,
        ComplaintAttachmentInline,
        ComplaintAssignmentInline,
    ]


@admin.register(ComplaintStatusHistory)
class ComplaintStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("complaint", "old_status", "new_status", "changed_by", "created_at")
    list_filter = ("new_status",)
    search_fields = ("complaint__reference",)


@admin.register(ComplaintComment)
class ComplaintCommentAdmin(admin.ModelAdmin):
    list_display = ("complaint", "author", "created_at")
    search_fields = ("complaint__reference", "comment")


@admin.register(ComplaintAttachment)
class ComplaintAttachmentAdmin(admin.ModelAdmin):
    list_display = ("complaint", "file", "uploaded_at")


@admin.register(ComplaintAssignment)
class ComplaintAssignmentAdmin(admin.ModelAdmin):
    list_display = ("complaint", "assigned_to", "assigned_at")
    search_fields = ("complaint__reference", "assigned_to__username")
