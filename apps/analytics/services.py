from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F
from django.db.models.functions import TruncMonth

from apps.complaints.models import Complaint, ComplaintStatus

RESOLVED_STATUSES = (ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED)
IN_PROGRESS_STATUSES = (
    ComplaintStatus.UNDER_REVIEW,
    ComplaintStatus.IN_PROGRESS,
    ComplaintStatus.WAITING_INFO,
)


def get_base_complaints_queryset():
    return Complaint.objects.filter(is_archived=False).select_related(
        "facility",
        "service",
        "category",
    )


def _avg_processing_hours(qs):
    resolved_qs = qs.filter(current_status__in=RESOLVED_STATUSES)
    avg_duration = resolved_qs.aggregate(
        avg=Avg(
            ExpressionWrapper(F("updated_at") - F("created_at"), output_field=DurationField())
        )
    )["avg"]
    return round(avg_duration.total_seconds() / 3600, 2) if avg_duration else None


def _rate(part, total):
    return round(part / total * 100, 2) if total else 0.0


def build_ministry_dashboard(qs) -> dict:
    total = qs.count()
    resolved = qs.filter(current_status__in=RESOLVED_STATUSES).count()
    rejected = qs.filter(current_status=ComplaintStatus.REJECTED).count()
    received = qs.filter(current_status=ComplaintStatus.RECEIVED).count()
    in_progress = qs.filter(current_status__in=IN_PROGRESS_STATUSES).count()

    by_region = list(
        qs.values("facility__region")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    by_facility = list(
        qs.values(
            "facility__id",
            "facility__name",
            "facility__code",
            "facility__region",
        )
        .annotate(count=Count("id"))
        .order_by("-count")[:20]
    )
    monthly_trend = list(
        qs.annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )

    return {
        "summary": {
            "total": total,
            "received": received,
            "in_progress": in_progress,
            "resolved": resolved,
            "rejected": rejected,
            "resolution_rate": _rate(resolved, total),
            "rejection_rate": _rate(rejected, total),
            "avg_processing_hours": _avg_processing_hours(qs),
        },
        "by_region": [
            {"region": row["facility__region"], "count": row["count"]} for row in by_region
        ],
        "by_facility": [
            {
                "id": row["facility__id"],
                "name": row["facility__name"],
                "code": row["facility__code"],
                "region": row["facility__region"],
                "count": row["count"],
            }
            for row in by_facility
        ],
        "monthly_trend": [
            {"month": row["month"].strftime("%Y-%m") if row["month"] else None, "count": row["count"]}
            for row in monthly_trend
        ],
    }


def build_ministry_analytics(qs) -> dict:
    by_status = list(
        qs.values("current_status").annotate(count=Count("id")).order_by("-count")
    )
    by_severity = list(
        qs.values("severity").annotate(count=Count("id")).order_by("-count")
    )
    by_category = list(
        qs.values("category__id", "category__name")
        .annotate(count=Count("id"))
        .order_by("-count")[:15]
    )
    by_complaint_type = list(
        qs.values("complaint_type").annotate(count=Count("id")).order_by("-count")
    )
    by_submitter_profile = list(
        qs.values("submitter_profile").annotate(count=Count("id")).order_by("-count")
    )
    region_status = list(
        qs.values("facility__region", "current_status")
        .annotate(count=Count("id"))
        .order_by("facility__region", "current_status")
    )

    return {
        "by_status": [
            {"status": row["current_status"], "count": row["count"]} for row in by_status
        ],
        "by_severity": [
            {"severity": row["severity"], "count": row["count"]} for row in by_severity
        ],
        "by_category": [
            {
                "id": row["category__id"],
                "name": row["category__name"],
                "count": row["count"],
            }
            for row in by_category
        ],
        "by_complaint_type": [
            {"complaint_type": row["complaint_type"], "count": row["count"]}
            for row in by_complaint_type
        ],
        "by_submitter_profile": [
            {"submitter_profile": row["submitter_profile"], "count": row["count"]}
            for row in by_submitter_profile
        ],
        "region_by_status": [
            {
                "region": row["facility__region"],
                "status": row["current_status"],
                "count": row["count"],
            }
            for row in region_status
        ],
    }
