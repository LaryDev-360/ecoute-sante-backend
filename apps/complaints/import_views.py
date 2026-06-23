from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserRole
from apps.ai.services.ocr import OCRExtractionError, extract_complaint_from_scan
from apps.common.permissions import IsMinistryOrAdmin
from apps.common.schema import COMMON_ERRORS, ERROR_503, ERROR_504
from apps.complaints.import_serializers import (
    ComplaintCSVUploadSerializer,
    StaffComplaintImportResponseSerializer,
    StaffComplaintImportSerializer,
)
from apps.complaints.import_services import ComplaintImportError, import_complaints_csv
from apps.complaints.permissions import IsHospitalComplaintStaff
from apps.facilities.services import get_user_facility, user_can_access_facility


class ComplaintOCRExtractView(APIView):
    """Extraction indicative depuis un scan — révision humaine obligatoire."""

    permission_classes = [IsHospitalComplaintStaff]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=["Complaints"],
        summary="Extraire les champs d'un formulaire papier (OCR)",
        request=ComplaintCSVUploadSerializer,
        responses={200: OpenApiResponse(description="Champs extraits"), 400: COMMON_ERRORS[400], 503: ERROR_503},
    )
    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response(
                {"success": False, "error": {"detail": "Fichier requis (champ file)."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = extract_complaint_from_scan(upload)
        except OCRExtractionError as exc:
            return Response(
                {"success": False, "error": {"detail": exc.message, "code": exc.code}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(result)


class HospitalComplaintCSVImportView(APIView):
    permission_classes = [IsHospitalComplaintStaff]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=["Hospital"],
        summary="Importer des plaintes papier (CSV)",
        request=ComplaintCSVUploadSerializer,
        responses={200: OpenApiResponse(description="Résultat import"), 400: COMMON_ERRORS[400]},
    )
    def post(self, request):
        return _handle_csv_import(request)


class MinistryComplaintCSVImportView(APIView):
    permission_classes = [IsMinistryOrAdmin]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=["Ministry"],
        summary="Importer des plaintes papier (CSV national)",
        request=ComplaintCSVUploadSerializer,
        responses={200: OpenApiResponse(description="Résultat import"), 400: COMMON_ERRORS[400]},
    )
    def post(self, request):
        return _handle_csv_import(request)


def _handle_csv_import(request):
    upload = request.FILES.get("file")
    if not upload:
        return Response(
            {"success": False, "error": {"detail": "Fichier CSV requis (champ file)."}},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        content = upload.read().decode("utf-8-sig")
        result = import_complaints_csv(request.user, content)
    except UnicodeDecodeError:
        return Response(
            {"success": False, "error": {"detail": "Encodage UTF-8 requis."}},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except ComplaintImportError as exc:
        payload = {"detail": exc.message}
        if exc.row:
            payload["row"] = exc.row
        return Response({"success": False, "error": payload}, status=status.HTTP_400_BAD_REQUEST)

    return Response(result)


class HospitalComplaintImportCreateView(APIView):
    permission_classes = [IsHospitalComplaintStaff]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=["Hospital"],
        summary="Créer une plainte papier (après révision)",
        request=StaffComplaintImportSerializer,
        responses={201: StaffComplaintImportResponseSerializer, 400: COMMON_ERRORS[400]},
    )
    def post(self, request):
        return _handle_staff_import_create(request)


class MinistryComplaintImportCreateView(APIView):
    permission_classes = [IsMinistryOrAdmin]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=["Ministry"],
        summary="Créer une plainte papier (après révision)",
        request=StaffComplaintImportSerializer,
        responses={201: StaffComplaintImportResponseSerializer, 400: COMMON_ERRORS[400]},
    )
    def post(self, request):
        return _handle_staff_import_create(request)


def _handle_staff_import_create(request):
    serializer = StaffComplaintImportSerializer(
        data=request.data,
        context={"request": request},
    )
    serializer.is_valid(raise_exception=True)

    facility = serializer.validated_data["facility"]
    if request.user.role in (UserRole.HOSPITAL_MANAGER, UserRole.FACILITY_AGENT):
        own = get_user_facility(request.user)
        if own is None or own.pk != facility.pk:
            return Response(
                {"success": False, "error": {"detail": "Établissement hors périmètre."}},
                status=status.HTTP_403_FORBIDDEN,
            )
    elif not user_can_access_facility(request.user, facility):
        return Response(
            {"success": False, "error": {"detail": "Accès refusé à cet établissement."}},
            status=status.HTTP_403_FORBIDDEN,
        )

    complaint = serializer.save()
    return Response(
        StaffComplaintImportResponseSerializer(complaint).data,
        status=status.HTTP_201_CREATED,
    )
