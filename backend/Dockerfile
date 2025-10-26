# Backend Dockerfile - lightweight image for running Django (dev-friendly)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps needed to build a few Python packages (kept minimal)
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python requirements (only backend requirements)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ .

# Expose Django default port
EXPOSE 8000

# Default command: run Django development server
CMD ["python","manage.py","runserver","0.0.0.0:8000"]
