from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["Health"],
        summary="Vérifier que l'API est en ligne",
        responses={200: OpenApiResponse(description="API opérationnelle")},
    )
    def get(self, request):
        return Response({"status": "ok", "service": "sante-ecoute"})
