import logging

from django.conf import settings
from django.core.mail import send_mail

from apps.complaints.models import (
    Complaint,
    ComplaintStatus,
    PreferredContactMethod,
    SubmissionType,
)

logger = logging.getLogger(__name__)


def _tracking_url(reference: str) -> str:
    base = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
    return f"{base}/suivi?ref={reference}"


def _status_label(code: str) -> str:
    if not code:
        return ""
    return dict(ComplaintStatus.choices).get(code, code)


def _resolve_complainant_contacts(complaint: Complaint) -> tuple[str, str]:
    email = (complaint.email or "").strip()
    phone = (complaint.phone or "").strip()

    if not email and complaint.submitted_by_id:
        email = (complaint.submitted_by.email or "").strip()

    return email, phone


def can_notify_complainant(complaint: Complaint) -> bool:
    if complaint.submission_type == SubmissionType.ANONYMOUS:
        return False
    email, phone = _resolve_complainant_contacts(complaint)
    return bool(email or phone)


def notify_complainant_status_change(
    complaint: Complaint,
    *,
    old_status: str,
    new_status: str,
    reason: str = "",
) -> bool:
    """
    Informe le déclarant d'un changement de statut (e-mail ou SMS selon préférence).
    Retourne True si au moins une notification a été envoyée.
    """
    if not can_notify_complainant(complaint):
        return False

    email, phone = _resolve_complainant_contacts(complaint)
    preferred = complaint.preferred_contact_method
    reason = (reason or "").strip()

    sent = False
    if preferred in ("", PreferredContactMethod.EMAIL) and email:
        sent = _send_status_email(complaint, old_status, new_status, reason, email) or sent
    elif preferred in (PreferredContactMethod.PHONE, PreferredContactMethod.SMS) and phone:
        sent = _send_status_sms(complaint, new_status, phone, reason) or sent
    else:
        if email:
            sent = _send_status_email(complaint, old_status, new_status, reason, email) or sent
        elif phone:
            sent = _send_status_sms(complaint, new_status, phone, reason) or sent

    return sent


def _send_status_email(
    complaint: Complaint,
    old_status: str,
    new_status: str,
    reason: str,
    recipient: str,
) -> bool:
    old_label = _status_label(old_status)
    new_label = _status_label(new_status)
    transition = f"{old_label} → {new_label}".strip(" →")

    lines = [
        "Bonjour,",
        "",
        f"Votre dossier Santé Écoute {complaint.reference} a été mis à jour.",
        "",
        f"Titre : {complaint.title}",
        f"Établissement : {complaint.facility.name}",
        f"Nouveau statut : {new_label}",
    ]
    if old_label:
        lines.append(f"Statut précédent : {old_label}")
    if reason:
        if new_status == ComplaintStatus.RESOLVED:
            lines.extend(["", f"Résolution : {reason}"])
        elif new_status == ComplaintStatus.REJECTED:
            lines.extend(["", f"Motif : {reason}"])
        else:
            lines.extend(["", f"Message de l'établissement : {reason}"])
    lines.extend(
        [
            "",
            f"Suivre votre dossier : {_tracking_url(complaint.reference)}",
            "",
            "— Santé Écoute · Ministère de la Santé, République du Bénin",
        ]
    )

    try:
        send_mail(
            subject=f"Mise à jour de votre dossier {complaint.reference} — Santé Écoute",
            message="\n".join(lines),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=True,
        )
        return True
    except Exception:
        logger.exception(
            "Failed to send status notification email for complaint %s",
            complaint.reference,
        )
        return False


def _send_status_sms(complaint: Complaint, new_status: str, phone: str, reason: str = "") -> bool:
    new_label = _status_label(new_status)
    message = (
        f"Santé Écoute — Dossier {complaint.reference} : statut « {new_label} »."
    )
    reason = (reason or "").strip()
    if reason and new_status == ComplaintStatus.RESOLVED:
        snippet = reason if len(reason) <= 80 else f"{reason[:77]}..."
        message = f"{message} {snippet}"
    message = f"{message} Suivi : {_tracking_url(complaint.reference)}"
    logger.info("Complaint status SMS to %s: %s", phone, message)
    return True
