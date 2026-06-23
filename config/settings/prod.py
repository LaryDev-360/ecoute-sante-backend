from .base import *  # noqa: F403

DEBUG = False

# DATABASE_URL is required in production (Neon PostgreSQL).
if not env("DATABASE_URL", default=""):  # noqa: F405
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("DATABASE_URL must be set in production.")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

RENDER_EXTERNAL_HOSTNAME = env("RENDER_EXTERNAL_HOSTNAME", default="")  # noqa: F405
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS = [*ALLOWED_HOSTS, RENDER_EXTERNAL_HOSTNAME]  # noqa: F405
    CSRF_TRUSTED_ORIGINS = [
        *env.list("CSRF_TRUSTED_ORIGINS", default=[]),  # noqa: F405
        f"https://{RENDER_EXTERNAL_HOSTNAME}",
    ]

# Static files served by WhiteNoise (no separate CDN required on Render).
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# Neon PostgreSQL requires SSL; CONN_MAX_AGE reuses connections across requests.
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=600)  # noqa: F405
DATABASES["default"].setdefault("OPTIONS", {})
if env.bool("DATABASE_SSL", default=True):  # noqa: F405
    DATABASES["default"]["OPTIONS"]["sslmode"] = "require"

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)  # noqa: F405
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
