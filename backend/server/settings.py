# backend/server/settings.py
from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv

load_dotenv()  # ← ensure .env is loaded

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-key")  # ← safer default
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

ALLOWED_HOSTS = [
    "localhost", "127.0.0.1", "[::1]",
    # add your Codespaces host or dev domains here if needed
    os.getenv("CODESPACES_HOST", "").strip() or "",  # optional
]
ALLOWED_HOSTS = [h for h in ALLOWED_HOSTS if h]  # remove empties

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",              # ← move high, before CommonMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "server.urls"

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

WSGI_APPLICATION = "server.wsgi.application"
ASGI_APPLICATION = "server.asgi.application"  # optional but nice to have

# --- Database (keep your logic) ---
DB = dj_database_url.parse(
    os.getenv("DATABASE_URL", "sqlite:///db.sqlite3"),
    conn_max_age=600,
)
if DB.get("ENGINE", "").endswith("postgresql"):
    DB["OPTIONS"] = {**DB.get("OPTIONS", {}), "sslmode": "require"}
DATABASES = {"default": DB}

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("TIME_ZONE", "UTC")  # set "Asia/Manila" if you like
USE_I18N = True
USE_TZ = True

# Static
STATIC_URL = "static/"
STATIC_ROOT = os.getenv("STATIC_ROOT", str(BASE_DIR / "staticfiles"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- CORS / CSRF for Vite ---
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
# Helpful for Codespaces / variable ports:
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https?:\/\/.*-.*-.*-.*\.githubpreview\.dev$",
    r"^https?:\/\/.*\.app\.github\.dev$",
]

CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
