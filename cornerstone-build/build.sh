#!/bin/bash
# Build script for Cornerstone3D segmentation bundle

set -e

echo "Building Cornerstone3D segmentation bundle..."

# Navigate to build directory
cd "$(dirname "$0")"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# Build the bundle
echo "Building bundle..."
npm run build

# Copy to Django static files
echo "Copying bundle to Django static files..."
mkdir -p ../static/js
cp dist/cornerstone-segmentation.bundle.js ../static/js/

echo "✓ Build complete! Bundle available at: static/js/cornerstone-segmentation.bundle.js"
echo ""
echo "Next steps:"
echo "1. Run: python manage.py collectstatic --noinput"
echo "2. Restart your Django server"
