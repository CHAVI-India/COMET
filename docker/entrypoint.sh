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

# Create logs directory if it doesn't exist
mkdir -p logs

# Determine which service to run
COMET_SERVICE=${COMET_SERVICE:-web}

if [ "$COMET_SERVICE" = "web" ]; then
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

    echo "Starting Gunicorn web server..."
    exec gunicorn spatialmetrics.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers ${GUNICORN_WORKERS:-4} \
        --timeout ${GUNICORN_TIMEOUT:-300} \
        --graceful-timeout ${GUNICORN_GRACEFUL_TIMEOUT:-60} \
        --keep-alive ${GUNICORN_KEEP_ALIVE:-5}

elif [ "$COMET_SERVICE" = "celery" ]; then
    echo "Starting Celery worker..."
    exec celery -A spatialmetrics worker \
        -l ${CELERY_WORKER_LOG_LEVEL:-info} \
        --concurrency ${CELERY_WORKER_CONCURRENCY:-4}

else
    echo "Unknown COMET_SERVICE: $COMET_SERVICE"
    echo "Valid options: web, celery"
    exit 1
fi
