from django.db import models
from django_filters import rest_framework as filters

from apps.audit.models import AuditLog


class AuditLogFilter(filters.FilterSet):
    action = filters.CharFilter(field_name="action")
    actor = filters.NumberFilter(field_name="actor_id")
    resource_type = filters.CharFilter(field_name="resource_type")
    resource_id = filters.CharFilter(field_name="resource_id")
    complaint_id = filters.NumberFilter(method="filter_complaint_id")
    date_from = filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    date_to = filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    search = filters.CharFilter(method="filter_search")

    class Meta:
        model = AuditLog
        fields = ("action", "actor", "resource_type", "resource_id", "complaint_id")

    def filter_complaint_id(self, queryset, name, value):
        if value is None:
            return queryset
        return queryset.filter(resource_type="complaint", resource_id=str(value))

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            models.Q(summary__icontains=value)
            | models.Q(resource_label__icontains=value)
            | models.Q(actor__username__icontains=value)
            | models.Q(actor__first_name__icontains=value)
            | models.Q(actor__last_name__icontains=value)
        )
