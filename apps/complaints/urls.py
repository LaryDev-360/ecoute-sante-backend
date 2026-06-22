from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.complaints.hospital_views import HospitalComplaintViewSet, HospitalDashboardView
from apps.complaints.views import (
    ComplaintCategoryListView,
    ComplaintSubmitView,
    ComplaintTrackView,
    SubmitterProfileListView,
)

router = DefaultRouter()
router.register("hospital/complaints", HospitalComplaintViewSet, basename="hospital-complaint")

app_name = "complaints"

urlpatterns = [
    path("complaints/", ComplaintSubmitView.as_view(), name="complaint-submit"),
    path(
        "complaints/track/<str:reference>/",
        ComplaintTrackView.as_view(),
        name="complaint-track",
    ),
    path(
        "complaints/meta/submitter-profiles/",
        SubmitterProfileListView.as_view(),
        name="submitter-profiles",
    ),
    path(
        "complaints/categories/",
        ComplaintCategoryListView.as_view(),
        name="complaint-categories",
    ),
    path("hospital/dashboard/", HospitalDashboardView.as_view(), name="hospital-dashboard"),
    path("", include(router.urls)),
]
