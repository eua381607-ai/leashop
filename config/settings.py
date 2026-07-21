"""
Django settings for LeaShop project.

Configuration is environment-driven (12-factor style) so the same codebase
runs locally (SQLite fallback) and on Railway (PostgreSQL, Stripe live keys).
"""

from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DEBUG=(bool, False),
)
# Reads a local .env file if present (never commit this file — see .gitignore)
environ.Env.read_env(BASE_DIR / ".env")

# ------------------------------------------------------------------------
# Core
# ------------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", default="unsafe-dev-key-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=env.bool("DEBUG", default=False))

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Railway exposes the public domain here; auto-trust it if present.
RAILWAY_PUBLIC_DOMAIN = env("RAILWAY_PUBLIC_DOMAIN", default=None)
if RAILWAY_PUBLIC_DOMAIN:
    ALLOWED_HOSTS.append(RAILWAY_PUBLIC_DOMAIN)
    CSRF_TRUSTED_ORIGINS = [f"https://{RAILWAY_PUBLIC_DOMAIN}"]
else:
    CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# ------------------------------------------------------------------------
# Applications
# ------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Local apps
    "accounts",
    "catalog",
    "cart",
    "orders",
    "payments",
]

if DEBUG:
    try:
        import sslserver  # noqa: F401
    except ImportError:
        pass
    else:
        INSTALLED_APPS.append("sslserver")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "cart.middleware.CartMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "catalog.context_processors.categories",
                "cart.context_processors.cart",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ------------------------------------------------------------------------
# Database
#
# Locally, falls back to SQLite if DATABASE_URL isn't set so you can start
# developing immediately. On Railway, set DATABASE_URL to the Postgres
# plugin's connection string (Railway injects this automatically when you
# attach a PostgreSQL service to this project).
# ------------------------------------------------------------------------
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}
DATABASES["default"]["CONN_MAX_AGE"] = 60
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    DATABASES["default"].setdefault("OPTIONS", {})
    DATABASES["default"]["OPTIONS"].setdefault("timeout", 20)

AUTH_USER_MODEL = "accounts.User"

# ------------------------------------------------------------------------
# Password validation
# ------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ------------------------------------------------------------------------
# Internationalization
# ------------------------------------------------------------------------
LANGUAGE_CODE = env("LANGUAGE_CODE", default="fr-fr")
TIME_ZONE = env("TIME_ZONE", default="Africa/Porto-Novo")
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------------------
# Static & media files
# ------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@leashop.local")

_EMAIL_PROVIDER = env("EMAIL_PROVIDER", default="console")

if _EMAIL_PROVIDER == "resend":
    # Resend — native HTTP API backend (more reliable than SMTP relay)
    # Supports attachments and gives clear error messages.
    # Requires: pip install resend  (already in requirements.txt)
    EMAIL_BACKEND = "payments.email_backends.ResendEmailBackend"
    RESEND_API_KEY = env("RESEND_API_KEY", default="")
elif _EMAIL_PROVIDER == "smtp":
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("EMAIL_HOST", default="localhost")
    EMAIL_PORT = env.int("EMAIL_PORT", default=25)
    EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
    EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
    EMAIL_TIMEOUT = 30
else:
    # Default to console in development
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ------------------------------------------------------------------------
# Auth redirects
# ------------------------------------------------------------------------
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "catalog:product_list"
LOGOUT_REDIRECT_URL = "catalog:product_list"

# ------------------------------------------------------------------------
# Security (relaxed in DEBUG, hardened in production)
# ------------------------------------------------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ------------------------------------------------------------------------
# Stripe
# ------------------------------------------------------------------------
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")
# Currency used for Stripe Checkout Sessions (ISO 4217, lowercase)
STRIPE_CURRENCY = env("STRIPE_CURRENCY", default="usd")
# Payment methods accepted in Stripe Checkout. For mobile money support,
# enable the Stripe payment method that matches your region.
STRIPE_PAYMENT_METHOD_TYPES = env.list(
    "STRIPE_PAYMENT_METHOD_TYPES", default=["card"]
)

# Mobile money integration settings
MOBILE_MONEY_API_URL = env("MOBILE_MONEY_API_URL", default="")
MOBILE_MONEY_API_KEY = env("MOBILE_MONEY_API_KEY", default="")
MOBILE_MONEY_WEBHOOK_SECRET = env("MOBILE_MONEY_WEBHOOK_SECRET", default="")

# FedaPay integration settings
FEDAPAY_SECRET_KEY = env("FEDAPAY_SECRET_KEY", default="")
FEDAPAY_ENVIRONMENT = env("FEDAPAY_ENVIRONMENT", default="sandbox")
FEDAPAY_CURRENCY = env("FEDAPAY_CURRENCY", default="XOF")
FEDAPAY_WEBHOOK_SECRET = env("FEDAPAY_WEBHOOK_SECRET", default="")

# Base URL used to build absolute success/cancel URLs for Stripe Checkout
SITE_BASE_URL = env(
    "SITE_BASE_URL",
    default=f"https://{RAILWAY_PUBLIC_DOMAIN}" if RAILWAY_PUBLIC_DOMAIN else "http://127.0.0.1:8000",
)

# ------------------------------------------------------------------------
# Logging (structured enough for Railway's log viewer)
# ------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": env("DJANGO_LOG_LEVEL", default="INFO"),
    },
}
