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

# Skip auto-collection if disabled via environment variable
if os.environ.get('SKIP_AUTO_COLLECT_STATIC') != 'true' and os.environ.get('DISABLE_AUTO_COLLECT') != 'true':
    if not os.path.exists(os.path.join(STATIC_ROOT, 'images')) or not os.listdir(STATIC_ROOT):
        print("Static files not found in production. Attempting auto-collection...")
        
        # Check if we have enough memory to run collectstatic
        try:
            import psutil
            available_memory = psutil.virtual_memory().available / (1024 * 1024)  # MB
            if available_memory < 100:  # Less than 100MB available
                print(f"Low memory detected ({available_memory:.1f}MB), skipping collectstatic")
                print("Will use fallback static file serving instead")
                raise MemoryError("Insufficient memory for collectstatic")
        except ImportError:
            # psutil not available, use alternative memory check
            try:
                import resource
                # Check memory limit (Linux/Unix systems)
                soft, hard = resource.getrlimit(resource.RLIMIT_AS)
                if soft != resource.RLIM_INFINITY and soft < 200 * 1024 * 1024:  # Less than 200MB
                    print("Low memory limit detected, skipping collectstatic")
                    raise MemoryError("Insufficient memory for collectstatic")
            except (ImportError, OSError):
                # resource not available or not applicable, assume we can proceed
                pass
        except MemoryError:
            # Memory too low, skip to fallback
            pass
        else:
            try:
                # Run collectstatic command with memory optimization
                result = subprocess.run([
                    sys.executable, 'manage.py', 'collectstatic', 
                    '--noinput', '--verbosity=0', '--clear'
                ], capture_output=True, text=True, cwd=BASE_DIR, timeout=300)  # 5 minute timeout
                
                if result.returncode == 0:
                    print("Static files collected successfully in production")
                else:
                    print(f"Error collecting static files: {result.stderr}")
                    print("Falling back to direct static file serving...")
            except subprocess.TimeoutExpired:
                print("collectstatic timed out, falling back to direct serving...")
            except Exception as e:
                print(f"Failed to auto-collect static files: {e}")
                print("Falling back to direct static file serving...")
else:
    print("Auto-collection disabled via SKIP_AUTO_COLLECT_STATIC")

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
    
    # Also try to copy essential files directly without collectstatic
    try:
        import shutil
        static_source = os.path.join(BASE_DIR, 'static')
        if os.path.exists(static_source):
            print(f"Copying essential static files from {static_source} to {STATIC_ROOT}")
            # Copy only essential directories to save memory
            for item in ['images', 'css', 'js']:
                src = os.path.join(static_source, item)
                dst = os.path.join(STATIC_ROOT, item)
                if os.path.exists(src):
                    try:
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                        print(f"Copied {item} directory successfully")
                    except Exception as copy_error:
                        print(f"Failed to copy {item}: {copy_error}")
                        # Continue with other directories
                        continue
        else:
            print(f"Static source directory {static_source} not found")
    except Exception as e:
        print(f"Failed to copy static files directly: {e}")
        print("Will serve static files directly from source directory")
else:
    print(f"STATIC_ROOT contains {len(os.listdir(STATIC_ROOT))} items, using WhiteNoise")

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

# Final verification and fallback
if not os.path.exists(os.path.join(STATIC_ROOT, 'images')):
    print("WARNING: Images directory still not found in STATIC_ROOT")
    print("Forcing fallback to direct static file serving...")
    
    # Ensure STATICFILES_DIRS is set for fallback
    if 'STATICFILES_DIRS' not in locals() or not STATICFILES_DIRS:
        STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
        print(f"Set STATICFILES_DIRS to: {STATICFILES_DIRS}")
    
    # Disable WhiteNoise if it's still enabled
    if 'whitenoise.middleware.WhiteNoiseMiddleware' in MIDDLEWARE:
        MIDDLEWARE.remove('whitenoise.middleware.WhiteNoiseMiddleware')
        print("Disabled WhiteNoise middleware for fallback")
    
    # Use Django's default static file storage
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
    print("Using Django's default static file serving as final fallback")
    
    # Verify static source exists
    static_source = os.path.join(BASE_DIR, 'static')
    if os.path.exists(static_source):
        print(f"Static source directory exists: {static_source}")
        print("Static files will be served directly from source")
    else:
        print(f"ERROR: Static source directory not found: {static_source}")
else:
    print("SUCCESS: Images directory found in STATIC_ROOT")

# Force static file collection if environment variable is set
if os.environ.get('FORCE_COLLECT_STATIC') == 'true':
    print("FORCE_COLLECT_STATIC detected, running collectstatic...")
    try:
        # Use memory-efficient approach
        result = subprocess.run([
            sys.executable, 'manage.py', 'collectstatic', 
            '--noinput', '--verbosity=0', '--clear', '--ignore=admin/*'
        ], capture_output=True, text=True, cwd=BASE_DIR, timeout=300)
        
        if result.returncode == 0:
            print("Static files collected successfully via FORCE_COLLECT_STATIC")
        else:
            print(f"Error collecting static files: {result.stderr}")
            print("Will use fallback static file serving")
    except subprocess.TimeoutExpired:
        print("FORCE_COLLECT_STATIC timed out, using fallback...")
    except Exception as e:
        print(f"Failed to force collect static files: {e}")
        print("Will use fallback static file serving")
