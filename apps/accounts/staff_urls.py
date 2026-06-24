from django.urls import path

from apps.accounts.user_views import (
    HospitalUserDetailView,
    HospitalUserListCreateView,
    MinistryUserDetailView,
    MinistryUserListCreateView,
)

app_name = "staff_users"

urlpatterns = [
    path("ministry/users/", MinistryUserListCreateView.as_view(), name="ministry-users"),
    path(
        "ministry/users/<int:pk>/",
        MinistryUserDetailView.as_view(),
        name="ministry-user-detail",
    ),
    path("hospital/users/", HospitalUserListCreateView.as_view(), name="hospital-users"),
    path(
        "hospital/users/<int:pk>/",
        HospitalUserDetailView.as_view(),
        name="hospital-user-detail",
    ),
]
