from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.complaints.models import (
    Complaint,
    ComplaintStatus,
    ComplaintStatusHistory,
    ComplaintType,
    SubmissionType,
    SubmitterProfile,
)
from apps.facilities.services import get_user_facility


class ComplaintValidationError(Exception):
    def __init__(self, message, field=None):
        self.message = message
        self.field = field
        super().__init__(message)


FACILITY_STAFF_ROLES = (UserRole.HOSPITAL_MANAGER, UserRole.FACILITY_AGENT)


def validate_complaint_submission(data: dict, user: User | None = None) -> None:
    """
    Valide le profil du déclarant et les champs associés.
    `data` contient les champs bruts de création (modèle ou serializer).
    """
    profile = data.get("submitter_profile", SubmitterProfile.CITIZEN)
    submission_type = data.get("submission_type")
    complaint_type = data.get("complaint_type")
    facility = data.get("facility")
    reported_agent = data.get("reported_agent")
    reported_agent_name = (data.get("reported_agent_name") or "").strip()

    if profile == SubmitterProfile.CITIZEN:
        if submission_type == SubmissionType.IDENTIFIED:
            if not data.get("phone") and not data.get("email"):
                raise ComplaintValidationError(
                    "Téléphone ou e-mail requis pour une plainte identifiée.",
                    "phone",
                )
        if reported_agent or reported_agent_name:
            raise ComplaintValidationError(
                "Le profil usager ne permet pas de cibler un agent nominativement.",
                "reported_agent",
            )
        return

    if profile != SubmitterProfile.FACILITY_AGENT:
        raise ComplaintValidationError("Profil de déclarant invalide.", "submitter_profile")

    if not user or not user.is_authenticated:
        raise ComplaintValidationError(
            "Authentification requise pour une plainte en tant qu'agent.",
            "submitter_profile",
        )

    if user.role not in FACILITY_STAFF_ROLES and user.role != UserRole.ADMIN:
        raise ComplaintValidationError(
            "Seul un agent ou responsable d'établissement peut utiliser ce profil.",
            "submitter_profile",
        )

    if complaint_type == ComplaintType.COMPLAINT:
        if not reported_agent and not reported_agent_name:
            raise ComplaintValidationError(
                "Indiquez l'agent concerné (compte ou nom).",
                "reported_agent",
            )

    if reported_agent:
        if reported_agent.pk == user.pk:
            raise ComplaintValidationError(
                "Vous ne pouvez pas porter plainte contre vous-même.",
                "reported_agent",
            )

        submitter_facility = get_user_facility(user)
        reported_facility = get_user_facility(reported_agent)

        if submitter_facility and reported_facility and submitter_facility != reported_facility:
            raise ComplaintValidationError(
                "L'agent visé doit appartenir au même établissement.",
                "reported_agent",
            )

        if facility and reported_facility and facility != reported_facility:
            raise ComplaintValidationError(
                "L'agent visé n'appartient pas à l'établissement indiqué.",
                "reported_agent",
            )

        if reported_agent.role not in FACILITY_STAFF_ROLES:
            raise ComplaintValidationError(
                "La cible doit être un agent ou responsable d'établissement.",
                "reported_agent",
            )


def apply_submitter_context(data: dict, user: User | None = None) -> dict:
    """Renseigne submitted_by pour les plaintes déposées par un agent connecté."""
    if data.get("submitter_profile") == SubmitterProfile.FACILITY_AGENT and user:
        data = {**data, "submitted_by": user}
    return data


def generate_reference(year: int | None = None) -> str:
    """
    Génère une référence unique au format SE-{année}-{6 chiffres}.
    Exemple : SE-2026-000001
    """
    year = year or timezone.now().year
    prefix = f"SE-{year}-"

    with transaction.atomic():
        last_reference = (
            Complaint.objects.select_for_update()
            .filter(reference__startswith=prefix)
            .order_by("-reference")
            .values_list("reference", flat=True)
            .first()
        )

        if last_reference:
            sequence = int(last_reference.rsplit("-", 1)[-1]) + 1
        else:
            sequence = 1

        return f"{prefix}{sequence:06d}"


def record_status_change(
    complaint: Complaint,
    new_status: str,
    changed_by=None,
    reason: str = "",
) -> ComplaintStatusHistory:
    """Enregistre une transition de statut et met à jour la plainte."""
    old_status = complaint.current_status
    if old_status == new_status:
        raise ValueError("Le statut est déjà défini à cette valeur.")

    history = ComplaintStatusHistory.objects.create(
        complaint=complaint,
        old_status=old_status,
        new_status=new_status,
        changed_by=changed_by,
        reason=reason,
    )
    complaint.current_status = new_status
    complaint.save(update_fields=["current_status", "updated_at"])
    return history


def reject_complaint(complaint: Complaint, changed_by, reason: str) -> ComplaintStatusHistory:
    """Rejette une plainte avec motif obligatoire."""
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("Le motif de rejet est obligatoire.")
    return record_status_change(
        complaint,
        ComplaintStatus.REJECTED,
        changed_by=changed_by,
        reason=reason,
    )


def change_complaint_status(
    complaint: Complaint,
    new_status: str,
    changed_by=None,
    reason: str = "",
) -> ComplaintStatusHistory:
    """Alias métier pour record_status_change."""
    return record_status_change(complaint, new_status, changed_by, reason)


def record_initial_status(complaint: Complaint) -> ComplaintStatusHistory:
    """Crée la première entrée d'historique à l'ouverture d'une plainte."""
    return ComplaintStatusHistory.objects.create(
        complaint=complaint,
        old_status="",
        new_status=complaint.current_status,
        changed_by=None,
        reason="Plainte enregistrée",
    )
