# COMET - Contour Metrics Application Dockerfile
FROM python:3.12

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgdcm-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    netcat-traditional \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create app user and directories
RUN groupadd -r comet && useradd -r -g comet comet \
    && mkdir -p /app /app/media /app/static /app/logs \
    && chown -R comet:comet /app

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY --chown=comet:comet requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy project
COPY --chown=comet:comet . .

# Create entrypoint script
COPY --chown=comet:comet docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Switch to non-root user
USER comet

# Expose port
EXPOSE 8000

# Use entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command: run gunicorn with extended timeout for DICOM processing
CMD ["gunicorn", "spatialmetrics.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "300", "--graceful-timeout", "60", "--keep-alive", "5"]
