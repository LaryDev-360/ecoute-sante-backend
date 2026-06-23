from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.response import Response

from apps.accounts.filters import StaffUserFilter
from apps.accounts.user_serializers import (
    HospitalUserCreateSerializer,
    MinistryUserCreateSerializer,
    StaffUserCreateResponseSerializer,
    StaffUserSerializer,
    StaffUserUpdateSerializer,
)
from apps.accounts.user_services import (
    create_staff_user,
    get_hospital_users_queryset,
    get_ministry_users_queryset,
    hospital_can_manage_user,
    ministry_can_manage_user,
    update_staff_user,
)
from apps.accounts.models import User, UserRole
from apps.common.pagination import StandardResultsSetPagination
from apps.common.permissions import IsMinistryOrAdmin
from apps.common.schema import COMMON_ERRORS
from apps.complaints.permissions import IsHospitalComplaintStaff


def _validation_error_response(exc: ValueError) -> Response:
    mapping = {
        "username_taken": ("username", "Ce nom d'utilisateur est déjà pris."),
        "email_taken": ("email", "Cette adresse e-mail est déjà utilisée."),
        "phone_taken": ("phone", "Ce numéro de téléphone est déjà utilisé."),
        "facility_required": ("facility_id", "Un établissement est requis pour ce rôle."),
        "cannot_deactivate_self": ("is_active", "Vous ne pouvez pas désactiver votre propre compte."),
    }
    code = str(exc)
    if code in mapping:
        field, message = mapping[code]
        return Response(
            {"success": False, "error": {field: message}},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        {"success": False, "error": {"detail": str(exc)}},
        status=status.HTTP_400_BAD_REQUEST,
    )


class MinistryUserListCreateView(ListCreateAPIView):
    permission_classes = [IsMinistryOrAdmin]
    serializer_class = StaffUserSerializer
    filterset_class = StaffUserFilter
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return get_ministry_users_queryset()

    @extend_schema(tags=["Ministry"], summary="Lister les utilisateurs staff")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["Ministry"],
        summary="Créer un utilisateur staff",
        request=MinistryUserCreateSerializer,
        responses={201: StaffUserCreateResponseSerializer},
    )
    def post(self, request, *args, **kwargs):
        serializer = MinistryUserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        facility = data.get("facility_id")
        role = data["role"]

        if role in (UserRole.HOSPITAL_MANAGER, UserRole.FACILITY_AGENT) and not facility:
            return Response(
                {"success": False, "error": {"facility_id": "Établissement requis."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user, initial_password = create_staff_user(
                actor=request.user,
                role=role,
                username=data["username"],
                email=data["email"],
                password=data.get("password") or None,
                phone=data.get("phone", ""),
                first_name=data.get("first_name", ""),
                last_name=data.get("last_name", ""),
                facility=facility,
            )
        except ValueError as exc:
            return _validation_error_response(exc)

        payload = {
            "user": StaffUserSerializer(user).data,
            "initial_password": initial_password,
            "message": (
                "Compte créé. Communiquez le mot de passe initial à l'utilisateur "
                "(il ne sera plus affiché)."
            ),
        }
        return Response(payload, status=status.HTTP_201_CREATED)


class MinistryUserDetailView(RetrieveUpdateAPIView):
    permission_classes = [IsMinistryOrAdmin]
    serializer_class = StaffUserSerializer
    lookup_url_kwarg = "pk"

    def get_queryset(self):
        return get_ministry_users_queryset()

    @extend_schema(tags=["Ministry"], summary="Détail utilisateur staff")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["Ministry"],
        summary="Mettre à jour un utilisateur staff",
        request=StaffUserUpdateSerializer,
        responses={200: StaffUserSerializer, 400: COMMON_ERRORS[400]},
    )
    def patch(self, request, *args, **kwargs):
        target = self.get_object()
        if not ministry_can_manage_user(request.user, target):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = StaffUserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            user = update_staff_user(
                actor=request.user,
                target=target,
                data=serializer.validated_data,
            )
        except ValueError as exc:
            return _validation_error_response(exc)

        return Response(StaffUserSerializer(user).data)


class HospitalUserListCreateView(ListCreateAPIView):
    queryset = User.objects.none()
    permission_classes = [IsHospitalComplaintStaff]
    serializer_class = StaffUserSerializer
    filterset_class = StaffUserFilter
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return User.objects.none()
        user = self.request.user
        if user.role != UserRole.HOSPITAL_MANAGER:
            return get_hospital_users_queryset(user).none()
        return get_hospital_users_queryset(user)

    @extend_schema(tags=["Hospital"], summary="Lister les agents de l'établissement")
    def get(self, request, *args, **kwargs):
        if request.user.role != UserRole.HOSPITAL_MANAGER:
            return Response(
                {"success": False, "error": {"detail": "Réservé aux responsables d'établissement."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["Hospital"],
        summary="Créer un agent d'établissement",
        request=HospitalUserCreateSerializer,
        responses={201: StaffUserCreateResponseSerializer},
    )
    def post(self, request, *args, **kwargs):
        if request.user.role != UserRole.HOSPITAL_MANAGER:
            return Response(
                {"success": False, "error": {"detail": "Réservé aux responsables d'établissement."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = HospitalUserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from apps.facilities.services import get_user_facility

        facility = get_user_facility(request.user)
        if not facility:
            return Response(
                {"success": False, "error": {"detail": "Aucun établissement affecté."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user, initial_password = create_staff_user(
                actor=request.user,
                role=UserRole.FACILITY_AGENT,
                username=data["username"],
                email=data["email"],
                password=data.get("password") or None,
                phone=data.get("phone", ""),
                first_name=data.get("first_name", ""),
                last_name=data.get("last_name", ""),
                facility=facility,
            )
        except ValueError as exc:
            return _validation_error_response(exc)

        payload = {
            "user": StaffUserSerializer(user).data,
            "initial_password": initial_password,
            "message": (
                "Agent créé. Communiquez le mot de passe initial "
                "(il ne sera plus affiché)."
            ),
        }
        return Response(payload, status=status.HTTP_201_CREATED)


class HospitalUserDetailView(RetrieveUpdateAPIView):
    queryset = User.objects.none()
    permission_classes = [IsHospitalComplaintStaff]
    serializer_class = StaffUserSerializer
    lookup_url_kwarg = "pk"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return User.objects.none()
        return get_hospital_users_queryset(self.request.user)

    @extend_schema(tags=["Hospital"], summary="Détail agent")
    def get(self, request, *args, **kwargs):
        if request.user.role != UserRole.HOSPITAL_MANAGER:
            return Response(status=status.HTTP_403_FORBIDDEN)
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["Hospital"],
        summary="Mettre à jour un agent",
        request=StaffUserUpdateSerializer,
        responses={200: StaffUserSerializer},
    )
    def patch(self, request, *args, **kwargs):
        if request.user.role != UserRole.HOSPITAL_MANAGER:
            return Response(status=status.HTTP_403_FORBIDDEN)

        target = self.get_object()
        if not hospital_can_manage_user(request.user, target):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = StaffUserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            user = update_staff_user(
                actor=request.user,
                target=target,
                data=serializer.validated_data,
            )
        except ValueError as exc:
            return _validation_error_response(exc)

        return Response(StaffUserSerializer(user).data)
