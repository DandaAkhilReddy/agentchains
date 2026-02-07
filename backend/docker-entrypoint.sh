#!/bin/sh
# Run database migrations, then start the app
echo "Running Alembic migrations..."
alembic upgrade head || echo "Migration failed (DB may not be ready yet, will retry on next restart)"
echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
