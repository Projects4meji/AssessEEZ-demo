#!/bin/bash
# Build script for deployment

echo "=== BUILDING DJANGO PROJECT ==="

# Show current directory and contents
echo "Current directory: $(pwd)"
echo "Directory contents:"
ls -la

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create staticfiles directory if it doesn't exist
echo "Creating staticfiles directory..."
mkdir -p staticfiles
echo "Staticfiles directory created:"
ls -la staticfiles/

# Show static directory contents
echo "Static directory contents:"
ls -la static/

# Collect static files with verbose output
echo "Collecting static files..."
python manage.py collectstatic --noinput --verbosity=2

# Check if static files were collected
echo "After collection - Staticfiles directory contents:"
ls -la staticfiles/

# Show static files structure
echo "Static files structure:"
find staticfiles -type f | head -20

# Run migrations
echo "Running migrations..."
python manage.py migrate

echo "=== BUILD COMPLETED ==="
