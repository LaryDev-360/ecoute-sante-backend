import django_filters

from apps.facilities.models import Facility


class FacilityFilter(django_filters.FilterSet):
    code = django_filters.CharFilter(lookup_expr="iexact")
    region = django_filters.CharFilter(lookup_expr="icontains")
    city = django_filters.CharFilter(lookup_expr="icontains")
    facility_type = django_filters.CharFilter(lookup_expr="iexact")
    active = django_filters.BooleanFilter()

    class Meta:
        model = Facility
        fields = ["region", "city", "facility_type", "active"]
