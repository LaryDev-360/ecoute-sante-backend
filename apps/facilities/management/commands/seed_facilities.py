from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.facilities.models import Facility, FacilityService, FacilityType, UserFacilityAssignment

DEFAULT_SERVICES = [
    "Accueil",
    "Consultation",
    "Laboratoire",
    "Pharmacie",
    "Maternité",
    "Urgences",
    "Caisse",
    "Hospitalisation",
]

FACILITIES = [
    {
        "name": "CNHU Hubert Koutoukou Maga",
        "code": "CNHU-HKM",
        "facility_type": FacilityType.HOSPITAL,
        "region": "Littoral",
        "city": "Cotonou",
        "address": "Avenue Clozel, Cotonou",
    },
    {
        "name": "Hôpital de Zone de Suru-Léré",
        "code": "HZ-SURU",
        "facility_type": FacilityType.HOSPITAL,
        "region": "Littoral",
        "city": "Cotonou",
        "address": "Quartier Suru-Léré, Cotonou",
    },
    {
        "name": "Centre de Santé de Porto-Novo",
        "code": "CS-PORTO",
        "facility_type": FacilityType.HEALTH_CENTER,
        "region": "Ouémé",
        "city": "Porto-Novo",
        "address": "Quartier Ouando, Porto-Novo",
    },
    {
        "name": "Hôpital Départemental de Parakou",
        "code": "HDP-PARAKOU",
        "facility_type": FacilityType.HOSPITAL,
        "region": "Borgou",
        "city": "Parakou",
        "address": "Avenue du Gouverneur, Parakou",
    },
]


class Command(BaseCommand):
    help = "Seed sample Benin facilities, services, and manager assignments"

    def handle(self, *args, **options):
        created_facilities = 0
        for data in FACILITIES:
            facility, created = Facility.objects.get_or_create(
                code=data["code"],
                defaults=data,
            )
            if created:
                created_facilities += 1
                for service_name in DEFAULT_SERVICES:
                    FacilityService.objects.get_or_create(
                        facility=facility,
                        name=service_name,
                    )

        manager = User.objects.filter(username="manager.test").first()
        cnhu = Facility.objects.filter(code="CNHU-HKM").first()
        if manager and cnhu:
            UserFacilityAssignment.objects.update_or_create(
                user=manager,
                defaults={"facility": cnhu},
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed terminé : {Facility.objects.count()} établissements "
                f"({created_facilities} créés), "
                f"{FacilityService.objects.count()} services."
            )
        )
