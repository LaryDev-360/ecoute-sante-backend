from rest_framework import serializers


class WhatsappWebhookSerializer(serializers.Serializer):
    """
    Documentation (Swagger) de la charge utile Green API. La structure réelle
    est imbriquée et variable selon `typeWebhook` ; le parsing est fait
    manuellement dans la vue.
    """

    typeWebhook = serializers.CharField(help_text="Ex: incomingMessageReceived")
    senderData = serializers.DictField(help_text="Contient `sender` (chatId).")
    messageData = serializers.DictField(help_text="Contient `typeMessage` et le contenu.")
