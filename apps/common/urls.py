from django.urls import path

from apps.common.views import HealthCheckView

app_name = "common"

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
]
