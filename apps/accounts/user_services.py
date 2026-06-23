import secrets
import string

from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from apps.accounts.models import User, UserRole
from apps.audit.services import log_user_created, log_user_deactivated, log_user_updated
from apps.facilities.models import Facility, UserFacilityAssignment
from apps.facilities.services import assign_manager_to_facility, get_user_facility

MINISTRY_MANAGED_ROLES = (
    UserRole.HOSPITAL_MANAGER,
    UserRole.FACILITY_AGENT,
    UserRole.MINISTRY_SUPERVISOR,
)

FACILITY_BOUND_ROLES = (UserRole.HOSPITAL_MANAGER, UserRole.FACILITY_AGENT)


def generate_temporary_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def get_ministry_users_queryset():
    return (
        User.objects.filter(role__in=MINISTRY_MANAGED_ROLES)
        .select_related("facility_assignment__facility")
        .order_by("-date_joined")
    )


def get_hospital_users_queryset(actor: User):
    facility = get_user_facility(actor)
    if not facility or actor.role != UserRole.HOSPITAL_MANAGER:
        return User.objects.none()
    return (
        User.objects.filter(
            role=UserRole.FACILITY_AGENT,
            facility_assignment__facility=facility,
        )
        .select_related("facility_assignment__facility")
        .order_by("-date_joined")
    )


def user_belongs_to_facility(user: User, facility: Facility) -> bool:
    assignment = getattr(user, "facility_assignment", None)
    if assignment is None:
        try:
            assignment = user.facility_assignment
        except UserFacilityAssignment.DoesNotExist:
            return False
    return assignment.facility_id == facility.pk


def ministry_can_manage_user(actor: User, target: User) -> bool:
    if actor.role not in (UserRole.ADMIN, UserRole.MINISTRY_SUPERVISOR):
        return False
    return target.role in MINISTRY_MANAGED_ROLES


def hospital_can_manage_user(actor: User, target: User) -> bool:
    if actor.role != UserRole.HOSPITAL_MANAGER:
        return False
    if target.role != UserRole.FACILITY_AGENT:
        return False
    facility = get_user_facility(actor)
    return facility is not None and user_belongs_to_facility(target, facility)


def _validate_unique_user_fields(attrs: dict) -> None:
    username = attrs.get("username", "").strip()
    email = attrs.get("email", "").strip().lower()
    phone = (attrs.get("phone") or "").strip()

    if User.objects.filter(username__iexact=username).exists():
        raise ValueError("username_taken")
    if User.objects.filter(email__iexact=email).exists():
        raise ValueError("email_taken")
    if phone and User.objects.filter(phone=phone).exists():
        raise ValueError("phone_taken")


@transaction.atomic
def create_staff_user(
    *,
    actor: User,
    role: str,
    username: str,
    email: str,
    password: str | None = None,
    phone: str = "",
    first_name: str = "",
    last_name: str = "",
    facility: Facility | None = None,
) -> tuple[User, str]:
    attrs = {
        "username": username.strip(),
        "email": email.strip().lower(),
        "phone": phone.strip(),
    }
    _validate_unique_user_fields(attrs)

    if role in FACILITY_BOUND_ROLES and facility is None:
        raise ValueError("facility_required")

    if role == UserRole.MINISTRY_SUPERVISOR:
        facility = None

    initial_password = password or generate_temporary_password()
    validate_password(initial_password)

    user = User.objects.create_user(
        username=attrs["username"],
        email=attrs["email"],
        password=initial_password,
        role=role,
        phone=attrs["phone"],
        first_name=first_name.strip(),
        last_name=last_name.strip(),
    )

    if facility is not None:
        assign_manager_to_facility(user, facility)

    log_user_created(user, actor=actor, facility=facility)
    return user, initial_password


@transaction.atomic
def update_staff_user(
    *,
    actor: User,
    target: User,
    data: dict,
) -> User:
    if target.pk == actor.pk and data.get("is_active") is False:
        raise ValueError("cannot_deactivate_self")

    changes: dict = {}
    allowed = ("first_name", "last_name", "phone", "email", "is_active")
    facility = get_user_facility(target)

    for field in allowed:
        if field not in data:
            continue
        new_value = data[field]
        if field == "email":
            new_value = (new_value or "").strip().lower()
            if (
                new_value
                and User.objects.filter(email__iexact=new_value)
                .exclude(pk=target.pk)
                .exists()
            ):
                raise ValueError("email_taken")
        if field == "phone":
            new_value = (new_value or "").strip()
            if (
                new_value
                and User.objects.filter(phone=new_value).exclude(pk=target.pk).exists()
            ):
                raise ValueError("phone_taken")

        old_value = getattr(target, field)
        if old_value != new_value:
            changes[field] = {"from": old_value, "to": new_value}
            setattr(target, field, new_value)

    if not changes:
        return target

    target.save()

    if changes.get("is_active", {}).get("to") is False:
        log_user_deactivated(target, actor=actor, facility=facility)
    else:
        log_user_updated(target, actor=actor, changes=changes, facility=facility)
    return target
