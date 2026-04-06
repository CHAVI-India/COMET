#!/bin/bash

# COMET Application Entrypoint Script
set -e

echo "================================"
echo "COMET - Contour Metrics"
echo "================================"

# Wait for database to be ready
echo "Waiting for PostgreSQL..."
while ! nc -z ${DJANGO_DB_HOST:-comet-db} ${DJANGO_DB_PORT:-5432}; do
    sleep 0.1
done
echo "PostgreSQL is ready!"

# Wait for RabbitMQ to be ready
echo "Waiting for RabbitMQ..."
while ! nc -z comet-rabbitmq 5672; do
    sleep 0.1
done
echo "RabbitMQ is ready!"

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Create superuser if credentials are provided and user doesn't already exist
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "Checking for superuser..."
    python manage.py createsuperuser --noinput 2>/dev/null && echo "Superuser created." || echo "Superuser already exists, skipping."
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Execute the provided command
echo "Starting COMET application..."
exec "$@"
