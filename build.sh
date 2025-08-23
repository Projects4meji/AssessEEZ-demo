#!/bin/bash
# Build script for deployment

echo "Building Django project..."

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate

echo "Build completed!"
