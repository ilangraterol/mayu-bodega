"""
Django settings for the Mayu Bodega project.

Business context: inventory, sales and credit (fiado) management for a small
warehouse/store operating natively in USD and VES (Bolívares).
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR.parent / '.env')

TESTING = 'test' in sys.argv


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {'1', 'true', 'yes', 'on'}


SECRET_KEY = os.getenv(
    'DJANGO_SECRET_KEY',
    'django-insecure-et0ilj=ka@y561)w1yfwn67dzt9$xpuu8hs%@fu6q+zwda+3=j',
)

DEBUG = env_bool('DJANGO_DEBUG', True)

ALLOWED_HOSTS = [h.strip() for h in os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]

CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    # Local
    'core',
    'catalog',
    'rates',
    'inventory',
    'customers',
    'sales',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 20,
        },
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# The default scrypt/PBKDF2 hashers make the suite take minutes. Tests only need
# a fast, deterministic hasher; production always keeps the Django defaults.
if TESTING:
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

LANGUAGE_CODE = 'es'

# Venezuela. Every timestamp stored in the database is timezone aware (UTC in DB,
# converted to America/Caracas on read).
TIME_ZONE = 'America/Caracas'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    }
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'core.permissions.IsAuthenticatedActiveUser',
    ],
    'EXCEPTION_HANDLER': 'core.exceptions.api_exception_handler',
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'core.search.UnaccentSearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.DefaultPagination',
    'PAGE_SIZE': 25,
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
}

# BCV official rate source. The backend syncs it through the `sync_bcv_rate`
# management command. The old mippetro.bcv.org.ve JSON endpoint no longer
# resolves, so the rate is read from the official site, which publishes it as
# "VES per 1 USD" inside the #dolar block.
BCV_RATE_URL = os.getenv('BCV_RATE_URL', 'https://www.bcv.org.ve/')
BCV_RATE_TIMEOUT_SECONDS = int(os.getenv('BCV_RATE_TIMEOUT_SECONDS', '15'))
# www.bcv.org.ve serves its leaf certificate without the Sectigo intermediate.
# Windows resolves it through the AIA URL, but certifi does not, so the chain
# fails verification. We ship that public intermediate and append it to the
# bundle instead of ever disabling verification for a money source.
BCV_RATE_CA_BUNDLE = os.getenv(
    'BCV_RATE_CA_BUNDLE',
    str(Path(BASE_DIR) / 'rates' / 'certs' / 'sectigo-intermediate.pem'),
)
# Minimum seconds between two upstream reads. Every sync performs exactly one
# request; a run started inside this window is skipped so a misconfigured
# scheduler cannot hammer the BCV.
BCV_RATE_MIN_INTERVAL_SECONDS = int(os.getenv('BCV_RATE_MIN_INTERVAL_SECONDS', '900'))

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB for product image uploads
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
