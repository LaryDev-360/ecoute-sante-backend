from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import UserRole
from apps.audit.models import AuditAction, AuditLog
from apps.common.tests.base import BaseAPITestCase
from apps.complaints.models import Complaint, ComplaintCategory, ComplaintSource, ComplaintStatus
from apps.facilities.models import FacilityService


class ComplaintImportTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.manager = self.create_user(username="manager.imp", role=UserRole.HOSPITAL_MANAGER)
        self.ministry = self.create_user(username="ministry.imp", role=UserRole.MINISTRY_SUPERVISOR)
        self.facility = self.create_facility(code="IMP-FAC", name="HZ Import")
        self.service = FacilityService.objects.create(facility=self.facility, name="Urgences")
        self.category = ComplaintCategory.objects.create(name="Accueil import")
        self.assign_facility(self.manager, self.facility)

    def _csv_row(self, **overrides):
        base = {
            "facility_code": self.facility.code,
            "service_name": "Urgences",
            "category_name": "Accueil import",
            "complaint_type": "COMPLAINT",
            "submission_type": "ANONYMOUS",
            "title": "Plainte papier test",
            "description": "Description importée depuis le registre papier.",
            "severity": "MEDIUM",
            "registered_on_paper_at": "2026-01-15",
        }
        base.update(overrides)
        header = ",".join(base.keys())
        values = ",".join(f'"{v}"' for v in base.values())
        return f"{header}\n{values}\n"

    def test_hospital_csv_import_creates_complaint(self):
        self.auth_as(self.manager)
        upload = SimpleUploadedFile(
            "plaintes.csv",
            self._csv_row().encode("utf-8"),
            content_type="text/csv",
        )
        response = self.client.post(
            "/api/v1/hospital/complaints/import/csv/",
            {"file": upload},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["created"], 1)
        complaint = Complaint.objects.get(title="Plainte papier test")
        self.assertEqual(complaint.source, ComplaintSource.PAPER)
        self.assertEqual(complaint.facility_id, self.facility.id)
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditAction.COMPLAINT_IMPORTED,
                resource_id=str(complaint.pk),
            ).exists()
        )

    def test_hospital_csv_import_three_rows(self):
        self.auth_as(self.manager)
        csv_content = (
            "facility_code,service_name,category_name,complaint_type,submission_type,"
            "title,description,severity\n"
        )
        for i in range(3):
            csv_content += (
                f"{self.facility.code},Urgences,Accueil import,COMPLAINT,ANONYMOUS,"
                f"Plainte {i},Description longue numéro {i} pour test.,MEDIUM\n"
            )
        upload = SimpleUploadedFile(
            "batch.csv",
            csv_content.encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(
            "/api/v1/hospital/complaints/import/csv/",
            {"file": upload},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["created"], 3)
        self.assertEqual(
            AuditLog.objects.filter(action=AuditAction.COMPLAINT_IMPORTED).count(),
            3,
        )

    def test_staff_manual_import_with_ocr_flag(self):
        self.auth_as(self.manager)
        response = self.client.post(
            "/api/v1/hospital/complaints/import/",
            {
                "submitter_profile": "CITIZEN",
                "submission_type": "ANONYMOUS",
                "complaint_type": "COMPLAINT",
                "facility": self.facility.id,
                "service": self.service.id,
                "category": self.category.id,
                "title": "OCR revisée",
                "description": "Contenu validé après extraction OCR du formulaire.",
                "severity": "HIGH",
                "registered_on_paper_at": "2026-02-01",
                "ocr_reviewed": True,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        complaint = Complaint.objects.get(reference=response.json()["reference"])
        self.assertEqual(complaint.source, ComplaintSource.PAPER)
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditAction.COMPLAINT_OCR_REVIEWED,
                resource_id=str(complaint.pk),
            ).exists()
        )

    def test_ministry_csv_import(self):
        self.auth_as(self.ministry)
        csv_content = (
            "facility_code,service_name,category_name,title,description,severity\n"
            f'{self.facility.code},Urgences,Accueil import,'
            '"Plainte nationale","Description nationale importée.",LOW\n'
        )
        upload = SimpleUploadedFile("m.csv", csv_content.encode("utf-8"), content_type="text/csv")
        response = self.client.post(
            "/api/v1/ministry/complaints/import/csv/",
            {"file": upload},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["created"], 1)

    def test_csv_import_invalid_row_returns_error(self):
        self.auth_as(self.manager)
        csv_content = (
            "facility_code,service_name,category_name,title,description,severity\n"
            f'{self.facility.code},Inconnu,Accueil import,Titre,Description valide.,MEDIUM\n'
        )
        upload = SimpleUploadedFile("bad.csv", csv_content.encode("utf-8"), content_type="text/csv")
        response = self.client.post(
            "/api/v1/hospital/complaints/import/csv/",
            {"file": upload},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    def test_imported_complaint_has_initial_status(self):
        self.auth_as(self.manager)
        upload = SimpleUploadedFile(
            "one.csv",
            self._csv_row().encode("utf-8"),
            content_type="text/csv",
        )
        self.client.post(
            "/api/v1/hospital/complaints/import/csv/",
            {"file": upload},
            format="multipart",
        )
        complaint = Complaint.objects.get(title="Plainte papier test")
        self.assertEqual(complaint.current_status, ComplaintStatus.RECEIVED)
        self.assertEqual(complaint.status_history.count(), 1)
