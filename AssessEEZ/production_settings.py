"""
Production settings for AssessEEZ project.
This file contains production-specific configurations.
"""

import os
from .settings import *

# Force production mode
DEBUG = False

# Security settings for production
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Static files configuration for production
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'

# Ensure staticfiles directory exists
if not os.path.exists(STATIC_ROOT):
    os.makedirs(STATIC_ROOT, exist_ok=True)

# Auto-collect static files in production if directory is empty
import subprocess
import sys

if not os.path.exists(os.path.join(STATIC_ROOT, 'images')) or not os.listdir(STATIC_ROOT):
    print("Static files not found in production. Auto-collecting...")
    try:
        # Run collectstatic command
        result = subprocess.run([
            sys.executable, 'manage.py', 'collectstatic', '--noinput', '--verbosity=0'
        ], capture_output=True, text=True, cwd=BASE_DIR)
        
        if result.returncode == 0:
            print("Static files collected successfully in production")
        else:
            print(f"Error collecting static files: {result.stderr}")
    except Exception as e:
        print(f"Failed to auto-collect static files: {e}")

# WhiteNoise configuration for production
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.StaticFilesStorage'  # Changed to simpler storage

# Static files finders
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# Fallback: If staticfiles is empty, serve from STATICFILES_DIRS
if not os.listdir(STATIC_ROOT):
    print("STATIC_ROOT is empty, falling back to STATICFILES_DIRS")
    STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
    # Disable WhiteNoise and use Django's default static file serving
    if 'whitenoise.middleware.WhiteNoiseMiddleware' in MIDDLEWARE:
        MIDDLEWARE.remove('whitenoise.middleware.WhiteNoiseMiddleware')
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
    print("Using Django's default static file serving as fallback")

# Logging configuration for production
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
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        '': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

print(f"Production settings loaded - STATIC_ROOT: {STATIC_ROOT}")
print(f"DEBUG mode: {DEBUG}")
print("WhiteNoise middleware configured for production")

# Force static file collection if environment variable is set
if os.environ.get('FORCE_COLLECT_STATIC') == 'true':
    print("FORCE_COLLECT_STATIC detected, running collectstatic...")
    try:
        result = subprocess.run([
            sys.executable, 'manage.py', 'collectstatic', '--noinput', '--verbosity=0'
        ], capture_output=True, text=True, cwd=BASE_DIR)
        
        if result.returncode == 0:
            print("Static files collected successfully via FORCE_COLLECT_STATIC")
        else:
            print(f"Error collecting static files: {result.stderr}")
    except Exception as e:
        print(f"Failed to force collect static files: {e}")
