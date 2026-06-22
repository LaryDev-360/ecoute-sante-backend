import csv
import io

from django.db import transaction

from apps.accounts.models import User, UserRole
from apps.facilities.models import (
    Facility,
    FacilityService,
    FacilityType,
    UserFacilityAssignment,
)

DEFAULT_SERVICES = [
    "Accueil",
    "Consultation",
    "Laboratoire",
    "Pharmacie",
    "Maternité",
    "Urgences",
    "Caisse",
    "Hospitalisation",
]


def get_user_facility(user: User) -> Facility | None:
    """Return the facility assigned to a hospital manager, or None."""
    if not user.is_authenticated:
        return None
    if user.role in (UserRole.ADMIN, UserRole.MINISTRY_SUPERVISOR):
        return None
    if user.role in (UserRole.HOSPITAL_MANAGER, UserRole.FACILITY_AGENT):
        assignment = (
            UserFacilityAssignment.objects.filter(user=user)
            .select_related("facility")
            .first()
        )
        return assignment.facility if assignment else None
    return None


def get_facilities_queryset_for_user(user: User):
    """Scope facility queryset based on user role."""
    qs = Facility.objects.prefetch_related("services")

    if user.role in (UserRole.ADMIN, UserRole.MINISTRY_SUPERVISOR):
        return qs

    if user.role in (UserRole.HOSPITAL_MANAGER, UserRole.FACILITY_AGENT):
        facility = get_user_facility(user)
        if facility:
            return qs.filter(pk=facility.pk)
        return qs.none()

    return qs.none()


def user_can_access_facility(user: User, facility: Facility) -> bool:
    if user.role in (UserRole.ADMIN, UserRole.MINISTRY_SUPERVISOR):
        return True
    own = get_user_facility(user)
    return own is not None and own.pk == facility.pk


def assign_manager_to_facility(user: User, facility: Facility) -> UserFacilityAssignment:
    assignment, _ = UserFacilityAssignment.objects.update_or_create(
        user=user,
        defaults={"facility": facility},
    )
    return assignment


def deactivate_facility(facility: Facility) -> None:
    facility.active = False
    facility.save(update_fields=["active"])


@transaction.atomic
def import_facilities_payload(user: User, facilities_data: list[dict]) -> dict:
    role = user.role
    if role == UserRole.HOSPITAL_MANAGER and len(facilities_data) != 1:
        raise ValueError(
            "Un responsable d'établissement ne peut importer qu'un seul établissement."
        )
    if role == UserRole.HOSPITAL_MANAGER and get_user_facility(user):
        raise ValueError("Vous êtes déjà rattaché à un établissement.")

    created_count = 0
    updated_count = 0
    results = []

    for entry in facilities_data:
        services = entry.pop("services", DEFAULT_SERVICES)
        code = entry["code"]

        facility, created = Facility.objects.update_or_create(
            code=code,
            defaults=entry,
        )
        if created:
            created_count += 1
        else:
            updated_count += 1

        for service_name in services:
            FacilityService.objects.get_or_create(
                facility=facility,
                name=service_name,
                defaults={"active": True},
            )

        if role == UserRole.HOSPITAL_MANAGER:
            assign_manager_to_facility(user, facility)

        results.append({"code": facility.code, "id": facility.id, "created": created})

    return {
        "created": created_count,
        "updated": updated_count,
        "facilities": results,
    }


def import_facilities_csv(user: User, file_content: str) -> dict:
    reader = csv.DictReader(io.StringIO(file_content))
    facilities_map: dict[str, dict] = {}

    required = {"code", "name", "facility_type", "region", "city", "address"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise ValueError(
            f"Colonnes CSV requises : {', '.join(sorted(required))}. "
            "Optionnel : services (séparés par |)"
        )

    for row in reader:
        code = row["code"].strip()
        if code not in facilities_map:
            facility_type = row["facility_type"].strip().upper()
            if facility_type not in FacilityType.values:
                raise ValueError(f"Type d'établissement invalide : {facility_type}")

            facilities_map[code] = {
                "code": code,
                "name": row["name"].strip(),
                "facility_type": facility_type,
                "region": row["region"].strip(),
                "city": row["city"].strip(),
                "address": row["address"].strip(),
                "active": row.get("active", "true").strip().lower() in ("1", "true", "yes", "oui"),
                "services": [],
            }

        services_raw = row.get("services", "").strip()
        if services_raw:
            for name in services_raw.split("|"):
                name = name.strip()
                if name and name not in facilities_map[code]["services"]:
                    facilities_map[code]["services"].append(name)

    if not facilities_map:
        raise ValueError("Le fichier CSV est vide.")

    return import_facilities_payload(user, list(facilities_map.values()))
