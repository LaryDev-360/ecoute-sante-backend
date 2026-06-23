from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
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
from apps.complaints.export import (
    complaint_detail_queryset,
    export_complaint_detail_csv,
    export_complaints_csv,
)
from apps.complaints.serializers import (
    HospitalComplaintDetailSerializer,
    HospitalComplaintListSerializer,
)


def _filtered_queryset(request):
    qs = get_base_complaints_queryset()
    filterset = MinistryComplaintFilter(request.query_params, queryset=qs)
    return filterset.qs


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
        if self.action in ("retrieve", "export"):
            return complaint_detail_queryset(qs)
        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return HospitalComplaintDetailSerializer
        return HospitalComplaintListSerializer

    @extend_schema(
        tags=["Ministry"],
        summary="Exporter un dossier en CSV",
        responses={403: COMMON_ERRORS[403], 404: COMMON_ERRORS[404]},
    )
    @action(detail=True, methods=["get"], url_path="export")
    def export(self, request, pk=None):
        complaint = self.get_object()
        return export_complaint_detail_csv(complaint)

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
