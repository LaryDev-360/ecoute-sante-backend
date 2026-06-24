"""
Synthèse vocale (Text-To-Speech) en français pour les prompts WhatsApp.

Utilise gTTS (gratuit, sans clé). Les fichiers générés sont mis en cache sur
disque (par empreinte du texte) pour éviter de régénérer les menus récurrents.
La génération est « best effort » : en cas d'échec (réseau, lib absente), on
renvoie None et la conversation continue en texte seul.
"""
import hashlib
import logging
import re
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(settings.MEDIA_ROOT) / "tts"

# Caractères décoratifs (emojis, symboles) à retirer avant lecture vocale.
_DECOR_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF←-⇿⬀-⯿]",
    flags=re.UNICODE,
)


def nettoyer_pour_voix(texte: str) -> str:
    """Retire emojis et balises pour une lecture vocale naturelle."""
    texte = _DECOR_RE.sub("", texte)
    texte = texte.replace("*", "").replace("_", "")
    texte = re.sub(r"[ \t]+", " ", texte)
    texte = re.sub(r"\n{2,}", "\n", texte)
    return texte.strip()


def _url_publique(nom_fichier: str) -> str | None:
    base = getattr(settings, "WHATSAPP_PUBLIC_BASE_URL", "")
    if not base:
        return None
    media = settings.MEDIA_URL.strip("/")
    return f"{base.rstrip('/')}/{media}/tts/{nom_fichier}"


def synthetiser_fr(texte: str) -> str | None:
    """
    Génère (ou récupère en cache) l'audio MP3 français d'un texte et renvoie son
    URL publique (servie via le tunnel), prête pour Green API `sendFileByUrl`.
    Renvoie None si la voix est désactivée, l'URL publique non configurée, ou en
    cas d'échec — la conversation continue alors en texte seul.
    """
    if not getattr(settings, "WHATSAPP_VOICE_PROMPTS", False):
        return None

    contenu = nettoyer_pour_voix(texte)
    if not contenu:
        return None

    empreinte = hashlib.sha1(contenu.encode("utf-8")).hexdigest()
    nom_fichier = f"{empreinte}.mp3"
    chemin = _CACHE_DIR / nom_fichier

    if not chemin.exists():
        try:
            from gtts import gTTS

            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            gTTS(text=contenu, lang="fr", slow=False).save(str(chemin))
        except Exception:  # noqa: BLE001 — la voix est un bonus, jamais bloquante
            logger.exception("Échec de la synthèse vocale (TTS)")
            return None

    return _url_publique(nom_fichier)
