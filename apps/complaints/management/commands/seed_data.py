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
from apps.complaints.services import change_complaint_status, reject_complaint
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

DEMO_USERS = [
    {
        "username": "admin",
        "email": "admin@sante-ecoute.bj",
        "password": "admin123",
        "role": UserRole.ADMIN,
        "first_name": "Admin",
        "last_name": "Système",
    },
    {
        "username": "ministry.bj",
        "email": "ministry@sante-ecoute.bj",
        "password": "Ministry123!",
        "role": UserRole.MINISTRY_SUPERVISOR,
        "first_name": "Superviseur",
        "last_name": "Ministère",
    },
    {
        "username": "manager.cnhu",
        "email": "manager.cnhu@cnhu.bj",
        "password": "Manager123!",
        "role": UserRole.HOSPITAL_MANAGER,
        "first_name": "Responsable",
        "last_name": "CNHU",
        "facility_code": "CNHU-HKM",
    },
    {
        "username": "manager.suru",
        "email": "manager.suru@hz.bj",
        "password": "Manager123!",
        "role": UserRole.HOSPITAL_MANAGER,
        "first_name": "Responsable",
        "last_name": "Suru-Léré",
        "facility_code": "HZ-SURU",
    },
    {
        "username": "agent.a",
        "email": "agent.a@cnhu.bj",
        "password": "Agent123!",
        "role": UserRole.FACILITY_AGENT,
        "first_name": "Agent",
        "last_name": "A",
        "facility_code": "CNHU-HKM",
    },
    {
        "username": "agent.b",
        "email": "agent.b@cnhu.bj",
        "password": "Agent123!",
        "role": UserRole.FACILITY_AGENT,
        "first_name": "Agent",
        "last_name": "B",
        "facility_code": "CNHU-HKM",
    },
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
        "status_flow": [
            (ComplaintStatus.UNDER_REVIEW, "Prise en charge par le responsable"),
            (ComplaintStatus.IN_PROGRESS, "Équipe mobilisée"),
        ],
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
        "status_flow": [
            (ComplaintStatus.RESOLVED, "Formation du personnel effectuée"),
        ],
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
        "status_flow": [
            (ComplaintStatus.CLOSED, "Remerciements transmis à l'équipe"),
        ],
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
        "status_flow": [
            (ComplaintStatus.UNDER_REVIEW, "Enquête interne ouverte"),
        ],
    },
    {
        "title": "Rupture de stock d'antibiotiques",
        "description": "Antibiotiques indisponibles à la pharmacie depuis une semaine.",
        "complaint_type": ComplaintType.COMPLAINT,
        "severity": Severity.URGENT,
        "submission_type": SubmissionType.IDENTIFIED,
        "facility_code": "HDP-PARAKOU",
        "service_name": "Pharmacie",
        "category_name": "Rupture de médicaments",
    },
    {
        "title": "Demande de paiement non officiel",
        "description": "On m'a demandé 5000 FCFA pour accélérer la consultation.",
        "complaint_type": ComplaintType.COMPLAINT,
        "severity": Severity.HIGH,
        "submission_type": SubmissionType.IDENTIFIED,
        "facility_code": "CS-PORTO",
        "service_name": "Consultation",
        "category_name": "Corruption",
        "status_flow": [
            (ComplaintStatus.REJECTED, "Plainte non étayée — éléments insuffisants"),
        ],
        "reject": True,
    },
    {
        "title": "Améliorer la signalétique",
        "description": "Proposer des panneaux directionnels dans les couloirs.",
        "complaint_type": ComplaintType.SUGGESTION,
        "severity": Severity.LOW,
        "submission_type": SubmissionType.IDENTIFIED,
        "facility_code": "CNHU-HKM",
        "service_name": "Accueil",
        "category_name": "Suggestion",
        "status_flow": [
            (ComplaintStatus.WAITING_INFO, "Besoin de précisions sur les emplacements"),
        ],
    },
    {
        "title": "Locaux insalubres aux toilettes",
        "description": "Toilettes publiques très sales, absence de savon.",
        "complaint_type": ComplaintType.COMPLAINT,
        "severity": Severity.MEDIUM,
        "submission_type": SubmissionType.ANONYMOUS,
        "facility_code": "HZ-SURU",
        "service_name": "Hospitalisation",
        "category_name": "Hygiène",
    },
]


class Command(BaseCommand):
    help = "Seed demo users, complaint categories, and sample complaints (Benin)"

    def handle(self, *args, **options):
        categories_created = self._seed_categories()
        users_created = self._seed_users()
        complaints_created = self._seed_complaints()

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed terminé : {ComplaintCategory.objects.count()} catégories "
                f"({categories_created} créées), "
                f"{User.objects.count()} utilisateurs ({users_created} créés), "
                f"{Complaint.objects.count()} plaintes ({complaints_created} créées)."
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "Comptes démo : admin/admin123, ministry.bj/Ministry123!, "
                "manager.cnhu/Manager123!, agent.a/Agent123!"
            )
        )

    def _seed_categories(self) -> int:
        created = 0
        for name, description in DEFAULT_CATEGORIES:
            _, was_created = ComplaintCategory.objects.get_or_create(
                name=name,
                defaults={"description": description},
            )
            if was_created:
                created += 1
        return created

    def _seed_users(self) -> int:
        created = 0
        for spec in DEMO_USERS:
            user, was_created = User.objects.get_or_create(
                username=spec["username"],
                defaults={
                    "email": spec["email"],
                    "role": spec["role"],
                    "first_name": spec.get("first_name", ""),
                    "last_name": spec.get("last_name", ""),
                },
            )
            if was_created:
                user.set_password(spec["password"])
                user.save()
                created += 1

            facility_code = spec.get("facility_code")
            if facility_code:
                facility = Facility.objects.filter(code=facility_code).first()
                if facility:
                    UserFacilityAssignment.objects.update_or_create(
                        user=user,
                        defaults={"facility": facility},
                    )
        return created

    def _seed_complaints(self) -> int:
        created = 0
        manager_by_facility = {}

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

            if Complaint.objects.filter(title=sample["title"], facility=facility).exists():
                continue

            submitter = None
            reported_agent = None
            if sample.get("submitter_username"):
                submitter = User.objects.filter(username=sample["submitter_username"]).first()
            if sample.get("reported_agent_username"):
                reported_agent = User.objects.filter(
                    username=sample["reported_agent_username"]
                ).first()

            complaint = Complaint.objects.create(
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
            created += 1

            manager = manager_by_facility.get(facility.code)
            if not manager:
                assignment = UserFacilityAssignment.objects.filter(facility=facility).first()
                manager = assignment.user if assignment else None
                manager_by_facility[facility.code] = manager

            for new_status, reason in sample.get("status_flow", []):
                if sample.get("reject"):
                    reject_complaint(complaint, manager, reason)
                else:
                    change_complaint_status(complaint, new_status, manager, reason)

        return created
