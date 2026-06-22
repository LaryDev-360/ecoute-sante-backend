from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.facilities.views import (
    FacilityCSVImportView,
    FacilityServiceViewSet,
    FacilityViewSet,
    UserFacilityAssignmentViewSet,
)

router = DefaultRouter()
router.register("facilities", FacilityViewSet, basename="facility")
router.register("assignments", UserFacilityAssignmentViewSet, basename="assignment")

service_list = FacilityServiceViewSet.as_view({"get": "list", "post": "create"})
service_detail = FacilityServiceViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)

app_name = "facilities"

urlpatterns = [
    path("facilities/import/csv/", FacilityCSVImportView.as_view(), name="facility-import-csv"),
    path(
        "facilities/<int:facility_pk>/services/",
        service_list,
        name="facility-services-list",
    ),
    path(
        "facilities/<int:facility_pk>/services/<int:pk>/",
        service_detail,
        name="facility-services-detail",
    ),
    path("", include(router.urls)),
]
