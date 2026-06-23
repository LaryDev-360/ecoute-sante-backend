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
