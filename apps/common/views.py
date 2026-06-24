from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.db_health import get_database_health


class HealthCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["Health"],
        summary="Vérifier que l'API est en ligne",
        responses={
            200: OpenApiResponse(description="API et base de données prêtes"),
            503: OpenApiResponse(description="API en ligne mais base non migrée ou inaccessible"),
        },
    )
    def get(self, request):
        payload = {"status": "ok", "service": "sante-ecoute"}
        try:
            db_health = get_database_health()
            payload.update(db_health)
            if not db_health["ready"]:
                payload["status"] = "degraded"
                return Response(payload, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as exc:
            payload["status"] = "error"
            payload["detail"] = str(exc)
            return Response(payload, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(payload)
