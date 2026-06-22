from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) == "ADMIN"
        )


class IsMinistrySupervisor(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) == "MINISTRY_SUPERVISOR"
        )


class IsHospitalManager(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) == "HOSPITAL_MANAGER"
        )


class IsMinistryOrAdmin(BasePermission):
    def has_permission(self, request, view):
        role = getattr(request.user, "role", None)
        return request.user.is_authenticated and role in ("ADMIN", "MINISTRY_SUPERVISOR")


class IsHospitalStaff(BasePermission):
    """Hospital manager or admin."""

    def has_permission(self, request, view):
        role = getattr(request.user, "role", None)
        return request.user.is_authenticated and role in ("ADMIN", "HOSPITAL_MANAGER")
