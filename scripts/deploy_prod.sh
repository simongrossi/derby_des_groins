#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/home/ubuntu/derby_des_groins}"
COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.prod.yml)

cd "${APP_DIR}"

echo "==> Pull latest main"
git fetch origin
git reset --hard origin/main

echo "==> Build web image"
docker compose "${COMPOSE_FILES[@]}" build web

echo "==> Start database"
docker compose "${COMPOSE_FILES[@]}" up -d db

echo "==> Run DB migrations in one-off container"
docker compose "${COMPOSE_FILES[@]}" run --rm -T -e RUN_DB_MIGRATIONS=0 web flask db upgrade

echo "==> Start web"
docker compose "${COMPOSE_FILES[@]}" up -d web

echo "==> Check routes"
docker compose "${COMPOSE_FILES[@]}" exec -T web python scripts/check_routes.py

echo "==> Health check"
docker compose "${COMPOSE_FILES[@]}" exec -T web python -c "import urllib.request; urllib.request.urlopen('http://localhost:5001/health', timeout=5); print('health: ok')"

echo "==> Recent logs"
docker compose "${COMPOSE_FILES[@]}" logs --tail=50 web
