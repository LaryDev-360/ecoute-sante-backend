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

Ou via Makefile :

```bash
make install
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
# ou
make run
```

- **Swagger UI :** http://127.0.0.1:8000/api/docs/
- **Schéma OpenAPI :** http://127.0.0.1:8000/api/schema/
- **Health check :** http://127.0.0.1:8000/api/v1/health/

### Commandes utiles (Makefile)

| Commande | Description |
|----------|-------------|
| `make db-up` | Démarrer PostgreSQL (Docker) |
| `make migrate` | Appliquer les migrations |
| `make seed` | Migrations + établissements + données démo |
| `make run` | Serveur de développement |
| `make test` | Suite de tests |

## CORS

Les origines autorisées sont configurées via `CORS_ALLOWED_ORIGINS` dans `.env` (séparées par des virgules). Par défaut : `http://localhost:3000`.

## Production

Variables essentielles (voir `.env.example`) :

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Clé secrète Django (longue, aléatoire) |
| `DEBUG` | `False` en production |
| `ALLOWED_HOSTS` | Domaines autorisés (séparés par des virgules) |
| `DATABASE_URL` | URL PostgreSQL (`postgres://user:pass@host:5432/db`) |
| `CORS_ALLOWED_ORIGINS` | Origines frontend HTTPS autorisées |

### Déploiement Render + Neon

#### 1. Base de données Neon

1. Créer un projet sur [neon.tech](https://neon.tech) (région proche de Frankfurt si possible).
2. Copier la **connection string** (format `postgresql://…@ep-….neon.tech/neondb?sslmode=require`).
3. Optionnel : renommer la base en `sante_ecoute` dans le SQL Editor Neon :
   ```sql
   CREATE DATABASE sante_ecoute;
   ```
   Puis ajuster le nom dans l’URL de connexion.

#### 2. Service web Render

**Option A — Blueprint (recommandé)**

1. Pousser le dépôt sur GitHub/GitLab.
2. Sur [render.com](https://render.com) : **New → Blueprint** → sélectionner le repo.
3. Render lit `render.yaml` et crée le service `sante-ecoute-api`.
4. Dans le dashboard Render → **Environment**, renseigner :
   - `DATABASE_URL` — URL Neon (avec `?sslmode=require`)
   - `CORS_ALLOWED_ORIGINS` — URL du frontend (ex. `https://mon-app.vercel.app`)
   - `OPENROUTER_API_KEY` — clé OpenRouter (si classification IA)
   - `OPENROUTER_APP_URL` — URL publique Render (ex. `https://sante-ecoute-api.onrender.com`)
5. Déployer ; les migrations s’exécutent via `preDeployCommand`.

**Option B — Manuel**

| Champ | Valeur |
|-------|--------|
| Runtime | Python 3 |
| Build Command | `./scripts/render_build.sh` |
| Pre-Deploy Command | `python manage.py migrate --noinput` |
| Start Command | `./scripts/render_start.sh` (migrations + gunicorn) |
| Health Check Path | `/api/v1/health/` |

Variables d’environnement :

| Variable | Valeur |
|----------|--------|
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` |
| `PYTHON_VERSION` | `3.10.14` |
| `SECRET_KEY` | générer une clé longue |
| `DEBUG` | `false` |
| `ALLOWED_HOSTS` | `.onrender.com` (+ domaine custom si besoin) |
| `DATABASE_URL` | URL Neon |

`RENDER_EXTERNAL_HOSTNAME` est injecté automatiquement par Render (ALLOWED_HOSTS + CSRF).

#### 3. Vérification

```bash
curl https://<votre-service>.onrender.com/api/v1/health/
# {"status":"ok"}
```

Swagger : `https://<votre-service>.onrender.com/api/docs/`

#### Dépannage — base Neon vide (0 tables)

Si le dashboard Neon affiche **0 tables**, les migrations n’ont pas été appliquées sur la base de production.

1. **Vérifier `DATABASE_URL` sur Render** (Environment) : elle doit pointer vers la base Neon `ecoute_sante`, par ex.  
   `postgresql://user:pass@ep-xxx.region.aws.neon.tech/ecoute_sante?sslmode=require`
2. **Vérifier les commandes de déploiement** :
   - Pre-Deploy : `python manage.py migrate --noinput`
   - Start : `./scripts/render_start.sh` (relance les migrations au démarrage si besoin)
3. **Appliquer les migrations immédiatement** — Render dashboard → votre service → **Shell** :
   ```bash
   python manage.py migrate --noinput
   ```
4. **Redéployer** (Manual Deploy) pour que le nouveau `render_start.sh` prenne effet.
5. Rafraîchir Neon → Tables : vous devriez voir `django_migrations`, `accounts_user`, `facilities_facility`, etc.

#### 4. Données initiales

Au **premier déploiement** (base sans utilisateurs), `render_migrate.sh` exécute automatiquement `seed_if_empty` (établissements, comptes démo, plaintes).

Pour forcer le seed manuellement (Render Shell) :

```bash
python manage.py seed_if_empty --force
# ou séparément :
python manage.py seed_facilities
python manage.py seed_data
```

En local : `make seed` (équivalent à `seed_if_empty --force` après migrate).

#### Limitations Render (plan gratuit)

- **Fichiers média** (`media/`) : disque éphémère — les pièces jointes sont perdues au redémarrage. Pour la prod, prévoir un stockage objet (S3, Cloudinary, etc.).
- **Cold start** : le service s’endort après inactivité (~15 s au premier appel).

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
make seed
# ou manuellement :
python manage.py seed_facilities
python manage.py seed_data
```

Comptes démo créés par `seed_data` :

| Utilisateur | Mot de passe | Rôle |
|-------------|--------------|------|
| `admin` | `admin123` | Administrateur |
| `ministry.bj` | `Ministry123!` | Superviseur ministère |
| `manager.cnhu` | `Manager123!` | Responsable CNHU |
| `manager.suru` | `Manager123!` | Responsable HZ Suru-Léré |
| `agent.a` / `agent.b` | `Agent123!` | Agents CNHU |

La commande crée aussi 8 plaintes variées (statuts, catégories, établissements) pour une démo bout-en-bout.

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
make test
# ou
python manage.py test --settings=config.settings.test
```

90 tests incluant 3 parcours d'intégration et 6 tests API IA (OpenRouter mocké).

### API publique (Phase 4)

| Méthode | Route | Description |
|---------|-------|-------------|
| `POST` | `/api/v1/complaints/` | Soumettre un signalement (+ pièces jointes) |
| `GET` | `/api/v1/complaints/track/{reference}/` | Suivre par référence |
| `GET` | `/api/v1/complaints/categories/` | Catégories actives |
| `GET` | `/api/v1/complaints/meta/submitter-profiles/` | Profils déclarant (usager / agent) |

### API hôpital (Phase 5)

| Méthode | Route | Description |
|---------|-------|-------------|
| `GET` | `/api/v1/hospital/dashboard/` | KPIs établissement |
| `GET` | `/api/v1/hospital/complaints/` | Liste (filtres : status, category, service, severity, dates) |
| `GET` | `/api/v1/hospital/complaints/{id}/` | Détail + historique + commentaires |
| `PATCH` | `/api/v1/hospital/complaints/{id}/status/` | Changer le statut |
| `PATCH` | `/api/v1/hospital/complaints/{id}/reject/` | Rejeter (motif obligatoire) |
| `POST` | `/api/v1/hospital/complaints/{id}/comments/` | Commentaire interne |

### API ministère (Phase 6)

| Méthode | Route | Description |
|---------|-------|-------------|
| `GET` | `/api/v1/ministry/dashboard/` | KPIs nationaux |
| `GET` | `/api/v1/ministry/analytics/` | Agrégats détaillés |
| `GET` | `/api/v1/ministry/complaints/` | Liste nationale (filtres) |
| `GET` | `/api/v1/ministry/complaints/?export=csv` | Export CSV via liste |
| `GET` | `/api/v1/ministry/complaints/export/` | Export CSV dédié |

### API IA (Phase 8)

| Méthode | Route | Description |
|---------|-------|-------------|
| `POST` | `/api/v1/ai/classify/` | Suggestion catégorie + priorité (OpenRouter, indicatif) |

Configurer `OPENROUTER_API_KEY` dans `.env` (clé gratuite sur [openrouter.ai](https://openrouter.ai)). Modèle par défaut : `openrouter/free`.

## Structure

```text
config/          # Settings, URLs, WSGI/ASGI
apps/
  common/        # Utilitaires partagés (pagination, permissions, exceptions)
  accounts/      # Utilisateurs, auth JWT, OTP
  facilities/    # Établissements sanitaires, services, affectations
  complaints/    # Plaintes, catégories, historique de statuts
  analytics/     # Services d'agrégation (ministère)
  ai/            # Classification assistée (OpenRouter)
requirements/    # Dépendances (base, dev, prod)
```

## Documentation

Voir [PLAN.md](PLAN.md) pour le plan d'implémentation par phases et [BLUEPRINT.md](BLUEPRINT.md) pour les spécifications métier.
