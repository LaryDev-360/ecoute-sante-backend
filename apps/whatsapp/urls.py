from django.urls import path

from apps.whatsapp.views import WhatsappWebhookView

app_name = "whatsapp"

urlpatterns = [
    path("webhook/", WhatsappWebhookView.as_view(), name="webhook"),
]
