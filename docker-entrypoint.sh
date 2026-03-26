#!/bin/bash
set -e

DB_URL="${DATABASE_URL:-}"

if [[ "$DB_URL" == postgresql* ]]; then
    echo "Waiting for PostgreSQL..."
    python -c "
import time, sys, os
db_url = os.environ.get('DATABASE_URL', '')
for i in range(40):
    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        conn.close()
        print('PostgreSQL is ready!')
        sys.exit(0)
    except Exception as e:
        if i == 0:
            print(f'Waiting for DB... ({e})')
        time.sleep(1)
print('ERROR: PostgreSQL not ready after 40s')
sys.exit(1)
"
else
    echo "SQLite mode, skipping PostgreSQL wait."
fi

exec gunicorn \
    --bind 0.0.0.0:5001 \
    --workers 1 \
    --threads 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    "app:app"
