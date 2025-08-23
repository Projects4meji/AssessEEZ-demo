#!/bin/bash
# Build script for deployment

echo "Building Django project..."

# Install dependencies
pip install -r requirements.txt

# Collect static files with verbose output
echo "Collecting static files..."
python manage.py collectstatic --noinput --verbosity=2

# Run migrations
echo "Running migrations..."
python manage.py migrate

# List static files for debugging
echo "Static files collected:"
ls -la staticfiles/

echo "Build completed!"
