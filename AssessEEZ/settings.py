from pathlib import Path
import os
from datetime import timedelta

# Try to import optional dependencies
try:
    import dj_database_url
except ImportError:
    dj_database_url = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from decouple import config
except ImportError:
    # Simple fallback for config function
    def config(key, default=None, cast=None):
        return os.environ.get(key, default)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# Import local settings for development first
try:
    from .local_settings import *
except ImportError:
    pass

# Use local settings if available, otherwise try to load from environment
try:
    SECRET_KEY = config('SECRET_KEY')
except:
    SECRET_KEY = 'django-insecure-your-secret-key-here-change-this-in-production'

DEBUG = config('DEBUG', default=False, cast=bool)

try:
    ALLOWED_HOSTS = config('ALLOWED_HOSTS').split(',')
except:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '.railway.app', '.render.com', '.herokuapp.com']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'users.apps.UsersConfig',
    'qualifications.apps.QualificationsConfig',
    'captcha',
    'stripe_payments.apps.StripePaymentsConfig',
    #'debug_toolbar',  # Add this
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    #'csp.middleware.CSPMiddleware',
    #'debug_toolbar.middleware.DebugToolbarMiddleware',  # Add this after other middleware
   ]

ROOT_URLCONF = 'AssessEEZ.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'AssessEEZ.context_processors.user_context',  # Add this
            ],
        },
    },
]

WSGI_APPLICATION = 'AssessEEZ.wsgi.application'

# Database
if dj_database_url:
    try:
        DATABASES = {
            'default': dj_database_url.parse(config('DATABASE_URL'))
        }
    except:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

DATA_UPLOAD_MAX_MEMORY_SIZE = 1048576000
FILE_UPLOAD_MAX_MEMORY_SIZE = 1048576000

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'users.CustomUser'

# Authentication configuration
AUTHENTICATION_BACKENDS = [
    'users.auth.BusinessIDAuthBackend',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
}

SIMPLE_JWT = {
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,
    'UPDATE_LAST_LOGIN': False,
    'ALGORITHM': 'HS256',
}

LOG_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'assess_eez.log'),
            'formatter': 'verbose',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 5,
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'qualifications': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'users': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        '': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# Email settings
try:
    EMAIL_BACKEND = 'AssessEEZ.email_backends.SESEmailBackend'
    DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL')
    PASSWORD_RESET_TIMEOUT = config('PASSWORD_RESET_TIMEOUT', cast=int)
except:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    DEFAULT_FROM_EMAIL = 'noreply@assesseez.co.uk'
    PASSWORD_RESET_TIMEOUT = 3600

SUPPORT_EMAIL = 'support@assesseez.co.uk'

# Site URL and Login URL
try:
    SITE_URL = config('SITE_URL')
    LOGIN_URL = config('LOGIN_URL')
except:
    SITE_URL = 'http://localhost:8000'
    LOGIN_URL = '/login/'

# DigitalOcean Spaces configuration for media files
try:
    AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME')
    AWS_S3_ENDPOINT_URL = config('AWS_S3_ENDPOINT_URL')
    AWS_S3_CUSTOM_DOMAIN = config('AWS_S3_CUSTOM_DOMAIN')
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',
    }
    AWS_DEFAULT_ACL = 'public-read'  # Media files are publicly accessible
    AWS_S3_FILE_OVERWRITE = False  # Prevent overwriting files with the same name
    AWS_S3_SIGNATURE_VERSION = 's3v4'

    # Configure Django to use DigitalOcean Spaces for media files
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

    # Media files served from DigitalOcean Spaces
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'
except:
    # Use local file storage for development
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'

try:
    RECAPTCHA_PUBLIC_KEY = config('RECAPTCHA_SITE_KEY')
    RECAPTCHA_PRIVATE_KEY = config('RECAPTCHA_SECRET_KEY')
except:
    # Use test keys for development
    RECAPTCHA_PUBLIC_KEY = '6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI'
    RECAPTCHA_PRIVATE_KEY = '6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe'

CSP_DEFAULT_SRC = ["'self'"]
CSP_SCRIPT_SRC = [
    "'self'",
    "'unsafe-inline'",
    'https://code.jquery.com',
    'https://cdn.jsdelivr.net',
]
CSP_STYLE_SRC = [
    "'self'",
    "'unsafe-inline'",
    'https://assesseez.lon1.cdn.digitaloceanspaces.com',
    'https://cdn.jsdelivr.net',
]
CSP_IMG_SRC = [
    "'self'",
    'https://assesseez.lon1.cdn.digitaloceanspaces.com',
]
CSP_MEDIA_SRC = [
    "'self'",
    'https://assesseez.lon1.cdn.digitaloceanspaces.com',
]
CSP_FRAME_SRC = ["'self'"]
CSP_CONNECT_SRC = ["'self'"]
CSP_FRAME_ANCESTORS = ["'self'"]
CSP_REPORT_ONLY = False

# Stripe Configuration
STRIPE_PUBLIC_KEY = config('STRIPE_PUBLIC_KEY', default='pk_test_51R3Q1PEYQxHtXYU4qOCuPhqRA97YpuM2Nvry3lHdfMLzngKRzdRIm7hJ5mYsg2qZ1xfletQWIda9esqqNmLhI6Cp00Q1AN1iTT')
STRIPE_SECRET_KEY = config('STRIPE_SECRET_KEY', default='sk_test_51R3Q1PEYQxHtXYU4rAo2IAxXrezUQ8Cmwk7hsH5A2qOlekKC2NM26b82pnyjeSMRWcIeFd5PBLcLgsAs7upo9Ysr00MNYn2ID0')
STRIPE_WEBHOOK_SECRET = config('STRIPE_WEBHOOK_SECRET', default='whsec_your_webhook_secret_here')  # You'll need to set this up in Stripe Dashboard

#INTERNAL_IPS = [
 #  '127.0.0.1',
  #'localhost',
#]

