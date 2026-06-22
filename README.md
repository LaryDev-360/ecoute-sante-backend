# Santé Écoute — Backend API

API Django REST pour la gestion des signalements et plaintes dans les établissements sanitaires.

## Prérequis

- Python 3.10+
- Docker & Docker Compose

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements/dev.txt
cp .env.example .env
```

## Base de données (Docker)

Démarrer PostgreSQL :

```bash
docker compose up -d db
```

La base `sante_ecoute` est créée automatiquement au premier démarrage du conteneur (port hôte **5433**).

Puis appliquer les migrations :

```bash
python manage.py migrate
```

Arrêter la base :

```bash
docker compose down
```

Conserver les données entre les arrêts ; pour tout réinitialiser : `docker compose down -v`.

## Lancement

```bash
python manage.py runserver
```

- **Swagger UI :** http://127.0.0.1:8000/api/docs/
- **Schéma OpenAPI :** http://127.0.0.1:8000/api/schema/
- **Health check :** http://127.0.0.1:8000/api/v1/health/

## Authentification

| Méthode | Route | Description |
|---------|-------|-------------|
| `POST` | `/api/v1/auth/register/` | Inscription (responsable hôpital) |
| `POST` | `/api/v1/auth/login/` | Connexion (username + password → JWT) |
| `POST` | `/api/v1/auth/refresh/` | Rafraîchir le token |
| `GET` | `/api/v1/auth/me/` | Profil connecté |
| `POST` | `/api/v1/auth/otp/request/` | Demander un code OTP (`LOGIN` ou `RESET_PASSWORD`) |
| `POST` | `/api/v1/auth/otp/verify/` | Vérifier OTP (connexion sans mot de passe) |
| `POST` | `/api/v1/auth/password/forgot/` | Mot de passe oublié (envoi OTP) |
| `POST` | `/api/v1/auth/password/reset/` | Réinitialiser avec OTP + nouveau mot de passe |
| `POST` | `/api/v1/auth/password/change/` | Changer le mot de passe (connecté) |

En développement, les codes OTP sont affichés dans la console du serveur (`EMAIL_BACKEND=console`).

### Seed données de test

```bash
python manage.py seed_facilities
```

### Établissements (API)

| Méthode | Route | Accès |
|---------|-------|-------|
| `GET/POST` | `/api/v1/facilities/` | Liste / création |
| `GET/PATCH/DELETE` | `/api/v1/facilities/{id}/` | Détail / mise à jour / désactivation |
| `POST` | `/api/v1/facilities/import/` | Import JSON en masse |
| `POST` | `/api/v1/facilities/import/csv/` | Import CSV (`file`) |
| `GET/POST` | `/api/v1/facilities/{id}/services/` | Services d'un établissement |
| `GET/PATCH/DELETE` | `/api/v1/facilities/{id}/services/{sid}/` | Gestion d'un service |
| `GET/POST/DELETE` | `/api/v1/assignments/` | Affectations responsable ↔ établissement |

**Règles :** admin/ministère gèrent tout ; un responsable sans affectation peut créer/importer un établissement (rattachement auto) ; un responsable affecté gère uniquement le sien.

## Tests

```bash
python manage.py test --settings=config.settings.test
```

## Structure

```text
config/          # Settings, URLs, WSGI/ASGI
apps/
  common/        # Utilitaires partagés (pagination, permissions, exceptions)
  accounts/      # Utilisateurs, auth JWT, OTP
  facilities/    # Établissements sanitaires, services, affectations
requirements/    # Dépendances (base, dev, prod)
```

## Documentation

Voir [PLAN.md](PLAN.md) pour le plan d'implémentation par phases et [BLUEPRINT.md](BLUEPRINT.md) pour les spécifications métier.
