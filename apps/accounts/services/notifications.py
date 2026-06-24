import logging

from django.conf import settings
from django.core.mail import send_mail

from apps.accounts.models import User, UserRole

logger = logging.getLogger(__name__)


def _login_url() -> str:
    base = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
    return f"{base}/connexion"


def _role_label(role: str) -> str:
    return dict(UserRole.choices).get(role, role)


def send_staff_welcome_email(
    *,
    user: User,
    password: str,
    created_by: User,
    facility_name: str | None = None,
) -> bool:
    if not user.email:
        logger.warning("Welcome email skipped: no email for user %s", user.username)
        return False

    creator = created_by.get_full_name() or created_by.username
    greeting = user.first_name.strip() or user.username
    role_label = _role_label(user.role)
    facility_line = f"\nÉtablissement : {facility_name}" if facility_name else ""

    message = (
        f"Bonjour {greeting},\n\n"
        f"Un compte Santé Écoute a été créé pour vous par {creator}.\n\n"
        f"Rôle : {role_label}{facility_line}\n\n"
        f"Identifiant : {user.username}\n"
        f"Mot de passe temporaire : {password}\n\n"
        f"Connectez-vous ici : {_login_url()}\n\n"
        "Changez votre mot de passe après votre première connexion.\n\n"
        "— Santé Écoute · Ministère de la Santé, République du Bénin"
    )

    try:
        send_mail(
            subject="Vos identifiants Santé Écoute",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception("Failed to send welcome email to %s", user.email)
        return False
