from django.db.models import Count
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserRole
from apps.facilities.filters import FacilityFilter
from apps.facilities.models import Facility, FacilityService, UserFacilityAssignment
from apps.facilities.permissions import CanManageAssignments, CanManageFacilities, CanManageFacilityServices
from apps.facilities.serializers import (
    FacilityDetailSerializer,
    FacilityImportSerializer,
    FacilityListSerializer,
    FacilityServiceSerializer,
    FacilityServiceWriteSerializer,
    FacilityWriteSerializer,
    UserFacilityAssignmentSerializer,
)
from apps.facilities.services import (
    assign_manager_to_facility,
    deactivate_facility,
    get_facilities_queryset_for_user,
    get_user_facility,
    import_facilities_csv,
    import_facilities_payload,
    user_can_access_facility,
)


@extend_schema_view(
    list=extend_schema(
        tags=["Facilities"],
        summary="Lister les établissements",
    ),
    retrieve=extend_schema(
        tags=["Facilities"],
        summary="Détail d'un établissement",
    ),
    create=extend_schema(
        tags=["Facilities"],
        summary="Créer un établissement",
        description=(
            "Admin/ministère : création libre. "
            "Responsable sans affectation : création + rattachement automatique."
        ),
    ),
    update=extend_schema(tags=["Facilities"], summary="Mettre à jour un établissement"),
    partial_update=extend_schema(tags=["Facilities"], summary="Mettre à jour partiellement"),
    destroy=extend_schema(
        tags=["Facilities"],
        summary="Désactiver un établissement",
        description="Désactivation logique (`active=false`), pas de suppression physique.",
    ),
)
class FacilityViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, CanManageFacilities]
    filterset_class = FacilityFilter
    search_fields = ["name", "code", "city", "region"]
    ordering_fields = ["name", "created_at", "city", "region"]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return (
            get_facilities_queryset_for_user(self.request.user)
            .annotate(services_count=Count("services"))
        )

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return FacilityWriteSerializer
        if self.action == "retrieve":
            return FacilityDetailSerializer
        return FacilityListSerializer

    def perform_create(self, serializer):
        facility = serializer.save()
        if self.request.user.role == UserRole.HOSPITAL_MANAGER:
            assign_manager_to_facility(self.request.user, facility)

    def perform_destroy(self, instance):
        deactivate_facility(instance)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["Facilities"],
        summary="Importer des établissements (JSON)",
        request=FacilityImportSerializer,
        responses={200: OpenApiResponse(description="Résultat de l'import")},
        examples=[
            OpenApiExample(
                "Import JSON",
                value={
                    "facilities": [
                        {
                            "name": "HZ Suru-Léré",
                            "code": "HZ-SURU",
                            "facility_type": "HOSPITAL",
                            "region": "Littoral",
                            "city": "Cotonou",
                            "address": "Quartier Suru-Léré",
                            "services": ["Accueil", "Urgences"],
                        }
                    ]
                },
                request_only=True,
            ),
        ],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="import",
        parser_classes=[JSONParser],
    )
    def import_facilities(self, request):
        serializer = FacilityImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = import_facilities_payload(
                request.user,
                serializer.validated_data["facilities"],
            )
        except ValueError as exc:
            return Response(
                {"success": False, "error": {"detail": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(result)


@extend_schema(
    tags=["Facilities"],
    summary="Importer des établissements (CSV)",
    description=(
        "Colonnes requises : code, name, facility_type, region, city, address. "
        "Optionnel : services (séparés par |), active."
    ),
)
class FacilityCSVImportView(APIView):
    permission_classes = [IsAuthenticated, CanManageFacilities]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response(
                {"success": False, "error": {"detail": "Fichier CSV requis (champ file)."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            content = upload.read().decode("utf-8-sig")
            result = import_facilities_csv(request.user, content)
        except ValueError as exc:
            return Response(
                {"success": False, "error": {"detail": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except UnicodeDecodeError:
            return Response(
                {"success": False, "error": {"detail": "Encodage UTF-8 requis."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(result)


@extend_schema_view(
    list=extend_schema(tags=["Facilities"], summary="Lister les services d'un établissement"),
    retrieve=extend_schema(tags=["Facilities"], summary="Détail d'un service"),
    create=extend_schema(tags=["Facilities"], summary="Ajouter un service"),
    update=extend_schema(tags=["Facilities"], summary="Mettre à jour un service"),
    partial_update=extend_schema(tags=["Facilities"], summary="Mettre à jour partiellement un service"),
    destroy=extend_schema(
        tags=["Facilities"],
        summary="Désactiver un service",
        description="Désactivation logique (`active=false`).",
    ),
)
class FacilityServiceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, CanManageFacilityServices]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_facility(self):
        facility = get_object_or_404(Facility, pk=self.kwargs["facility_pk"])
        if not user_can_access_facility(self.request.user, facility):
            self.permission_denied(self.request)
        return facility

    def get_queryset(self):
        facility = self.get_facility()
        return FacilityService.objects.filter(facility=facility)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return FacilityServiceWriteSerializer
        return FacilityServiceSerializer

    def perform_create(self, serializer):
        serializer.save(facility=self.get_facility())

    def perform_destroy(self, instance):
        instance.active = False
        instance.save(update_fields=["active"])

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    list=extend_schema(tags=["Facilities"], summary="Lister les affectations responsable ↔ établissement"),
    retrieve=extend_schema(tags=["Facilities"], summary="Détail d'une affectation"),
    create=extend_schema(tags=["Facilities"], summary="Affecter un responsable à un établissement"),
    destroy=extend_schema(tags=["Facilities"], summary="Supprimer une affectation"),
)
class UserFacilityAssignmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, CanManageAssignments]
    serializer_class = UserFacilityAssignmentSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        return UserFacilityAssignment.objects.select_related("user", "facility")
