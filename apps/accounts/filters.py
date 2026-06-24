from django_filters import rest_framework as filters

from apps.accounts.models import User, UserRole


class StaffUserFilter(filters.FilterSet):
    role = filters.ChoiceFilter(choices=UserRole.choices)
    facility = filters.NumberFilter(field_name="facility_assignment__facility_id")
    is_active = filters.BooleanFilter()
    search = filters.CharFilter(method="filter_search")

    class Meta:
        model = User
        fields = ("role", "facility", "is_active")

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        from django.db import models

        return queryset.filter(
            models.Q(username__icontains=value)
            | models.Q(email__icontains=value)
            | models.Q(first_name__icontains=value)
            | models.Q(last_name__icontains=value)
            | models.Q(phone__icontains=value)
        )
