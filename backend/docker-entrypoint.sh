#!/bin/sh
set -e

echo "Running Alembic migrations..."
MAX_RETRIES=5
RETRY_DELAY=5
for i in $(seq 1 $MAX_RETRIES); do
    if alembic upgrade head; then
        echo "Migrations completed successfully."
        break
    fi
    if [ "$i" = "$MAX_RETRIES" ]; then
        echo "FATAL: Migrations failed after $MAX_RETRIES attempts. Exiting."
        exit 1
    fi
    echo "Migration attempt $i failed. Retrying in ${RETRY_DELAY}s..."
    sleep $RETRY_DELAY
done

echo "Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
