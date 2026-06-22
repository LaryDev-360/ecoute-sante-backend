from django.urls import path

from apps.complaints.views import (
    ComplaintCategoryListView,
    ComplaintSubmitView,
    ComplaintTrackView,
    SubmitterProfileListView,
)

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
]
