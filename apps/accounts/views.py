from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.models import OTPPurpose
from apps.accounts.serializers import (
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
    ForgotPasswordSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    RegisterResponseSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    UserSerializer,
)
from apps.accounts.services.otp import (
    OTPError,
    create_and_send_otp,
    find_user_by_identifier,
    issue_jwt_tokens,
    verify_otp,
)


class AuthRateThrottle(AnonRateThrottle):
    scope = "auth"


class OTPRateThrottle(AnonRateThrottle):
    scope = "otp"


GENERIC_OTP_RESPONSE = {
    "detail": "Si un compte correspondant existe, un code de vérification a été envoyé.",
}


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    @extend_schema(
        tags=["Auth"],
        summary="Inscription",
        description=(
            "Crée un compte responsable d'établissement (`HOSPITAL_MANAGER`). "
            "Les rôles admin et ministère sont créés par un administrateur."
        ),
        request=RegisterSerializer,
        responses={201: RegisterResponseSerializer},
        examples=[
            OpenApiExample(
                "Inscription",
                value={
                    "username": "manager.chu",
                    "email": "manager@chu.ci",
                    "password": "SecurePass123!",
                    "password_confirm": "SecurePass123!",
                    "phone": "+2250700000000",
                    "first_name": "Jean",
                    "last_name": "Kouassi",
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(issue_jwt_tokens(user), status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [AuthRateThrottle]

    @extend_schema(
        tags=["Auth"],
        summary="Connexion JWT",
        description="Authentifie un utilisateur et retourne les tokens access et refresh.",
        examples=[
            OpenApiExample(
                "Connexion admin",
                value={"username": "admin", "password": "admin123"},
                request_only=True,
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class RefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    @extend_schema(
        tags=["Auth"],
        summary="Rafraîchir le token JWT",
        description="Échange un refresh token valide contre un nouveau access token.",
        examples=[
            OpenApiExample(
                "Refresh",
                value={"refresh": "<refresh_token>"},
                request_only=True,
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class MeView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    @extend_schema(
        tags=["Auth"],
        summary="Profil de l'utilisateur connecté",
        responses={200: UserSerializer},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_object(self):
        return self.request.user


class OTPRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [OTPRateThrottle]

    @extend_schema(
        tags=["Auth"],
        summary="Demander un code OTP",
        description=(
            "Envoie un code à 6 chiffres par e-mail ou SMS. "
            "Usages : connexion sans mot de passe (`LOGIN`) ou réinitialisation (`RESET_PASSWORD`)."
        ),
        request=OTPRequestSerializer,
        responses={200: OpenApiResponse(description=GENERIC_OTP_RESPONSE["detail"])},
        examples=[
            OpenApiExample(
                "OTP connexion",
                value={"identifier": "admin@example.com", "purpose": "LOGIN"},
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = find_user_by_identifier(serializer.validated_data["identifier"])
        if user:
            try:
                create_and_send_otp(
                    user,
                    serializer.validated_data["purpose"],
                    serializer.validated_data["identifier"],
                )
            except OTPError as exc:
                return Response(
                    {"success": False, "error": {"detail": exc.message, "code": exc.code}},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(GENERIC_OTP_RESPONSE)


class OTPVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [OTPRateThrottle]

    @extend_schema(
        tags=["Auth"],
        summary="Vérifier un code OTP",
        description=(
            "Pour `LOGIN`, retourne les tokens JWT. "
            "Pour `RESET_PASSWORD`, confirme le code avant la réinitialisation."
        ),
        request=OTPVerifySerializer,
        examples=[
            OpenApiExample(
                "Vérification connexion",
                value={
                    "identifier": "admin@example.com",
                    "otp": "123456",
                    "purpose": "LOGIN",
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        user = find_user_by_identifier(data["identifier"])
        if not user:
            return Response(
                {"success": False, "error": {"detail": "Code incorrect.", "code": "otp_invalid"}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            verify_otp(user, data["purpose"], data["otp"])
        except OTPError as exc:
            return Response(
                {"success": False, "error": {"detail": exc.message, "code": exc.code}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if data["purpose"] == OTPPurpose.LOGIN:
            return Response(issue_jwt_tokens(user))

        return Response({"detail": "Code vérifié. Vous pouvez définir un nouveau mot de passe."})


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [OTPRateThrottle]

    @extend_schema(
        tags=["Auth"],
        summary="Mot de passe oublié",
        description="Envoie un code OTP pour réinitialiser le mot de passe.",
        request=ForgotPasswordSerializer,
        responses={200: OpenApiResponse(description=GENERIC_OTP_RESPONSE["detail"])},
        examples=[
            OpenApiExample(
                "Mot de passe oublié",
                value={"identifier": "admin@example.com"},
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = find_user_by_identifier(serializer.validated_data["identifier"])
        if user:
            try:
                create_and_send_otp(
                    user,
                    OTPPurpose.RESET_PASSWORD,
                    serializer.validated_data["identifier"],
                )
            except OTPError as exc:
                return Response(
                    {"success": False, "error": {"detail": exc.message, "code": exc.code}},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(GENERIC_OTP_RESPONSE)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [OTPRateThrottle]

    @extend_schema(
        tags=["Auth"],
        summary="Réinitialiser le mot de passe",
        description="Valide le code OTP et définit un nouveau mot de passe.",
        request=ResetPasswordSerializer,
        responses={200: OpenApiResponse(description="Mot de passe mis à jour.")},
        examples=[
            OpenApiExample(
                "Réinitialisation",
                value={
                    "identifier": "admin@example.com",
                    "otp": "123456",
                    "new_password": "NewSecurePass123!",
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        user = find_user_by_identifier(data["identifier"])
        if not user:
            return Response(
                {"success": False, "error": {"detail": "Code incorrect.", "code": "otp_invalid"}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            verify_otp(user, OTPPurpose.RESET_PASSWORD, data["otp"])
        except OTPError as exc:
            return Response(
                {"success": False, "error": {"detail": exc.message, "code": exc.code}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(data["new_password"])
        user.save(update_fields=["password"])

        return Response({"detail": "Mot de passe mis à jour avec succès."})


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Auth"],
        summary="Changer le mot de passe",
        description="Permet à un utilisateur connecté de changer son mot de passe.",
        request=ChangePasswordSerializer,
        responses={200: OpenApiResponse(description="Mot de passe modifié.")},
        examples=[
            OpenApiExample(
                "Changement",
                value={
                    "old_password": "admin123",
                    "new_password": "NewSecurePass123!",
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])

        return Response({"detail": "Mot de passe modifié avec succès."})
