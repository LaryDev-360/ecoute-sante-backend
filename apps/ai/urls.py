from django.urls import path

from apps.ai.views import ClassifyView

app_name = "ai"

urlpatterns = [
    path("ai/classify/", ClassifyView.as_view(), name="classify"),
]
