from django.urls import path

from apps.audit.views import HospitalAuditLogListView, MinistryAuditLogListView

app_name = "audit"

urlpatterns = [
    path("hospital/audit-logs/", HospitalAuditLogListView.as_view(), name="hospital-audit-logs"),
    path("ministry/audit-logs/", MinistryAuditLogListView.as_view(), name="ministry-audit-logs"),
]
