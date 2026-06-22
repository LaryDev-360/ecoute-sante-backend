from rest_framework import serializers


class ClassifyRequestSerializer(serializers.Serializer):
    description = serializers.CharField(
        min_length=10,
        max_length=5000,
        help_text="Texte libre décrivant le signalement.",
    )


class ClassifyResponseSerializer(serializers.Serializer):
    category = serializers.CharField(help_text="Catégorie suggérée (indicative).")
    priority = serializers.ChoiceField(
        choices=["LOW", "MEDIUM", "HIGH", "URGENT"],
        help_text="Priorité suggérée (indicative).",
    )
    disclaimer = serializers.CharField(
        help_text="Rappel : la suggestion n'est pas appliquée automatiquement.",
    )
