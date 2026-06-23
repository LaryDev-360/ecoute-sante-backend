"""
Shared Django settings for Santé Écoute.
"""
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
)

environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "corsheaders",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    # Local apps
    "apps.common",
    "apps.accounts",
    "apps.facilities",
    "apps.complaints",
    "apps.analytics",
    "apps.ai",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL"),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Porto-Novo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Pièces jointes plaintes
COMPLAINT_ATTACHMENT_MAX_SIZE = 5 * 1024 * 1024  # 5 Mo
COMPLAINT_ATTACHMENT_ALLOWED_TYPES = [
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# OTP & e-mail
OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 10
OTP_MAX_ATTEMPTS = 5

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@sante-ecoute.bj")
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.common.exceptions.custom_exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        "auth": "20/min",
        "otp": "5/min",
        "public_complaint": "30/hour",
        "ai_classify": "20/hour",
    },
}

# OpenRouter (classification IA — Phase 8)
OPENROUTER_API_KEY = env("OPENROUTER_API_KEY", default="")
OPENROUTER_MODEL = env("OPENROUTER_MODEL", default="openrouter/free")
OPENROUTER_BASE_URL = env("OPENROUTER_BASE_URL", default="https://openrouter.ai/api/v1")
OPENROUTER_TIMEOUT = env.int("OPENROUTER_TIMEOUT", default=15)
OPENROUTER_APP_NAME = env("OPENROUTER_APP_NAME", default="Santé Écoute")
OPENROUTER_APP_URL = env("OPENROUTER_APP_URL", default="http://localhost:8000")

# Mistral (médiateur vocal Gbègbe — modèle audio Voxtral)
MISTRAL_API_KEY = env("MISTRAL_API_KEY", default="")
MISTRAL_MODEL = env("MISTRAL_MODEL", default="voxtral-small-latest")
MISTRAL_BASE_URL = env("MISTRAL_BASE_URL", default="https://api.mistral.ai/v1")
MISTRAL_TIMEOUT = env.int("MISTRAL_TIMEOUT", default=30)

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Santé Écoute API",
    "DESCRIPTION": "API de gestion des signalements et plaintes sanitaires",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "TAGS": [
        {"name": "Health", "description": "Santé de l'API"},
        {"name": "Auth", "description": "Authentification JWT"},
        {"name": "Public", "description": "Endpoints publics (soumission, suivi)"},
        {"name": "Facilities", "description": "Établissements sanitaires"},
        {"name": "Hospital", "description": "Gestion hôpital"},
        {"name": "Ministry", "description": "Supervision ministère"},
        {"name": "AI", "description": "Classification assistée"},
    ],
}
