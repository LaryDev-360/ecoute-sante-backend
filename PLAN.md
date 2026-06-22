# Plan d'implémentation — Santé Écoute Backend

Ce document découpe le développement en **phases indépendantes et testables**. Chaque phase se termine par un livrable vérifiable (migrations, endpoints, Swagger à jour).

**Documentation API :** [drf-spectacular](https://drf-spectacular.readthedocs.io/) (OpenAPI 3) — schéma à `/api/schema/`, UI Swagger à `/api/docs/`.

**Base URL API :** `/api/v1/`

---

## Principes transverses (toutes les phases)

- Aucune suppression physique — soft delete via `active=False` ou `is_archived=True`
- Toute transition de statut crée une entrée `ComplaintStatusHistory`
- Un `HOSPITAL_MANAGER` ne voit jamais les données d'un autre établissement
- Les plaintes rejetées restent visibles, consultables et comptabilisées
- Chaque endpoint livré est documenté dans Swagger (tags, request/response, codes d'erreur)

---

## Phase 0 — Fondations projet

**Objectif :** Projet Django bootstrappé, prêt à recevoir les apps métier.

### Tâches

- [ ] Initialiser le projet Django (`config/`, `manage.py`)
- [ ] Structurer les settings (`base.py`, `dev.py`, `prod.py`)
- [ ] Configurer PostgreSQL (variables d'environnement)
- [ ] Créer `requirements/` (base, dev, prod)
- [ ] Installer et configurer DRF, SimpleJWT, django-filter, drf-spectacular, Pillow, psycopg
- [ ] Configurer `MEDIA_ROOT` / `STATIC_ROOT`
- [ ] Exposer Swagger :
  - `GET /api/schema/` — schéma OpenAPI
  - `GET /api/docs/` — Swagger UI
- [ ] Créer l'app `common` (mixins, exceptions, pagination, permissions de base)
- [ ] `.env.example` + README minimal (lancement local)

### Livrable

Projet qui démarre, se connecte à PostgreSQL, et affiche Swagger (vide ou quasi vide).

### Critères de validation

- `python manage.py runserver` OK
- `python manage.py migrate` OK
- `/api/docs/` accessible en dev

---

## Phase 1 — Comptes & authentification

**Objectif :** Modèle utilisateur, rôles, JWT.

### Modèles

- `User` (extends `AbstractUser`) : `phone`, `role`, `is_active`
- Rôles : `ADMIN`, `MINISTRY_SUPERVISOR`, `HOSPITAL_MANAGER`

### Tâches

- [ ] App `accounts` + modèle `User` + migrations
- [ ] `AUTH_USER_MODEL = "accounts.User"`
- [ ] Endpoints JWT :
  - `POST /api/v1/auth/login/`
  - `POST /api/v1/auth/refresh/`
- [ ] Endpoint profil (optionnel mais utile) : `GET /api/v1/auth/me/`
- [ ] Permissions DRF par rôle (classes réutilisables dans `common`)
- [ ] Admin Django pour `User`
- [ ] Documenter les endpoints auth dans Swagger (tag `Auth`)

### Livrable

Connexion JWT fonctionnelle, utilisateurs créables via admin.

### Critères de validation

- Login retourne `access` + `refresh`
- Refresh renouvelle le token
- Swagger documente login/refresh avec exemples de payload

---

## Phase 2 — Établissements sanitaires

**Objectif :** Structures, services, affectation responsable ↔ hôpital.

### Modèles

- `Facility` : nom, code, type, région, ville, adresse, `active`
- `FacilityService` : service rattaché à un établissement
- `UserFacilityAssignment` : lien `User` ↔ `Facility`

### Tâches

- [ ] App `facilities` + modèles + migrations
- [ ] CRUD admin (Facility, FacilityService, UserFacilityAssignment)
- [ ] Serializers + ViewSets (accès restreint selon rôle) :
  - `GET /api/v1/facilities/` — liste (filtrable)
  - `GET /api/v1/facilities/{id}/` — détail + services
- [ ] Filtres : région, ville, `active`, type
- [ ] Helper : `get_user_facility(user)` pour le scope hôpital
- [ ] Swagger tag `Facilities`

### Livrable

Établissements et services gérables ; un responsable est rattaché à son hôpital.

### Critères de validation

- Un `HOSPITAL_MANAGER` ne voit que son établissement
- Un `MINISTRY_SUPERVISOR` / `ADMIN` voit tous les établissements

---

## Phase 3 — Plaintes — modèles & référence

**Objectif :** Cœur métier en base, sans encore toute la surface API.

### Modèles

- `ComplaintCategory` (seed des catégories par défaut)
- `Complaint` : tous les champs du blueprint
- `ComplaintAttachment`
- `ComplaintComment`
- `ComplaintStatusHistory`
- `ComplaintAssignment`

### Enums / choix

| Champ | Valeurs |
|-------|---------|
| `submission_type` | ANONYMOUS, CONFIDENTIAL, IDENTIFIED |
| `complaint_type` | COMPLAINT, SUGGESTION, APPRECIATION |
| `severity` | LOW, MEDIUM, HIGH, URGENT |
| `current_status` | RECEIVED, UNDER_REVIEW, IN_PROGRESS, WAITING_INFO, RESOLVED, REJECTED, CLOSED |

### Tâches

- [ ] App `complaints` + modèles + migrations
- [ ] `generate_reference()` → format `SE-{année}-{6 chiffres}` (auto au `save`)
- [ ] Signal ou service métier : création automatique du premier `ComplaintStatusHistory` à la création
- [ ] Admin Django pour tous les modèles complaints
- [ ] Management command `seed_data` (catégories + données de démo minimales)
- [ ] Tests unitaires sur `generate_reference()` et unicité

### Livrable

Schéma plaintes complet en base, catégories seedées, référence auto-générée.

### Critères de validation

- Références uniques et séquentielles par année
- Première entrée d'historique créée à l'ouverture d'une plainte

---

## Phase 4 — API publique (soumission & suivi)

**Objectif :** Permettre au citoyen de déposer et suivre un dossier sans compte.

### Endpoints

| Méthode | Route | Description |
|---------|-------|-------------|
| `POST` | `/api/v1/complaints/` | Soumettre un signalement (+ pièces jointes optionnelles) |
| `GET` | `/api/v1/complaints/track/{reference}/` | Suivre par référence (statut public limité) |

### Tâches

- [ ] Serializer création plainte (validation facility/service/category)
- [ ] Upload fichiers (`ComplaintAttachment`) — types MIME / taille max
- [ ] Statut initial : `RECEIVED`
- [ ] Endpoint tracking : retourne statut, dates, pas les commentaires internes
- [ ] Rate limiting basique sur soumission publique (optionnel phase 4, recommandé)
- [ ] Swagger tag `Public` — exemples JSON complets

### Livrable

Soumission et suivi fonctionnels sans authentification.

### Critères de validation

- `POST` crée plainte + référence + historique initial
- `GET track/SE-2026-000001/` retourne le statut courant
- Swagger montre les deux endpoints avec schémas request/response

---

## Phase 5 — API hôpital (gestion des plaintes)

**Objectif :** Le responsable d'établissement traite les plaintes de son hôpital.

### Endpoints

| Méthode | Route | Description |
|---------|-------|-------------|
| `GET` | `/api/v1/hospital/dashboard/` | KPIs établissement |
| `GET` | `/api/v1/hospital/complaints/` | Liste (filtrée par établissement) |
| `GET` | `/api/v1/hospital/complaints/{id}/` | Détail |
| `PATCH` | `/api/v1/hospital/complaints/{id}/status/` | Changer le statut |
| `PATCH` | `/api/v1/hospital/complaints/{id}/reject/` | Rejeter (avec motif) |
| `POST` | `/api/v1/hospital/complaints/{id}/comments/` | Commentaire interne |

### Filtres liste

`status`, `category`, `service`, `severity`, `date_from`, `date_to`

### Tâches

- [ ] Permission : scope strict sur `UserFacilityAssignment`
- [ ] Service `change_complaint_status(complaint, new_status, user, reason)` — écrit historique
- [ ] Rejet : statut `REJECTED` + motif obligatoire dans l'historique
- [ ] Dashboard hôpital : total, reçues, en cours, résolues, rejetées, délai moyen, top catégories, top services
- [ ] Serializers détail (historique, commentaires, pièces jointes)
- [ ] Swagger tag `Hospital`

### Livrable

Workflow complet côté établissement.

### Critères de validation

- Impossible d'accéder à une plainte d'un autre hôpital (403)
- Chaque `PATCH status` crée une ligne `ComplaintStatusHistory`
- Plainte rejetée toujours listable et comptée dans le dashboard

---

## Phase 6 — API ministère (vue nationale & analytics)

**Objectif :** Supervision nationale, statistiques agrégées.

### Endpoints

| Méthode | Route | Description |
|---------|-------|-------------|
| `GET` | `/api/v1/ministry/dashboard/` | KPIs nationaux |
| `GET` | `/api/v1/ministry/analytics/` | Agrégats détaillés |
| `GET` | `/api/v1/ministry/complaints/` | Liste globale (filtres) |

### Métriques

**Dashboard hôpital (rappel phase 5) :** totaux par statut, délai moyen, top catégories/services.

**Dashboard ministère :** plaintes par région, par hôpital, taux résolution, taux rejet, délai moyen national, évolution mensuelle.

### Tâches

- [ ] App `analytics` (services de requêtes, pas de modèles)
- [ ] Requêtes ORM : `annotate`, `aggregate`, `Count`, `Avg`, `Case`, `When`
- [ ] Filtres globaux : région, établissement, période, statut
- [ ] Export CSV : `GET /api/v1/ministry/complaints/export/` (ou query param `?format=csv`)
- [ ] Permission `MINISTRY_SUPERVISOR` + `ADMIN` uniquement
- [ ] Swagger tag `Ministry`

### Livrable

Vue nationale opérationnelle avec export.

### Critères de validation

- Agrégats cohérents avec les données seed
- Export CSV téléchargeable
- `MINISTRY_SUPERVISOR` ne peut pas supprimer de plainte

---

## Phase 7 — Qualité, documentation & données de démo

**Objectif :** Projet présentable (hackathon / recette).

### Tâches

- [ ] Compléter les descriptions Swagger (`@extend_schema`, exemples, codes 400/403/404)
- [ ] Grouper les tags OpenAPI : Auth, Public, Hospital, Ministry, Facilities
- [ ] `seed_data` enrichi : établissements, utilisateurs par rôle, plaintes variées (statuts, catégories)
- [ ] Tests d'intégration sur les parcours critiques :
  - soumission → tracking
  - changement statut → historique
  - isolation hôpital
- [ ] Configuration CORS pour le frontend
- [ ] Variables prod documentées (`SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS`)
- [ ] Script ou Makefile : `migrate`, `seed`, `run`

### Livrable

Backend documenté, seedé, testé — prêt pour démo.

### Critères de validation

- `/api/docs/` couvre 100 % des endpoints livrés
- `seed_data` permet une démo bout-en-bout en 5 minutes

---

## Phase 8 (bonus) — Classification IA légère

**Objectif :** Assistance à la qualification, sans remplacer le responsable.

### Endpoint

```
POST /api/v1/ai/classify/
```

**Request :**
```json
{ "description": "..." }
```

**Response :**
```json
{
  "category": "Temps d'attente",
  "priority": "HIGH"
}
```

### Tâches

- [ ] Service de classification (règles heuristiques ou appel modèle léger)
- [ ] Résultat indicatif uniquement — jamais appliqué automatiquement à la plainte
- [ ] Swagger tag `AI`
- [ ] Rate limit + timeout

### Livrable

Endpoint d'assistance optionnel pour la soumission côté frontend.

---

## Ordre recommandé & dépendances

```text
Phase 0 (fondations)
    └── Phase 1 (accounts/auth)
            └── Phase 2 (facilities)
                    └── Phase 3 (complaints models)
                            ├── Phase 4 (API publique)
                            └── Phase 5 (API hôpital)
                                    └── Phase 6 (API ministère)
                                            └── Phase 7 (qualité & seed)
                                                    └── Phase 8 (bonus IA)
```

| Phase | Estimation | Bloque |
|-------|------------|--------|
| 0 | ½ journée | tout |
| 1 | ½ journée | 2, 5, 6 |
| 2 | ½ journée | 3, 4, 5 |
| 3 | 1 journée | 4, 5, 6 |
| 4 | ½ journée | 7 |
| 5 | 1 journée | 6, 7 |
| 6 | 1 journée | 7 |
| 7 | ½ journée | — |
| 8 | ½ journée | — |

**Total cœur (phases 0–7) : ~5–6 jours** — aligné avec le blueprint 3 jours en mode intensif hackathon.

---

## Convention Swagger (drf-spectacular)

À appliquer dès la Phase 0 :

```python
# config/settings/base.py
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    ...
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Santé Écoute API",
    "DESCRIPTION": "API de gestion des signalements et plaintes sanitaires",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "TAGS": [
        {"name": "Auth"},
        {"name": "Public"},
        {"name": "Facilities"},
        {"name": "Hospital"},
        {"name": "Ministry"},
        {"name": "AI"},
    ],
}
```

Sur chaque vue :

```python
from drf_spectacular.utils import extend_schema, OpenApiExample

@extend_schema(
    tags=["Hospital"],
    summary="Changer le statut d'une plainte",
    request=ComplaintStatusSerializer,
    responses={200: ComplaintDetailSerializer},
)
def patch(self, request, pk):
    ...
```

---

## Checklist finale avant livraison

- [ ] Tous les endpoints du blueprint sont implémentés
- [ ] Swagger à jour et testé via `/api/docs/`
- [ ] Règles métier 1–4 respectées
- [ ] `seed_data` exécutable en une commande
- [ ] Aucun secret dans le dépôt
- [ ] README : installation, migrations, seed, accès Swagger
