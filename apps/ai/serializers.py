import base64
import binascii

from rest_framework import serializers

from apps.ai.services.mediateur import SUPPORTED_FORMATS

_FORMAT_BY_EXTENSION = {
    "ogg": "ogg",
    "oga": "ogg",
    "mp3": "mp3",
    "wav": "wav",
    "webm": "webm",
}


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


class GbegbeRequestSerializer(serializers.Serializer):
    """
    Accepte l'audio de deux façons :
    - multipart/form-data : champ `audio` (fichier) + `format` optionnel
    - application/json : `audio_base64` + `format` (par défaut « ogg »)
    Produit un `validated_data` normalisé avec `audio_base64` et `format`.
    """

    audio = serializers.FileField(
        required=False,
        write_only=True,
        help_text="Fichier audio (multipart). Formats : ogg, mp3, wav, webm.",
    )
    audio_base64 = serializers.CharField(
        required=False,
        write_only=True,
        help_text="Audio encodé en base64 (mode JSON).",
    )
    format = serializers.ChoiceField(
        choices=SUPPORTED_FORMATS,
        required=False,
        help_text="Format de l'audio (ogg, mp3, wav, webm).",
    )

    def validate(self, attrs):
        audio_file = attrs.get("audio")
        audio_base64 = attrs.get("audio_base64")

        if not audio_file and not audio_base64:
            raise serializers.ValidationError(
                "Fournissez un fichier `audio` (multipart) ou `audio_base64` (JSON)."
            )
        if audio_file and audio_base64:
            raise serializers.ValidationError(
                "Fournissez l'audio d'une seule façon : `audio` ou `audio_base64`."
            )

        audio_format = attrs.get("format")

        if audio_file:
            if not audio_format:
                extension = audio_file.name.rsplit(".", 1)[-1].lower() if "." in audio_file.name else ""
                audio_format = _FORMAT_BY_EXTENSION.get(extension)
            if not audio_format:
                raise serializers.ValidationError(
                    {"format": "Format indéterminé : précisez `format` (ogg, mp3, wav, webm)."}
                )
            encoded = base64.b64encode(audio_file.read()).decode("ascii")
        else:
            audio_format = audio_format or "ogg"
            encoded = audio_base64.strip()
            try:
                base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError):
                raise serializers.ValidationError(
                    {"audio_base64": "Chaîne base64 invalide."}
                )

        return {"audio_base64": encoded, "format": audio_format}


class GbegbeResponseSerializer(serializers.Serializer):
    langue_detectee = serializers.CharField(help_text="Langue détectée (fon, yoruba ou français).")
    transcription_fr = serializers.CharField(help_text="Transcription fidèle en français.")
    type = serializers.CharField(help_text="plainte, suggestion ou felicitation.")
    service = serializers.CharField(help_text="urgences, consultation, pharmacie ou autre.")
    gravite = serializers.CharField(help_text="faible, moyen ou urgent.")
    resume = serializers.CharField(help_text="Résumé synthétique du signalement.")
