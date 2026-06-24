"""
Transcodage audio robuste avant l'appel Mistral (Voxtral).

Les navigateurs et applications encodent les notes vocales dans des formats
variés (webm/opus, ogg, m4a…) que l'API peut refuser ou mal interpréter. On
normalise donc tout en **MP3 16 kHz mono** via ffmpeg avant l'envoi.

Le binaire ffmpeg provient de `imageio-ffmpeg` (embarqué, pas de dépendance
système) — avec repli sur un ffmpeg du PATH si disponible. En cas d'échec, on
renvoie None et l'appelant conserve l'audio d'origine (jamais bloquant).
"""
import logging
import subprocess

logger = logging.getLogger(__name__)

TARGET_FORMAT = "mp3"
_TIMEOUT = 60


def _ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 — repli sur ffmpeg système
        logger.warning("imageio-ffmpeg indisponible, tentative avec ffmpeg du PATH.")
        return "ffmpeg"


def transcode_to_mp3(audio_bytes: bytes) -> bytes | None:
    """
    Transcode un audio quelconque en MP3 16 kHz mono.
    Retourne les octets MP3, ou None si le transcodage échoue.
    """
    if not audio_bytes:
        return None

    cmd = [
        _ffmpeg_exe(),
        "-hide_banner",
        "-loglevel", "error",
        "-i", "pipe:0",
        "-ac", "1",
        "-ar", "16000",
        "-f", "mp3",
        "pipe:1",
    ]
    try:
        proc = subprocess.run(
            cmd,
            input=audio_bytes,
            capture_output=True,
            timeout=_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        logger.exception("ffmpeg introuvable ou échec d'exécution.")
        return None

    if proc.returncode != 0 or not proc.stdout:
        detail = proc.stderr.decode("utf-8", "replace")[:300]
        logger.error("Transcodage ffmpeg échoué (code %s): %s", proc.returncode, detail)
        return None

    return proc.stdout
