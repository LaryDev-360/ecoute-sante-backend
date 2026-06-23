from django.db.models import Prefetch
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.common.schema import COMMON_ERRORS

from apps.complaints.models import Complaint, ComplaintCategory
from apps.complaints.serializers import (
    SUBMITTER_PROFILE_META,
    ComplaintCategoryPublicSerializer,
    ComplaintCreateResponseSerializer,
    ComplaintCreateSerializer,
    ComplaintTrackSerializer,
    FacilityPublicSerializer,
    SubmitterProfileChoicesSerializer,
)
from apps.facilities.models import Facility, FacilityService


class PublicComplaintThrottle(AnonRateThrottle):
    scope = "public_complaint"


class ComplaintSubmitView(APIView):
    """
    Soumettre un signalement (public ou agent authentifié).
    JWT optionnel — requis pour `submitter_profile=FACILITY_AGENT`.
    """

    permission_classes = [AllowAny]
    throttle_classes = [PublicComplaintThrottle]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @extend_schema(
        tags=["Public"],
        summary="Soumettre un signalement",
        description=(
            "Crée une plainte avec statut initial `RECEIVED` et historique automatique. "
            "Pièces jointes optionnelles (JPEG, PNG, WebP, PDF — max 5 Mo). "
            "Pour `FACILITY_AGENT`, fournir un token JWT."
        ),
        request=ComplaintCreateSerializer,
        responses={201: ComplaintCreateResponseSerializer, **COMMON_ERRORS},
        examples=[
            OpenApiExample(
                "Plainte usager",
                value={
                    "submitter_profile": "CITIZEN",
                    "submission_type": "IDENTIFIED",
                    "complaint_type": "COMPLAINT",
                    "facility": 1,
                    "service": 2,
                    "category": 1,
                    "title": "Temps d'attente aux urgences",
                    "description": "Attente de plus de 3 heures sans information.",
                    "requested_actions": "Réduire les délais et informer les patients en salle d'attente.",
                    "severity": "HIGH",
                    "phone": "+22997000001",
                    "email": "citoyen@example.bj",
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = ComplaintCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        complaint = serializer.save()
        return Response(
            ComplaintCreateResponseSerializer(complaint).data,
            status=status.HTTP_201_CREATED,
        )


class ComplaintTrackView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PublicComplaintThrottle]

    @extend_schema(
        tags=["Public"],
        summary="Suivre un signalement par référence",
        description="Retourne le statut et la chronologie publique (sans commentaires internes).",
        responses={
            200: ComplaintTrackSerializer,
            404: OpenApiResponse(description="Référence introuvable"),
        },
    )
    def get(self, request, reference):
        complaint = (
            Complaint.objects.filter(reference__iexact=reference.strip(), is_archived=False)
            .select_related("facility")
            .prefetch_related("status_history")
            .first()
        )
        if not complaint:
            return Response(
                {"success": False, "error": {"detail": "Référence introuvable."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ComplaintTrackSerializer(complaint).data)


class SubmitterProfileListView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Public"],
        summary="Profils de déclarant disponibles",
        responses={200: SubmitterProfileChoicesSerializer(many=True)},
    )
    def get(self, request):
        return Response(SUBMITTER_PROFILE_META)


class ComplaintCategoryListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ComplaintCategoryPublicSerializer
    pagination_class = None
    queryset = ComplaintCategory.objects.filter(active=True)

    @extend_schema(
        tags=["Public"],
        summary="Lister les catégories de signalement",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class FacilityPublicListView(ListAPIView):
    """Établissements actifs et leurs services — pour les formulaires publics."""

    permission_classes = [AllowAny]
    serializer_class = FacilityPublicSerializer
    pagination_class = None

    def get_queryset(self):
        return (
            Facility.objects.filter(active=True)
            .prefetch_related(
                Prefetch(
                    "services",
                    queryset=FacilityService.objects.filter(active=True).order_by("name"),
                )
            )
            .order_by("name")
        )

    @extend_schema(
        tags=["Public"],
        summary="Lister les établissements (formulaire public)",
        description="Retourne les établissements actifs avec leurs services pour alimenter le dépôt de signalement.",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
