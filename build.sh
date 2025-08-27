#!/bin/bash
# Build script for deployment

echo "=== BUILDING DJANGO PROJECT ==="

# Set Django settings to production
export DJANGO_SETTINGS_MODULE=AssessEEZ.production_settings
export FORCE_COLLECT_STATIC=true

# Create staticfiles directory if it doesn't exist
echo "Creating staticfiles directory..."
mkdir -p staticfiles

# Clean up any existing staticfiles to avoid conflicts
echo "Cleaning up existing staticfiles..."
rm -rf staticfiles/*

# Collect static files using production settings
echo "Collecting static files..."
python manage.py collectstatic --noinput --verbosity=2 --clear

# Check if static files were collected
echo "After collection - Staticfiles directory contents:"
ls -la staticfiles/

# Verify static files were collected
if [ -z "$(ls -A staticfiles)" ]; then
    echo "ERROR: No static files were collected!"
    exit 1
else
    echo "SUCCESS: Static files collected successfully"
fi

# Run migrations
echo "Running migrations..."
python manage.py migrate

echo "=== BUILD COMPLETED ==="
