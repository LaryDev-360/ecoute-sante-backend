from __future__ import annotations

import csv
import io
from datetime import datetime

from django.db import transaction
from django.utils.dateparse import parse_date

from apps.accounts.models import User, UserRole
from apps.complaints.attachments import save_complaint_attachments
from apps.complaints.models import (
    Complaint,
    ComplaintCategory,
    ComplaintSource,
    ComplaintType,
    Severity,
    SubmissionType,
    SubmitterProfile,
)
from apps.complaints.services import ComplaintValidationError, validate_complaint_submission
from apps.facilities.models import Facility, FacilityService
from apps.facilities.services import get_user_facility, user_can_access_facility

CSV_REQUIRED_COLUMNS = {
    "facility_code",
    "service_name",
    "category_name",
    "title",
    "description",
    "severity",
}

CSV_OPTIONAL_COLUMNS = {
    "complaint_type",
    "submission_type",
    "submitter_profile",
    "phone",
    "email",
    "incident_date",
    "registered_on_paper_at",
    "requested_actions",
}


class ComplaintImportError(Exception):
    def __init__(self, message, row: int | None = None):
        self.message = message
        self.row = row
        super().__init__(message)


def _parse_date(value: str | None):
    if not value or not str(value).strip():
        return None
    parsed = parse_date(str(value).strip())
    if parsed:
        return parsed
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    raise ComplaintImportError(f"Date invalide : {value}")


def _resolve_category(name: str) -> ComplaintCategory:
    name = (name or "").strip()
    if not name:
        raise ComplaintImportError("Catégorie requise.")
    category = ComplaintCategory.objects.filter(name__iexact=name, active=True).first()
    if category:
        return category
    category = ComplaintCategory.objects.filter(name__icontains=name, active=True).first()
    if category:
        return category
    raise ComplaintImportError(f"Catégorie introuvable : {name}")


def _resolve_service(facility: Facility, name: str) -> FacilityService:
    name = (name or "").strip()
    if not name:
        raise ComplaintImportError("Service requis.")
    service = FacilityService.objects.filter(
        facility=facility,
        name__iexact=name,
        active=True,
    ).first()
    if service:
        return service
    service = FacilityService.objects.filter(
        facility=facility,
        name__icontains=name,
        active=True,
    ).first()
    if service:
        return service
    raise ComplaintImportError(
        f"Service « {name} » introuvable pour l'établissement {facility.code}."
    )


def _resolve_facility(*, actor: User, facility_code: str | None, facility_id: int | None) -> Facility:
    staff_facility = get_user_facility(actor)
    if actor.role in (UserRole.HOSPITAL_MANAGER, UserRole.FACILITY_AGENT):
        if staff_facility is None:
            raise ComplaintImportError("Aucun établissement rattaché à votre compte.")
        return staff_facility

    if facility_id:
        facility = Facility.objects.filter(pk=facility_id, active=True).first()
    elif facility_code:
        facility = Facility.objects.filter(code__iexact=facility_code.strip(), active=True).first()
    else:
        raise ComplaintImportError("Code ou identifiant d'établissement requis.")

    if not facility:
        raise ComplaintImportError("Établissement introuvable ou inactif.")
    if not user_can_access_facility(actor, facility):
        raise ComplaintImportError("Accès refusé à cet établissement.")
    return facility


def _normalize_choice(value: str | None, choices: dict, default: str) -> str:
    raw = (value or "").strip().upper()
    if not raw:
        return default
    if raw in choices:
        return raw
    for code, label in choices.items():
        if raw == label.upper():
            return code
    raise ComplaintImportError(f"Valeur invalide : {value}")


def build_complaint_data_from_row(row: dict, *, actor: User, row_number: int) -> dict:
    facility = _resolve_facility(
        actor=actor,
        facility_code=row.get("facility_code"),
        facility_id=int(row["facility_id"]) if row.get("facility_id") else None,
    )
    service = _resolve_service(facility, row.get("service_name", ""))
    category = _resolve_category(row.get("category_name", ""))

    title = (row.get("title") or "").strip()
    description = (row.get("description") or "").strip()
    if len(title) < 3:
        raise ComplaintImportError("Titre requis (3 caractères minimum).", row=row_number)
    if len(description) < 10:
        raise ComplaintImportError("Description requise (10 caractères minimum).", row=row_number)

    severity = _normalize_choice(row.get("severity"), dict(Severity.choices), Severity.MEDIUM)
    complaint_type = _normalize_choice(
        row.get("complaint_type"),
        dict(ComplaintType.choices),
        ComplaintType.COMPLAINT,
    )
    submission_type = _normalize_choice(
        row.get("submission_type"),
        dict(SubmissionType.choices),
        SubmissionType.ANONYMOUS,
    )
    submitter_profile = _normalize_choice(
        row.get("submitter_profile"),
        dict(SubmitterProfile.choices),
        SubmitterProfile.CITIZEN,
    )

    return {
        "submitter_profile": submitter_profile,
        "submission_type": submission_type,
        "complaint_type": complaint_type,
        "facility": facility,
        "service": service,
        "category": category,
        "title": title,
        "description": description,
        "severity": severity,
        "phone": (row.get("phone") or "").strip(),
        "email": (row.get("email") or "").strip(),
        "requested_actions": (row.get("requested_actions") or "").strip(),
        "incident_date": _parse_date(row.get("incident_date")),
        "registered_on_paper_at": _parse_date(row.get("registered_on_paper_at")),
        "source": ComplaintSource.PAPER,
    }


@transaction.atomic
def create_imported_complaint(
    data: dict,
    *,
    actor: User,
    attachments=None,
    via: str = "csv",
    ocr_reviewed: bool = False,
) -> Complaint:
    attachments = attachments or []
    payload = {**data, "source": ComplaintSource.PAPER, "imported_by": actor}

    try:
        validate_complaint_submission(payload, user=actor)
    except ComplaintValidationError as exc:
        raise ComplaintImportError(exc.message) from exc

    complaint = Complaint.objects.create(**payload)
    if attachments:
        save_complaint_attachments(complaint, attachments)

    from apps.audit.services import log_complaint_imported, log_complaint_ocr_reviewed

    log_complaint_imported(complaint, actor=actor, via=via)
    if ocr_reviewed:
        log_complaint_ocr_reviewed(complaint, actor=actor)

    return complaint


def import_complaints_csv(actor: User, file_content: str) -> dict:
    reader = csv.DictReader(io.StringIO(file_content))
    if not reader.fieldnames:
        raise ComplaintImportError("Fichier CSV vide.")

    headers = {h.strip().lower() for h in reader.fieldnames if h}
    missing = CSV_REQUIRED_COLUMNS - headers
    if missing:
        raise ComplaintImportError(
            f"Colonnes CSV requises manquantes : {', '.join(sorted(missing))}."
        )

    created = []
    errors = []

    for index, raw_row in enumerate(reader, start=2):
        row = {k.strip().lower(): (v or "").strip() for k, v in raw_row.items() if k}
        if not any(row.values()):
            continue
        try:
            data = build_complaint_data_from_row(row, actor=actor, row_number=index)
            complaint = create_imported_complaint(data, actor=actor, via="csv")
            created.append(
                {
                    "reference": complaint.reference,
                    "id": complaint.id,
                    "title": complaint.title,
                }
            )
        except ComplaintImportError as exc:
            errors.append({"row": exc.row or index, "message": exc.message})

    if not created and errors:
        raise ComplaintImportError(errors[0]["message"], row=errors[0]["row"])

    return {
        "created": len(created),
        "errors": errors,
        "complaints": created,
    }
