import django_filters

from apps.complaints.models import Complaint


class HospitalComplaintFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="current_status")
    category = django_filters.NumberFilter(field_name="category_id")
    service = django_filters.NumberFilter(field_name="service_id")
    severity = django_filters.CharFilter()
    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = Complaint
        fields = ["status", "category", "service", "severity", "date_from", "date_to"]
