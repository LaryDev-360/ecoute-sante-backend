"""Build a prefilled complaint payload from a Gbègbe voice mediation result.

The transcription and summary are used internally; the final review still happens
in the public /signaler wizard.
"""

import unicodedata

from apps.complaints.models import (
    ComplaintCategory,
    ComplaintType,
    Severity,
    SubmissionType,
    SubmitterProfile,
)
from apps.facilities.models import FacilityService


GBEGBE_TYPE_TO_COMPLAINT_TYPE = {
    "plainte": ComplaintType.COMPLAINT,
    "suggestion": ComplaintType.SUGGESTION,
    "felicitation": ComplaintType.APPRECIATION,
}

GBEGBE_GRAVITY_TO_SEVERITY = {
    "faible": Severity.LOW,
    "moyen": Severity.MEDIUM,
    "urgent": Severity.URGENT,
}


def _normalize(text: str) -> str:
    text = (text or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text


def _map_complaint_type(gbegbe_type: str) -> ComplaintType:
    key = _normalize(gbegbe_type)
    return GBEGBE_TYPE_TO_COMPLAINT_TYPE.get(key, ComplaintType.COMPLAINT)


def _map_severity(gbegbe_gravity: str) -> Severity:
    key = _normalize(gbegbe_gravity)
    return GBEGBE_GRAVITY_TO_SEVERITY.get(key, Severity.MEDIUM)


def _resolve_category(gbegbe_category: str | None = None) -> ComplaintCategory | None:
    active = ComplaintCategory.objects.filter(active=True)
    if gbegbe_category:
        name = gbegbe_category.strip()
        exact = active.filter(name__iexact=name).first()
        if exact:
            return exact
        partial = active.filter(name__icontains=name).first()
        if partial:
            return partial
    return active.filter(name__iexact="Autre").first() or active.first()


def _resolve_service(gbegbe_service: str) -> FacilityService | None:
    service_text = _normalize(gbegbe_service)
    if not service_text:
        return None

    active_services = FacilityService.objects.filter(active=True).select_related("facility")

    # Exact match (case and accent insensitive)
    exact = active_services.filter(name__iexact=gbegbe_service.strip()).first()
    if exact:
        return exact

    # Partial containment match
    candidates = list(active_services)
    for candidate in candidates:
        normalized_name = _normalize(candidate.name)
        if service_text in normalized_name or normalized_name in service_text:
            return candidate

    return None


def build_prefill_payload(gbegbe_result: dict) -> dict:
    """
    Convert a Gbègbe result into a payload that can prefill the /signaler form.

    Returns:
        {
            "submitter_profile": str,
            "submission_type": str,
            "complaint_type": str,
            "nature_ui": str,          # "plainte" | "suggestion" | "felicitation"
            "facility": int | None,
            "service": int | None,
            "category": int | None,
            "title": str,
            "description": str,
            "severity": str,
            "detected_language": str,
            "requested_actions": str,
            "needs_manual_review": bool,
        }
    """
    complaint_type = _map_complaint_type(gbegbe_result.get("type", ""))

    # nature_ui is used by the frontend wizard
    nature_ui_map = {
        ComplaintType.COMPLAINT: "plainte",
        ComplaintType.SUGGESTION: "suggestion",
        ComplaintType.APPRECIATION: "felicitation",
    }
    nature_ui = nature_ui_map.get(complaint_type, "plainte")

    severity = _map_severity(gbegbe_result.get("gravite", ""))
    service = _resolve_service(gbegbe_result.get("service", ""))
    category = _resolve_category(gbegbe_result.get("category"))

    title = (gbegbe_result.get("resume") or "").strip()
    description = (gbegbe_result.get("transcription_fr") or "").strip()

    # Fallback title if the model did not provide a resume
    if not title and description:
        title = description[:80]

    needs_manual_review = service is None or category is None or not title or not description

    return {
        "submitter_profile": SubmitterProfile.CITIZEN,
        "submission_type": SubmissionType.ANONYMOUS,
        "complaint_type": complaint_type,
        "nature_ui": nature_ui,
        "facility": service.facility_id if service else None,
        "service": service.id if service else None,
        "category": category.id if category else None,
        "title": title,
        "description": description,
        "severity": severity,
        "detected_language": (gbegbe_result.get("langue_detectee") or "").strip(),
        "requested_actions": "",
        "needs_manual_review": needs_manual_review,
    }
