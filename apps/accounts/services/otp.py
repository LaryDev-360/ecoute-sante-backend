import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import OTPChannel, OTPPurpose, OTPVerification, User

logger = logging.getLogger(__name__)


class OTPError(Exception):
    def __init__(self, message, code="otp_error"):
        self.message = message
        self.code = code
        super().__init__(message)


def find_user_by_identifier(identifier: str) -> User | None:
    identifier = identifier.strip()
    return User.objects.filter(
        Q(email__iexact=identifier)
        | Q(username__iexact=identifier)
        | Q(phone=identifier),
        is_active=True,
    ).first()


def _generate_otp_code() -> str:
    length = getattr(settings, "OTP_LENGTH", 6)
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def _hash_otp(code: str) -> str:
    return make_password(code)


def _invalidate_pending_otps(user: User, purpose: str) -> None:
    OTPVerification.objects.filter(
        user=user,
        purpose=purpose,
        is_used=False,
    ).update(is_used=True)


def _resolve_channel(user: User, identifier: str) -> OTPChannel:
    if "@" in identifier:
        return OTPChannel.EMAIL
    if user.email and identifier.lower() == user.email.lower():
        return OTPChannel.EMAIL
    if user.phone and identifier == user.phone:
        return OTPChannel.SMS
    return OTPChannel.EMAIL if user.email else OTPChannel.SMS


def _send_otp(user: User, code: str, purpose: str, channel: str) -> None:
    purpose_label = {
        OTPPurpose.LOGIN: "connexion",
        OTPPurpose.RESET_PASSWORD: "réinitialisation de mot de passe",
    }.get(purpose, purpose)

    message = (
        f"Votre code Santé Écoute ({purpose_label}) : {code}\n"
        f"Valide {getattr(settings, 'OTP_EXPIRY_MINUTES', 10)} minutes."
    )

    if channel == OTPChannel.EMAIL:
        if not user.email:
            raise OTPError("Aucune adresse e-mail associée à ce compte.", "no_email")
        try:
            sent = send_mail(
                subject="Code de vérification — Santé Écoute",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception:
            logger.exception("Failed to send OTP email to %s", user.email)
            raise OTPError("Impossible d'envoyer le code par e-mail.", "email_send_failed")
        if sent == 0:
            logger.error("OTP email not delivered to %s", user.email)
            raise OTPError("Impossible d'envoyer le code par e-mail.", "email_send_failed")
        return

    if not user.phone:
        raise OTPError("Aucun numéro de téléphone associé à ce compte.", "no_phone")
    logger.info("OTP SMS to %s: %s", user.phone, code)


def create_and_send_otp(user: User, purpose: str, identifier: str) -> None:
    _invalidate_pending_otps(user, purpose)

    code = _generate_otp_code()
    expiry_minutes = getattr(settings, "OTP_EXPIRY_MINUTES", 10)
    channel = _resolve_channel(user, identifier)

    OTPVerification.objects.create(
        user=user,
        code_hash=_hash_otp(code),
        purpose=purpose,
        channel=channel,
        expires_at=timezone.now() + timedelta(minutes=expiry_minutes),
    )
    _send_otp(user, code, purpose, channel)


def verify_otp(user: User, purpose: str, code: str) -> OTPVerification:
    max_attempts = getattr(settings, "OTP_MAX_ATTEMPTS", 5)

    otp = (
        OTPVerification.objects.filter(
            user=user,
            purpose=purpose,
            is_used=False,
            expires_at__gt=timezone.now(),
        )
        .order_by("-created_at")
        .first()
    )

    if not otp:
        raise OTPError("Code expiré ou introuvable.", "otp_expired")

    if otp.attempts >= max_attempts:
        otp.is_used = True
        otp.save(update_fields=["is_used"])
        raise OTPError("Nombre maximal de tentatives atteint.", "otp_max_attempts")

    if not check_password(code, otp.code_hash):
        otp.attempts += 1
        otp.save(update_fields=["attempts"])
        raise OTPError("Code incorrect.", "otp_invalid")

    otp.is_used = True
    otp.save(update_fields=["is_used"])
    return otp


def issue_jwt_tokens(user: User) -> dict:
    from rest_framework_simplejwt.tokens import RefreshToken

    from apps.accounts.serializers import UserSerializer

    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    refresh["username"] = user.username

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
        "user": UserSerializer(user).data,
    }
