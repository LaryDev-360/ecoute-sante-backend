from __future__ import annotations

from typing import Any

from apps.accounts.models import UserRole
from apps.audit.models import AuditAction, AuditLog, AuditResourceType
from apps.complaints.hospital_services import FACILITY_STAFF_ROLES
from apps.complaints.models import Complaint, ComplaintComment, ComplaintStatus
from apps.facilities.models import Facility
from apps.facilities.services import get_user_facility


def record_audit_log(
    *,
    action: str,
    resource_type: str,
    resource_id: str | int,
    summary: str,
    actor=None,
    resource_label: str = "",
    metadata: dict[str, Any] | None = None,
    facility: Facility | None = None,
) -> AuditLog:
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        resource_label=resource_label,
        summary=summary,
        metadata=metadata or {},
        facility=facility,
    )


def _complaint_facility(complaint: Complaint) -> Facility:
    return complaint.facility


def log_complaint_created(complaint: Complaint, *, actor=None) -> AuditLog:
    actor_label = "un usager" if actor is None else actor.get_username()
    return record_audit_log(
        actor=actor,
        action=AuditAction.COMPLAINT_CREATED,
        resource_type=AuditResourceType.COMPLAINT,
        resource_id=complaint.pk,
        resource_label=complaint.reference,
        facility=_complaint_facility(complaint),
        summary=f"Signalement {complaint.reference} enregistré par {actor_label}.",
        metadata={
            "reference": complaint.reference,
            "complaint_type": complaint.complaint_type,
            "submitter_profile": complaint.submitter_profile,
        },
    )


def log_complaint_status_changed(
    complaint: Complaint,
    *,
    actor,
    old_status: str,
    new_status: str,
    reason: str = "",
) -> AuditLog:
    action = (
        AuditAction.COMPLAINT_REJECTED
        if new_status == ComplaintStatus.REJECTED
        else AuditAction.COMPLAINT_STATUS_CHANGED
    )
    old_label = ComplaintStatus(old_status).label if old_status else "—"
    new_label = ComplaintStatus(new_status).label
    summary = f"{complaint.reference} : {old_label} → {new_label}"
    if reason:
        summary = f"{summary} ({reason})"

    return record_audit_log(
        actor=actor,
        action=action,
        resource_type=AuditResourceType.COMPLAINT,
        resource_id=complaint.pk,
        resource_label=complaint.reference,
        facility=_complaint_facility(complaint),
        summary=summary,
        metadata={
            "reference": complaint.reference,
            "old_status": old_status,
            "new_status": new_status,
            "reason": reason,
        },
    )


def log_complaint_comment_added(
    comment: ComplaintComment,
    *,
    actor,
) -> AuditLog:
    complaint = comment.complaint
    preview = (comment.comment or "").strip()
    if len(preview) > 80:
        preview = f"{preview[:77]}..."

    return record_audit_log(
        actor=actor,
        action=AuditAction.COMPLAINT_COMMENT_ADDED,
        resource_type=AuditResourceType.COMPLAINT,
        resource_id=complaint.pk,
        resource_label=complaint.reference,
        facility=_complaint_facility(complaint),
        summary=f"Commentaire sur {complaint.reference}" + (f" : {preview}" if preview else "."),
        metadata={
            "reference": complaint.reference,
            "comment_id": comment.pk,
        },
    )


def log_complaint_imported(complaint: Complaint, *, actor, via: str = "csv") -> AuditLog:
    via_label = "CSV" if via == "csv" else "saisie staff"
    return record_audit_log(
        actor=actor,
        action=AuditAction.COMPLAINT_IMPORTED,
        resource_type=AuditResourceType.COMPLAINT,
        resource_id=complaint.pk,
        resource_label=complaint.reference,
        facility=_complaint_facility(complaint),
        summary=f"Plainte papier {complaint.reference} importée ({via_label}).",
        metadata={
            "reference": complaint.reference,
            "source": complaint.source,
            "via": via,
        },
    )


def log_complaint_ocr_reviewed(complaint: Complaint, *, actor) -> AuditLog:
    return record_audit_log(
        actor=actor,
        action=AuditAction.COMPLAINT_OCR_REVIEWED,
        resource_type=AuditResourceType.COMPLAINT,
        resource_id=complaint.pk,
        resource_label=complaint.reference,
        facility=_complaint_facility(complaint),
        summary=f"Plainte {complaint.reference} créée après révision OCR.",
        metadata={"reference": complaint.reference, "source": complaint.source},
    )


def get_hospital_audit_queryset(user):
    qs = AuditLog.objects.select_related("actor", "facility").order_by("-created_at")

    if user.role in (UserRole.ADMIN, UserRole.MINISTRY_SUPERVISOR):
        return qs

    if user.role in FACILITY_STAFF_ROLES:
        facility = get_user_facility(user)
        if facility:
            return qs.filter(facility=facility)
        return qs.none()

    return qs.none()


def get_ministry_audit_queryset():
    return AuditLog.objects.select_related("actor", "facility").order_by("-created_at")


def log_user_created(user, *, actor, facility: Facility | None = None) -> AuditLog:
    role_label = user.get_role_display() if hasattr(user, "get_role_display") else user.role
    return record_audit_log(
        actor=actor,
        action=AuditAction.USER_CREATED,
        resource_type=AuditResourceType.USER,
        resource_id=user.pk,
        resource_label=user.username,
        facility=facility,
        summary=f"Compte {user.username} créé ({role_label}).",
        metadata={"username": user.username, "role": user.role},
    )


def log_user_updated(user, *, actor, changes: dict, facility: Facility | None = None) -> AuditLog:
    return record_audit_log(
        actor=actor,
        action=AuditAction.USER_UPDATED,
        resource_type=AuditResourceType.USER,
        resource_id=user.pk,
        resource_label=user.username,
        facility=facility,
        summary=f"Compte {user.username} mis à jour.",
        metadata={"username": user.username, "changes": changes},
    )


def log_user_deactivated(user, *, actor, facility: Facility | None = None) -> AuditLog:
    return record_audit_log(
        actor=actor,
        action=AuditAction.USER_DEACTIVATED,
        resource_type=AuditResourceType.USER,
        resource_id=user.pk,
        resource_label=user.username,
        facility=facility,
        summary=f"Compte {user.username} désactivé.",
        metadata={"username": user.username, "role": user.role},
    )


def log_facility_created(facility: Facility, *, actor) -> AuditLog:
    return record_audit_log(
        actor=actor,
        action=AuditAction.FACILITY_CREATED,
        resource_type=AuditResourceType.FACILITY,
        resource_id=facility.pk,
        resource_label=facility.code,
        facility=facility,
        summary=f"Établissement {facility.code} créé ({facility.name}).",
        metadata={"code": facility.code, "name": facility.name},
    )


def log_facility_updated(facility: Facility, *, actor, changes: dict | None = None) -> AuditLog:
    return record_audit_log(
        actor=actor,
        action=AuditAction.FACILITY_UPDATED,
        resource_type=AuditResourceType.FACILITY,
        resource_id=facility.pk,
        resource_label=facility.code,
        facility=facility,
        summary=f"Établissement {facility.code} mis à jour.",
        metadata={"code": facility.code, "changes": changes or {}},
    )


def log_facility_deactivated(facility: Facility, *, actor) -> AuditLog:
    return record_audit_log(
        actor=actor,
        action=AuditAction.FACILITY_DEACTIVATED,
        resource_type=AuditResourceType.FACILITY,
        resource_id=facility.pk,
        resource_label=facility.code,
        facility=facility,
        summary=f"Établissement {facility.code} désactivé.",
        metadata={"code": facility.code},
    )


def log_facilities_imported(*, actor, created: int, updated: int) -> AuditLog:
    return record_audit_log(
        actor=actor,
        action=AuditAction.FACILITY_IMPORTED,
        resource_type=AuditResourceType.FACILITY,
        resource_id="import",
        resource_label="Import établissements",
        summary=f"Import établissements : {created} créé(s), {updated} mis à jour.",
        metadata={"created": created, "updated": updated},
    )


def log_facility_service_changed(
    facility: Facility,
    *,
    actor,
    service_name: str,
    change: str,
) -> AuditLog:
    return record_audit_log(
        actor=actor,
        action=AuditAction.FACILITY_SERVICE_CHANGED,
        resource_type=AuditResourceType.FACILITY,
        resource_id=facility.pk,
        resource_label=facility.code,
        facility=facility,
        summary=f"Service « {service_name} » — {change} ({facility.code}).",
        metadata={"code": facility.code, "service": service_name, "change": change},
    )


def log_facility_assignment_changed(
    *,
    actor,
    username: str,
    facility: Facility,
    change: str,
) -> AuditLog:
    return record_audit_log(
        actor=actor,
        action=AuditAction.FACILITY_ASSIGNMENT_CHANGED,
        resource_type=AuditResourceType.FACILITY,
        resource_id=facility.pk,
        resource_label=facility.code,
        facility=facility,
        summary=f"Affectation {username} → {facility.code} ({change}).",
        metadata={"username": username, "code": facility.code, "change": change},
    )
