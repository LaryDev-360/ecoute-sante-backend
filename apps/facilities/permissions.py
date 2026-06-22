from apps.accounts.models import UserRole
from apps.facilities.services import get_user_facility
from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsFacilityAdmin(BasePermission):
    """Admin ou superviseur ministère."""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role in (UserRole.ADMIN, UserRole.MINISTRY_SUPERVISOR)
        )


class CanManageFacilities(BasePermission):
    """Lecture pour tous les authentifiés ; écriture selon le rôle."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True

        role = request.user.role
        if role in (UserRole.ADMIN, UserRole.MINISTRY_SUPERVISOR):
            return True

        if role == UserRole.HOSPITAL_MANAGER:
            unassigned = get_user_facility(request.user) is None
            action = getattr(view, "action", None)
            is_import = action in ("create", "import_facilities") or (
                request.method == "POST" and "import" in request.path
            )
            if is_import:
                return unassigned
            return not unassigned

        return False

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        role = request.user.role
        if view.action == "destroy":
            return role in (UserRole.ADMIN, UserRole.MINISTRY_SUPERVISOR)

        if role in (UserRole.ADMIN, UserRole.MINISTRY_SUPERVISOR):
            return True

        if role == UserRole.HOSPITAL_MANAGER:
            own = get_user_facility(request.user)
            return own is not None and own.pk == obj.pk

        return False


class CanManageFacilityServices(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        role = request.user.role
        if role in (UserRole.ADMIN, UserRole.MINISTRY_SUPERVISOR):
            return True
        return role == UserRole.HOSPITAL_MANAGER and get_user_facility(request.user) is not None

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        role = request.user.role
        if role in (UserRole.ADMIN, UserRole.MINISTRY_SUPERVISOR):
            return True
        own = get_user_facility(request.user)
        return own is not None and obj.facility_id == own.pk


class CanManageAssignments(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role in (UserRole.ADMIN, UserRole.MINISTRY_SUPERVISOR)
        )
