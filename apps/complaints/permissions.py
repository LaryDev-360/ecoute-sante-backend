from rest_framework.permissions import BasePermission

from apps.accounts.models import UserRole
from apps.complaints.hospital_services import FACILITY_STAFF_ROLES
from apps.facilities.services import get_user_facility


class IsHospitalComplaintStaff(BasePermission):
    """Responsable ou agent rattaché à un établissement."""

    message = "Accès réservé au personnel d'établissement affecté."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.role in (UserRole.ADMIN, UserRole.MINISTRY_SUPERVISOR):
            return True
        if request.user.role in FACILITY_STAFF_ROLES:
            return get_user_facility(request.user) is not None
        return False
