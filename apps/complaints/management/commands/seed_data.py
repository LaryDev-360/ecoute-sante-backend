from datetime import date, timedelta

from django.core.management.base import BaseCommand

from apps.accounts.models import User, UserRole
from apps.complaints.models import (
    Complaint,
    ComplaintCategory,
    ComplaintStatus,
    ComplaintType,
    Severity,
    SubmissionType,
    SubmitterProfile,
)
from apps.facilities.models import Facility, FacilityService, UserFacilityAssignment

DEFAULT_CATEGORIES = [
    ("Mauvais accueil", "Problèmes liés à l'accueil des patients"),
    ("Temps d'attente", "Délais d'attente excessifs"),
    ("Corruption", "Demandes de paiement non officielles"),
    ("Rupture de médicaments", "Indisponibilité de médicaments"),
    ("Hygiène", "Problèmes d'hygiène et de propreté"),
    ("Facturation", "Erreurs ou surfacturation"),
    ("Refus de prise en charge", "Refus de soins ou d'orientation"),
    ("Orientation", "Mauvaise orientation du patient"),
    ("Suggestion", "Proposition d'amélioration"),
    ("Félicitation", "Message de satisfaction"),
    ("Autre", "Autres motifs"),
]

SAMPLE_COMPLAINTS = [
    {
        "title": "Attente excessive aux urgences",
        "description": "Plus de 4 heures d'attente sans information aux urgences.",
        "complaint_type": ComplaintType.COMPLAINT,
        "severity": Severity.HIGH,
        "submission_type": SubmissionType.IDENTIFIED,
        "facility_code": "CNHU-HKM",
        "service_name": "Urgences",
        "category_name": "Temps d'attente",
    },
    {
        "title": "Accueil déplorable",
        "description": "Personnel peu courtois à l'accueil.",
        "complaint_type": ComplaintType.COMPLAINT,
        "severity": Severity.MEDIUM,
        "submission_type": SubmissionType.CONFIDENTIAL,
        "facility_code": "HZ-SURU",
        "service_name": "Accueil",
        "category_name": "Mauvais accueil",
    },
    {
        "title": "Excellente prise en charge",
        "description": "Équipe très professionnelle au service de maternité.",
        "complaint_type": ComplaintType.APPRECIATION,
        "severity": Severity.LOW,
        "submission_type": SubmissionType.ANONYMOUS,
        "facility_code": "CNHU-HKM",
        "service_name": "Maternité",
        "category_name": "Félicitation",
    },
    {
        "title": "Comportement irrespectueux d'un collègue",
        "description": "Un agent a manqué de respect à un patient et à l'équipe.",
        "complaint_type": ComplaintType.COMPLAINT,
        "severity": Severity.HIGH,
        "submission_type": SubmissionType.CONFIDENTIAL,
        "submitter_profile": SubmitterProfile.FACILITY_AGENT,
        "facility_code": "CNHU-HKM",
        "service_name": "Accueil",
        "category_name": "Mauvais accueil",
        "submitter_username": "agent.a",
        "reported_agent_username": "agent.b",
    },
]


class Command(BaseCommand):
    help = "Seed complaint categories and sample complaints (Benin demo data)"

    def handle(self, *args, **options):
        categories_created = 0
        for name, description in DEFAULT_CATEGORIES:
            _, created = ComplaintCategory.objects.get_or_create(
                name=name,
                defaults={"description": description},
            )
            if created:
                categories_created += 1

        complaints_created = 0
        cnhu = Facility.objects.filter(code="CNHU-HKM").first()
        if cnhu:
            for username in ("agent.a", "agent.b"):
                agent, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "email": f"{username}@cnhu.bj",
                        "role": UserRole.FACILITY_AGENT,
                    },
                )
                if created:
                    agent.set_password("Agent123!")
                    agent.save()
                UserFacilityAssignment.objects.update_or_create(
                    user=agent,
                    defaults={"facility": cnhu},
                )

        for sample in SAMPLE_COMPLAINTS:
            facility = Facility.objects.filter(code=sample["facility_code"]).first()
            if not facility:
                continue

            service = FacilityService.objects.filter(
                facility=facility,
                name=sample["service_name"],
            ).first()
            category = ComplaintCategory.objects.filter(name=sample["category_name"]).first()
            if not service or not category:
                continue

            exists = Complaint.objects.filter(
                title=sample["title"],
                facility=facility,
            ).exists()
            if exists:
                continue

            submitter = None
            reported_agent = None
            if sample.get("submitter_username"):
                submitter = User.objects.filter(username=sample["submitter_username"]).first()
            if sample.get("reported_agent_username"):
                reported_agent = User.objects.filter(
                    username=sample["reported_agent_username"]
                ).first()

            Complaint.objects.create(
                submitter_profile=sample.get("submitter_profile", SubmitterProfile.CITIZEN),
                submission_type=sample["submission_type"],
                complaint_type=sample["complaint_type"],
                facility=facility,
                service=service,
                category=category,
                submitted_by=submitter,
                reported_agent=reported_agent,
                title=sample["title"],
                description=sample["description"],
                incident_date=date.today() - timedelta(days=3),
                severity=sample["severity"],
                current_status=ComplaintStatus.RECEIVED,
                phone="+22997000001",
                email="citoyen@example.bj",
            )
            complaints_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed terminé : {ComplaintCategory.objects.count()} catégories "
                f"({categories_created} créées), "
                f"{Complaint.objects.count()} plaintes ({complaints_created} créées)."
            )
        )
