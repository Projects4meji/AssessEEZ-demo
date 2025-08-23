#!/bin/bash
# Build script for deployment

echo "=== BUILDING DJANGO PROJECT ==="

# Create staticfiles directory if it doesn't exist
echo "Creating staticfiles directory..."
mkdir -p staticfiles

# Clean up any existing staticfiles to avoid conflicts
echo "Cleaning up existing staticfiles..."
rm -rf staticfiles/*

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput --verbosity=2 --clear

# Check if static files were collected
echo "After collection - Staticfiles directory contents:"
ls -la staticfiles/

# Run migrations
echo "Running migrations..."
python manage.py migrate

echo "=== BUILD COMPLETED ==="
