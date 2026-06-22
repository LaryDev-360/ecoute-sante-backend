"""Réponses OpenAPI réutilisables pour drf-spectacular."""

from drf_spectacular.utils import OpenApiResponse

ERROR_400 = OpenApiResponse(
    description="Requête invalide (validation ou règle métier).",
)
ERROR_401 = OpenApiResponse(
    description="Authentification requise ou token invalide.",
)
ERROR_403 = OpenApiResponse(
    description="Accès refusé (rôle ou périmètre insuffisant).",
)
ERROR_404 = OpenApiResponse(
    description="Ressource introuvable.",
)
ERROR_503 = OpenApiResponse(
    description="Service temporairement indisponible.",
)
ERROR_504 = OpenApiResponse(
    description="Délai dépassé lors de l'appel au service externe.",
)

COMMON_ERRORS = {
    400: ERROR_400,
    403: ERROR_403,
    404: ERROR_404,
}

AUTH_ERRORS = {
    400: ERROR_400,
    401: ERROR_401,
}
