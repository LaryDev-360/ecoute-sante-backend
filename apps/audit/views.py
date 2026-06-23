from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView

from apps.audit.filters import AuditLogFilter
from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer
from apps.audit.services import get_hospital_audit_queryset, get_ministry_audit_queryset
from apps.common.pagination import StandardResultsSetPagination
from apps.common.schema import COMMON_ERRORS
from apps.complaints.permissions import IsHospitalComplaintStaff, MinistryPermission


class HospitalAuditLogListView(ListAPIView):
    permission_classes = [IsHospitalComplaintStaff]
    serializer_class = AuditLogSerializer
    filterset_class = AuditLogFilter
    pagination_class = StandardResultsSetPagination
    search_fields = []

    def get_queryset(self):
        return get_hospital_audit_queryset(self.request.user)

    @extend_schema(
        tags=["Hospital"],
        summary="Journal d'activité de l'établissement",
        responses={403: COMMON_ERRORS[403]},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class MinistryAuditLogListView(ListAPIView):
    permission_classes = [MinistryPermission]
    serializer_class = AuditLogSerializer
    filterset_class = AuditLogFilter
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return get_ministry_audit_queryset()

    @extend_schema(
        tags=["Ministry"],
        summary="Journal d'activité national",
        responses={403: COMMON_ERRORS[403]},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
