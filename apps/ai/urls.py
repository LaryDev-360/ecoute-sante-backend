from django.urls import path

from apps.ai.views import ClassifyView, GbegbePrefillView, GbegbeView

app_name = "ai"

urlpatterns = [
    path("ai/classify/", ClassifyView.as_view(), name="classify"),
    path("ai/mediateur/", GbegbeView.as_view(), name="mediateur"),
    path("ai/mediateur/prefill/", GbegbePrefillView.as_view(), name="mediateur-prefill"),
]
