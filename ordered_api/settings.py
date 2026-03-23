"""
Django settings for ordered-api.

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.1/ref/settings/
"""

from pathlib import Path
import os
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured
from corsheaders.defaults import default_headers

from ordered_api.db_config import get_django_databases

ENV = os.getenv("APP_MODE", "development")

if ENV == "staging":
    load_dotenv(".env.staging")
else:
    load_dotenv(".env")

ASGI_APPLICATION = "ordered_api.asgi.application"

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY")

DEBUG = os.getenv("DEBUG", "False") == "True"

if not DEBUG and not SECRET_KEY:
    raise ImproperlyConfigured("Set SECRET_KEY when DEBUG=False.")

_allowed = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()]
if _allowed:
    ALLOWED_HOSTS = _allowed
else:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
    if DEBUG:
        ALLOWED_HOSTS.append("dev4.undock.ngrok.io")

CORS_ALLOW_CREDENTIALS = True

_LOCALHOST_DEV_PORTS = range(3000, 3010)
_DEV_FRONTEND_ORIGINS = [
    *[f"http://localhost:{p}" for p in _LOCALHOST_DEV_PORTS],
    *[f"http://127.0.0.1:{p}" for p in _LOCALHOST_DEV_PORTS],
]
_DEV_CORS_EXTRAS = [
    *_DEV_FRONTEND_ORIGINS,
    "http://localhost:8686",
    "https://dev4.undock.ngrok.io",
]
_DEV_CORS_REGEXES = [
    r"^http://localhost(:\d+)?$",
    r"^http://127\.0\.0\.1(:\d+)?$",
    r"^http://\[::1\](:\d+)?$",
]

_cors_env = [o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
if _cors_env:
    # Production/staging list from env; in DEBUG also allow local frontends (Next, etc.),
    # otherwise a non-empty CORS_ALLOWED_ORIGINS skips the permissive branch below.
    if DEBUG:
        CORS_ALLOWED_ORIGINS = list(dict.fromkeys([*_cors_env, *_DEV_CORS_EXTRAS]))
        CORS_ALLOWED_ORIGIN_REGEXES = _DEV_CORS_REGEXES
    else:
        CORS_ALLOWED_ORIGINS = _cors_env
        CORS_ALLOWED_ORIGIN_REGEXES = []
    CORS_ALLOW_ALL_ORIGINS = False
elif DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOWED_ORIGINS = list(_DEV_CORS_EXTRAS)
    CORS_ALLOWED_ORIGIN_REGEXES = list(_DEV_CORS_REGEXES)
else:
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = []
    CORS_ALLOWED_ORIGIN_REGEXES = []

CORS_ALLOW_METHODS = [
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "OPTIONS",
]

# default_headers plus SPA / API client extras (idempotency-key is required for browser preflight).
CORS_ALLOW_HEADERS = list(
    dict.fromkeys(
        [
            *default_headers,
            "accept-encoding",
            "dnt",
            "origin",
            "idempotency-key",
            "cache-control",
        ]
    )
)

_csrf_env = [o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]
if _csrf_env:
    CSRF_TRUSTED_ORIGINS = _csrf_env
else:
    CSRF_TRUSTED_ORIGINS = [
        "https://*.run.app",
        "https://*.web.app",
        "http://localhost:8000",
        "http://localhost:8686",
        *_DEV_FRONTEND_ORIGINS,
    ]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "django_filters",
    # Ordered domain (Postgres / Supabase via DATABASE_URL)
    "apps.core",
    "apps.tenants",
    "apps.users",
    "apps.events",
    "apps.properties",
    "apps.jobs",
    "apps.bookings",
    "apps.service_requests",
    "apps.pricing",
    "apps.intake",
    "apps.technicians",
]

AUTH_USER_MODEL = "users.User"

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # Bearer Supabase JWT (operator SPA) — must run before SessionAuthentication
        "apps.users.authentication.SupabaseAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
}

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ordered_api.urls"
WSGI_APPLICATION = "ordered_api.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = get_django_databases(BASE_DIR, debug=DEBUG)

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
_staticfiles_backend = (
    "django.contrib.staticfiles.storage.StaticFilesStorage"
    if DEBUG
    else "whitenoise.storage.CompressedManifestStaticFilesStorage"
)
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": _staticfiles_backend,
    },
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

if not DEBUG:
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True") == "True"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "True") == "True"
    CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "True") == "True"
    SECURE_BROWSER_XSS_FILTER = os.getenv("SECURE_BROWSER_XSS_FILTER", "True") == "True"
    SECURE_CONTENT_TYPE_NOSNIFF = os.getenv("SECURE_CONTENT_TYPE_NOSNIFF", "True") == "True"
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if DEBUG:
    GOOGLE_CLOUD_CREDENTIALS = os.getenv("GOOGLE_CLOUD_CREDENTIALS")
    if GOOGLE_CLOUD_CREDENTIALS:
        GOOGLE_CLOUD_CREDENTIALS_PATH = os.path.join(BASE_DIR, GOOGLE_CLOUD_CREDENTIALS)
    else:
        GOOGLE_CLOUD_CREDENTIALS_PATH = None

GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "matterseek-staging")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-east4")
GOOGLE_CLOUD_STORAGE_BUCKET = os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET", "matterseek-staging")
GOOGLE_SERVICE_ACCOUNT = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT",
    "matterseek@matterseek-staging.iam.gserviceaccount.com",
)
GOOGLE_CLOUD_RUN_URL = os.getenv("API_URL", "https://dev4.undock.ngrok.io")

LOGFIRE_TOKEN = os.getenv("LOGFIRE_TOKEN")
