from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.complaints.filters import HospitalComplaintFilter
from apps.complaints.hospital_services import build_hospital_dashboard, get_hospital_complaints_queryset
from apps.complaints.permissions import IsHospitalComplaintStaff
from apps.complaints.serializers import (
    ComplaintCommentCreateSerializer,
    ComplaintRejectSerializer,
    ComplaintStatusUpdateSerializer,
    HospitalCommentSerializer,
    HospitalComplaintDetailSerializer,
    HospitalComplaintListSerializer,
    HospitalStatusHistorySerializer,
)


class HospitalDashboardView(APIView):
    permission_classes = [IsHospitalComplaintStaff]

    @extend_schema(
        tags=["Hospital"],
        summary="Tableau de bord établissement",
        description=(
            "KPIs : totaux par statut, délai moyen de traitement, "
            "top catégories et services."
        ),
    )
    def get(self, request):
        return Response(build_hospital_dashboard(request.user))


@extend_schema_view(
    list=extend_schema(
        tags=["Hospital"],
        summary="Lister les plaintes de l'établissement",
    ),
    retrieve=extend_schema(
        tags=["Hospital"],
        summary="Détail d'une plainte",
    ),
)
class HospitalComplaintViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsHospitalComplaintStaff]
    filterset_class = HospitalComplaintFilter
    search_fields = ["reference", "title", "description"]
    ordering_fields = ["created_at", "updated_at", "severity", "current_status"]

    def get_queryset(self):
        return get_hospital_complaints_queryset(self.request.user)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return HospitalComplaintDetailSerializer
        return HospitalComplaintListSerializer

    @extend_schema(
        tags=["Hospital"],
        summary="Changer le statut d'une plainte",
        request=ComplaintStatusUpdateSerializer,
        responses={200: HospitalStatusHistorySerializer},
        examples=[
            OpenApiExample(
                "Passer en cours",
                value={"status": "IN_PROGRESS", "reason": "Équipe mobilisée"},
                request_only=True,
            ),
        ],
    )
    @action(detail=True, methods=["patch"], url_path="status")
    def update_status(self, request, pk=None):
        complaint = self.get_object()
        serializer = ComplaintStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        history = serializer.save(complaint=complaint, user=request.user)
        return Response(HospitalStatusHistorySerializer(history).data)

    @extend_schema(
        tags=["Hospital"],
        summary="Rejeter une plainte",
        request=ComplaintRejectSerializer,
        responses={200: HospitalStatusHistorySerializer},
        examples=[
            OpenApiExample(
                "Rejet",
                value={"reason": "Plainte hors périmètre de l'établissement"},
                request_only=True,
            ),
        ],
    )
    @action(detail=True, methods=["patch"], url_path="reject")
    def reject(self, request, pk=None):
        complaint = self.get_object()
        serializer = ComplaintRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        history = serializer.save(complaint=complaint, user=request.user)
        return Response(HospitalStatusHistorySerializer(history).data)

    @extend_schema(
        tags=["Hospital"],
        summary="Ajouter un commentaire interne",
        request=ComplaintCommentCreateSerializer,
        responses={201: HospitalCommentSerializer},
    )
    @action(detail=True, methods=["post"], url_path="comments")
    def add_comment(self, request, pk=None):
        complaint = self.get_object()
        serializer = ComplaintCommentCreateSerializer(
            data=request.data,
            context={"complaint": complaint, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        comment = serializer.save()
        return Response(
            HospitalCommentSerializer(comment).data,
            status=status.HTTP_201_CREATED,
        )
