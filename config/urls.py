"""
URL configuration for Santé Écoute.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

from apps.complaints.ussd_views import UssdView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("ussd/", UssdView.as_view(), name="ussd"),
    path("whatsapp/", include("apps.whatsapp.urls")),
    path("api/v1/", include("apps.common.urls")),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.facilities.urls")),
    path("api/v1/", include("apps.complaints.urls")),
    path("api/v1/", include("apps.ai.urls")),
    # OpenAPI / Swagger
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
