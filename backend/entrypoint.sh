#!/bin/sh
set -e

echo "Running database migrations..."
cd /app

# Multiple containers share the same entrypoint and may race to run migrations.
# Retry up to 5 times so that losers of the race (who see partial DDL state)
# can succeed once the winner finishes.
MAX_RETRIES=5
RETRY=0
until PYTHONPATH=/app alembic upgrade head; do
    RETRY=$((RETRY + 1))
    if [ "$RETRY" -ge "$MAX_RETRIES" ]; then
        echo "Migration failed after $MAX_RETRIES attempts, exiting."
        exit 1
    fi
    echo "Migration attempt $RETRY failed, retrying in 2s..."
    sleep 2
done

echo "Starting application..."
exec "$@"
