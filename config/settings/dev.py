from .base import *  # noqa: F403

DEBUG = True

# Domaines locaux + tunnels publics (ngrok / cloudflare) pour tester les webhooks.
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "[::1]",
    ".ngrok-free.app",
    ".ngrok.io",
    ".trycloudflare.com",
]

# Le webhook arrive en HTTPS via le tunnel : on fait confiance à ces origines pour CSRF.
CSRF_TRUSTED_ORIGINS = [
    "https://*.ngrok-free.app",
    "https://*.ngrok.io",
    "https://*.trycloudflare.com",
]
