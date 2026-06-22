from django.contrib import admin

from apps.facilities.models import Facility, FacilityService, UserFacilityAssignment


class FacilityServiceInline(admin.TabularInline):
    model = FacilityService
    extra = 1


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "facility_type", "region", "city", "active", "created_at")
    list_filter = ("facility_type", "region", "city", "active")
    search_fields = ("name", "code", "region", "city")
    inlines = [FacilityServiceInline]


@admin.register(FacilityService)
class FacilityServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "facility", "active")
    list_filter = ("active", "facility")
    search_fields = ("name", "facility__name", "facility__code")


@admin.register(UserFacilityAssignment)
class UserFacilityAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "facility", "assigned_at")
    list_filter = ("facility",)
    search_fields = ("user__username", "user__email", "facility__name", "facility__code")
    autocomplete_fields = ("user", "facility")
