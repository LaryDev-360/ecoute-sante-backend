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

## Structure

```text
config/          # Settings, URLs, WSGI/ASGI
apps/
  common/        # Utilitaires partagés (pagination, permissions, exceptions)
requirements/    # Dépendances (base, dev, prod)
```

## Documentation

Voir [PLAN.md](PLAN.md) pour le plan d'implémentation par phases et [BLUEPRINT.md](BLUEPRINT.md) pour les spécifications métier.
