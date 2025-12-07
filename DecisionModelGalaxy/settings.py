"""
Unified settings for DecisionModelGalaxy
- Dev (Windows): minimal env needed; DEBUG on by default.
- Prod (Linux): OS-detected fallback so STATIC_ROOT/MEDIA_ROOT are set even without env vars.
"""
import os
import platform
from pathlib import Path
import posixpath


BASE_DIR = Path(__file__).resolve().parent.parent

# ---- Environment switches ----
DJANGO_ENV = os.getenv("DJANGO_ENV", "dev").lower()
IS_PROD = DJANGO_ENV == "prod"
IS_LINUX = platform.system() == "Linux"  # Treat Linux like prod by default

def env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name, str(default))
    return v.lower() in {"1", "true", "yes", "on"}

# ---- Core security/debug ----
# On servers (Linux) or when explicitly set to prod, use production-ish defaults.
if IS_PROD or IS_LINUX:
    DEBUG = env_bool("DEBUG", False)
    SECRET_KEY = os.getenv("SECRET_KEY") or "CHANGE_ME_IN_PROD"
    # Explicit hosts required in prod; default to '*' if not provided to avoid accidental lockouts
    ALLOWED_HOSTS = [h for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h] or ["*"]
    # CSRF origins should include https://… for your domains
    CSRF_TRUSTED_ORIGINS = [o for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o]
    # Tell Django we're behind a TLS-terminating proxy (e.g., Nginx)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
else:
    # Developer-friendly defaults (Windows)
    DEBUG = True
    SECRET_KEY = "dev-insecure-secret-key"  # fine for local only
    ALLOWED_HOSTS = ["*"]
    # Helpful if you post forms from localhost in dev
    CSRF_TRUSTED_ORIGINS = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000"
    ]

# ---- Apps ----
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Project apps
    "DSS",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "DecisionModelGalaxy.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [str(BASE_DIR / "templates")],  # project-level templates
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

WSGI_APPLICATION = "DecisionModelGalaxy.wsgi.application"

# ---- Database (SQLite by default) ----
# Keep SQLite for both; you can swap via env later if needed.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_DIR / "db.sqlite3"),
    }
}

# ---- Password validation ----
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---- I18N ----
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# ---- Static & media ----

STATIC_URL = "/static/"

if IS_PROD or IS_LINUX:
    # Production (Linux): collect static here; do NOT set STATICFILES_DIRS
    STATIC_ROOT = "/var/lib/DecisionModelGalaxy/static"
    STATICFILES_DIRS = []  # or omit the setting entirely
    MEDIA_URL = "/media/"
    MEDIA_ROOT = "/var/lib/DecisionModelGalaxy/media"
else:
    # Development (Windows): keep a source dir and a separate collect dir
    STATICFILES_DIRS = [str(BASE_DIR / "static")]   # source assets you edit
    STATIC_ROOT = str(BASE_DIR / "staticfiles")     # collect output (separate)
    MEDIA_URL = "/media/"
    MEDIA_ROOT = str(BASE_DIR / "media")

