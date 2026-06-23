import csv
from io import StringIO

from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.schema import COMMON_ERRORS

from apps.analytics.services import (
    build_ministry_analytics,
    build_ministry_dashboard,
    get_base_complaints_queryset,
)
from apps.complaints.filters import MinistryComplaintFilter
from apps.complaints.permissions import MinistryPermission
from apps.complaints.serializers import (
    HospitalComplaintDetailSerializer,
    HospitalComplaintListSerializer,
)


def _filtered_queryset(request):
    qs = get_base_complaints_queryset()
    filterset = MinistryComplaintFilter(request.query_params, queryset=qs)
    return filterset.qs


def export_complaints_csv(queryset) -> HttpResponse:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "reference",
            "title",
            "status",
            "severity",
            "complaint_type",
            "submitter_profile",
            "facility_code",
            "facility_name",
            "region",
            "city",
            "category",
            "service",
            "created_at",
        ]
    )
    for complaint in queryset.iterator():
        writer.writerow(
            [
                complaint.reference,
                complaint.title,
                complaint.current_status,
                complaint.severity,
                complaint.complaint_type,
                complaint.submitter_profile,
                complaint.facility.code,
                complaint.facility.name,
                complaint.facility.region,
                complaint.facility.city,
                complaint.category.name,
                complaint.service.name,
                complaint.created_at.isoformat(),
            ]
        )

    response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
    filename = f"plaintes_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class MinistryDashboardView(APIView):
    permission_classes = [MinistryPermission]

    @extend_schema(
        tags=["Ministry"],
        summary="Tableau de bord national",
        description=(
            "KPIs nationaux : totaux, taux de résolution/rejet, "
            "délai moyen, répartition par région et établissement, tendance mensuelle."
        ),
        responses={403: COMMON_ERRORS[403]},
    )
    def get(self, request):
        return Response(build_ministry_dashboard(_filtered_queryset(request)))


class MinistryAnalyticsView(APIView):
    permission_classes = [MinistryPermission]

    @extend_schema(
        tags=["Ministry"],
        summary="Analytiques détaillées",
        description="Agrégats par statut, sévérité, catégorie, type et profil déclarant.",
        responses={403: COMMON_ERRORS[403]},
    )
    def get(self, request):
        return Response(build_ministry_analytics(_filtered_queryset(request)))


@extend_schema_view(
    list=extend_schema(
        tags=["Ministry"],
        summary="Liste nationale des plaintes",
        description="Filtres : region, facility, status, category, service, severity, date_from, date_to.",
        responses={403: COMMON_ERRORS[403]},
    ),
    retrieve=extend_schema(
        tags=["Ministry"],
        summary="Détail d'une plainte (lecture seule)",
        responses={403: COMMON_ERRORS[403], 404: COMMON_ERRORS[404]},
    ),
)
class MinistryComplaintViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [MinistryPermission]
    filterset_class = MinistryComplaintFilter
    search_fields = ["reference", "title", "description", "facility__name", "facility__region"]
    ordering_fields = ["created_at", "updated_at", "severity", "current_status"]

    def get_queryset(self):
        qs = get_base_complaints_queryset()
        if self.action == "retrieve":
            return qs.prefetch_related(
                "attachments",
                "comments__author",
                "status_history__changed_by",
            )
        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return HospitalComplaintDetailSerializer
        return HospitalComplaintListSerializer

    def list(self, request, *args, **kwargs):
        if request.query_params.get("export") == "csv":
            queryset = self.filter_queryset(self.get_queryset())
            return export_complaints_csv(queryset)
        return super().list(request, *args, **kwargs)


class MinistryComplaintExportView(APIView):
    permission_classes = [MinistryPermission]

    @extend_schema(
        tags=["Ministry"],
        summary="Exporter les plaintes en CSV",
        description="Mêmes filtres que la liste nationale (region, facility, status, dates, etc.).",
        responses={403: COMMON_ERRORS[403]},
    )
    def get(self, request):
        qs = _filtered_queryset(request)
        return export_complaints_csv(qs)
