# Blueprint Backend Django
## Projet : Santé Écoute
### Stack
- Django 5.x
- Django REST Framework
- PostgreSQL
- SimpleJWT
- django-filter
- drf-spectacular
- Pillow (si pièces jointes)
- psycopg

---

# Architecture du projet

```text
backend/
│
├── manage.py
│
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── dev.py
│   │   └── prod.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── apps/
│   │
│   ├── accounts/
│   ├── facilities/
│   ├── complaints/
│   ├── analytics/
│   └── common/
│
├── media/
├── static/
├── requirements/
└── docs/
```

---

# App : accounts

## Responsabilité

Gestion :

- utilisateurs
- authentification
- rôles
- permissions

---

## Modèle User

```python
class User(AbstractUser):
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=30)
    is_active = models.BooleanField(default=True)
```

---

## Rôles

```python
ADMIN

MINISTRY_SUPERVISOR

HOSPITAL_MANAGER
```

---

# App : facilities

## Responsabilité

Gestion des structures sanitaires.

---

## Facility

```python
class Facility(models.Model):
    name = models.CharField(max_length=255)

    code = models.CharField(max_length=50, unique=True)

    facility_type = models.CharField(max_length=50)

    region = models.CharField(max_length=100)

    city = models.CharField(max_length=100)

    address = models.TextField()

    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
```

---

## FacilityService

```python
class FacilityService(models.Model):

    facility = models.ForeignKey(
        Facility,
        on_delete=models.CASCADE
    )

    name = models.CharField(max_length=150)
```

---

### Exemples

- Accueil
- Consultation
- Laboratoire
- Pharmacie
- Maternité
- Urgences
- Caisse
- Hospitalisation

---

## UserFacilityAssignment

Permet d'associer un responsable à son hôpital.

```python
class UserFacilityAssignment(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    facility = models.ForeignKey(
        Facility,
        on_delete=models.CASCADE
    )
```

---

# App : complaints

## Responsabilité

Cœur métier.

---

# ComplaintCategory

```python
class ComplaintCategory(models.Model):

    name = models.CharField(max_length=255)

    description = models.TextField(blank=True)
```

---

### Catégories par défaut

- Mauvais accueil
- Temps d'attente
- Corruption
- Rupture de médicaments
- Hygiène
- Facturation
- Refus de prise en charge
- Orientation
- Suggestion
- Félicitation
- Autre

---

# Complaint

## Modèle principal

```python
class Complaint(models.Model):

    reference = models.CharField(
        max_length=30,
        unique=True
    )

    submission_type = models.CharField(
        max_length=20
    )

    complaint_type = models.CharField(
        max_length=20
    )

    facility = models.ForeignKey(
        Facility,
        on_delete=models.PROTECT
    )

    service = models.ForeignKey(
        FacilityService,
        on_delete=models.PROTECT
    )

    category = models.ForeignKey(
        ComplaintCategory,
        on_delete=models.PROTECT
    )

    title = models.CharField(
        max_length=255
    )

    description = models.TextField()

    incident_date = models.DateField(
        null=True,
        blank=True
    )

    severity = models.CharField(
        max_length=20
    )

    current_status = models.CharField(
        max_length=30
    )

    phone = models.CharField(
        max_length=20,
        blank=True
    )

    email = models.EmailField(
        blank=True
    )

    preferred_contact_method = models.CharField(
        max_length=30,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )
```

---

# Valeurs métier

## submission_type

```python
ANONYMOUS

CONFIDENTIAL

IDENTIFIED
```

---

## complaint_type

```python
COMPLAINT

SUGGESTION

APPRECIATION
```

---

## severity

```python
LOW

MEDIUM

HIGH

URGENT
```

---

## current_status

```python
RECEIVED

UNDER_REVIEW

IN_PROGRESS

WAITING_INFO

RESOLVED

REJECTED

CLOSED
```

---

# ComplaintAttachment

```python
class ComplaintAttachment(models.Model):

    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE
    )

    file = models.FileField(
        upload_to="complaints/"
    )
```

---

# ComplaintComment

Commentaires internes.

```python
class ComplaintComment(models.Model):

    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE
    )

    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    comment = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )
```

---

# ComplaintStatusHistory

TRÈS IMPORTANT

Toutes les transitions passent ici.

```python
class ComplaintStatusHistory(models.Model):

    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE
    )

    old_status = models.CharField(
        max_length=30
    )

    new_status = models.CharField(
        max_length=30
    )

    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    reason = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )
```

---

# ComplaintAssignment

```python
class ComplaintAssignment(models.Model):

    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE
    )

    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    assigned_at = models.DateTimeField(
        auto_now_add=True
    )
```

---

# Génération de référence

Format :

```text
SE-2026-000001
SE-2026-000002
SE-2026-000003
```

Fonction :

```python
generate_reference()
```

Appelée automatiquement lors du save.

---

# App : analytics

## Responsabilité

Statistiques.

Aucun modèle nécessaire au départ.

Utiliser :

```python
annotate()

aggregate()

Count()

Avg()

Case()

When()
```

---

# Dashboards à produire

## Hôpital

- nombre total
- reçues
- en cours
- résolues
- rejetées
- délai moyen traitement
- top catégories
- top services

---

## Ministère

- plaintes par région
- plaintes par hôpital
- taux de résolution
- taux de rejet
- délai moyen national
- évolution mensuelle

---

# Permissions

## ADMIN

Peut tout faire.

---

## MINISTRY_SUPERVISOR

Peut :

- voir toutes les plaintes
- voir tous les dashboards
- exporter

Ne peut pas :

- supprimer

---

## HOSPITAL_MANAGER

Peut :

- voir uniquement son établissement
- modifier les statuts
- commenter
- rejeter
- clôturer

Ne peut pas :

- voir les autres hôpitaux

---

# API REST

Base URL

```text
/api/v1/
```

---

# Auth

## Login

```http
POST /auth/login/
```

Retour :

```json
{
  "access": "...",
  "refresh": "..."
}
```

---

## Refresh

```http
POST /auth/refresh/
```

---

# Public

## Soumettre un signalement

```http
POST /complaints/
```

---

## Suivre un dossier

```http
GET /complaints/track/{reference}/
```

Exemple :

```http
GET /complaints/track/SE-2026-000123/
```

---

# Hôpital

## Dashboard

```http
GET /hospital/dashboard/
```

---

## Liste des plaintes

```http
GET /hospital/complaints/
```

Filtres :

```text
status

category

service

severity

date_from

date_to
```

---

## Détail

```http
GET /hospital/complaints/{id}/
```

---

## Changer statut

```http
PATCH /hospital/complaints/{id}/status/
```

Payload :

```json
{
  "status": "IN_PROGRESS"
}
```

---

## Rejeter

```http
PATCH /hospital/complaints/{id}/reject/
```

Payload :

```json
{
  "reason": "Plainte hors périmètre"
}
```

---

## Ajouter commentaire

```http
POST /hospital/complaints/{id}/comments/
```

---

# Ministère

## Dashboard global

```http
GET /ministry/dashboard/
```

---

## Analytics

```http
GET /ministry/analytics/
```

---

## Liste globale

```http
GET /ministry/complaints/
```

---

# Règles métier critiques

## Règle 1

Une plainte rejetée :

- reste visible
- reste consultable
- reste comptabilisée

---

## Règle 2

Toute modification de statut :

- crée un historique

obligatoirement.

---

## Règle 3

Aucune suppression physique.

Toujours :

```python
is_archived = True
```

ou

```python
active = False
```

---

## Règle 4

Un responsable hôpital ne voit jamais :

- les plaintes d'un autre hôpital
- les dashboards d'un autre hôpital

---

# Ordre de développement (3 jours)

## Jour 1

### Backend Core

- Accounts
- Auth JWT
- Facilities
- Complaint
- PostgreSQL
- Admin Django

---

## Jour 2

### APIs

- Soumission plainte
- Tracking
- Dashboard hôpital
- Statuts
- Historique
- Commentaires

---

## Jour 3

### Analytics

- Dashboard ministère
- Filtres
- Exports CSV
- Documentation Swagger
- Seed data

---

# Bonus Hackathon

## IA légère

Endpoint :

```http
POST /ai/classify/
```

Entrée :

```json
{
  "description": "..."
}
```

Retour :

```json
{
  "category": "Temps d'attente",
  "priority": "HIGH"
}
```

L'IA ne remplace jamais le responsable.

Elle assiste uniquement la qualification.
