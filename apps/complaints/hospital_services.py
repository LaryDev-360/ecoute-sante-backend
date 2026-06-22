from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F

from apps.accounts.models import User, UserRole
from apps.complaints.models import Complaint, ComplaintComment, ComplaintStatus
from apps.facilities.services import get_user_facility

FACILITY_STAFF_ROLES = (UserRole.HOSPITAL_MANAGER, UserRole.FACILITY_AGENT)

IN_PROGRESS_STATUSES = (
    ComplaintStatus.UNDER_REVIEW,
    ComplaintStatus.IN_PROGRESS,
    ComplaintStatus.WAITING_INFO,
)

RESOLVED_STATUSES = (ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED)


def get_hospital_complaints_queryset(user):
    """Plaintes visibles par le personnel d'établissement (scope facility)."""
    qs = (
        Complaint.objects.filter(is_archived=False)
        .select_related("facility", "service", "category", "submitted_by", "reported_agent")
        .prefetch_related("attachments", "comments__author", "status_history__changed_by")
    )

    if user.role in (UserRole.ADMIN, UserRole.MINISTRY_SUPERVISOR):
        return qs

    if user.role in FACILITY_STAFF_ROLES:
        facility = get_user_facility(user)
        if facility:
            return qs.filter(facility=facility)
        return qs.none()

    return qs.none()


def user_can_access_complaint(user, complaint: Complaint) -> bool:
    return get_hospital_complaints_queryset(user).filter(pk=complaint.pk).exists()


def build_hospital_dashboard(user) -> dict:
    qs = get_hospital_complaints_queryset(user)
    facility = get_user_facility(user)

    total = qs.count()
    received = qs.filter(current_status=ComplaintStatus.RECEIVED).count()
    in_progress = qs.filter(current_status__in=IN_PROGRESS_STATUSES).count()
    resolved = qs.filter(current_status__in=RESOLVED_STATUSES).count()
    rejected = qs.filter(current_status=ComplaintStatus.REJECTED).count()

    resolved_qs = qs.filter(current_status__in=RESOLVED_STATUSES)
    avg_duration = resolved_qs.aggregate(
        avg=Avg(
            ExpressionWrapper(F("updated_at") - F("created_at"), output_field=DurationField())
        )
    )["avg"]
    avg_processing_hours = round(avg_duration.total_seconds() / 3600, 2) if avg_duration else None

    top_categories = list(
        qs.values("category__id", "category__name")
        .annotate(count=Count("id"))
        .order_by("-count")[:5]
    )
    top_services = list(
        qs.values("service__id", "service__name")
        .annotate(count=Count("id"))
        .order_by("-count")[:5]
    )

    return {
        "facility": {
            "id": facility.id,
            "name": facility.name,
            "code": facility.code,
        }
        if facility
        else None,
        "summary": {
            "total": total,
            "received": received,
            "in_progress": in_progress,
            "resolved": resolved,
            "rejected": rejected,
            "avg_processing_hours": avg_processing_hours,
        },
        "top_categories": [
            {"id": row["category__id"], "name": row["category__name"], "count": row["count"]}
            for row in top_categories
        ],
        "top_services": [
            {"id": row["service__id"], "name": row["service__name"], "count": row["count"]}
            for row in top_services
        ],
    }


def add_complaint_comment(complaint: Complaint, author, comment: str) -> ComplaintComment:
    return ComplaintComment.objects.create(
        complaint=complaint,
        author=author,
        comment=comment,
    )
