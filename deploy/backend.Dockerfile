FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend/ /app/backend/
WORKDIR /app/backend

RUN useradd --system --uid 10001 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app/backend /data

USER appuser
EXPOSE 8000

# Keep one Gunicorn worker: provisioning state and the 32-slot queue are in-process.
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn nokia_setup.wsgi:application --bind 0.0.0.0:8000 --workers 1 --threads 16 --timeout 120"]
