#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/home/ubuntu/derby_des_groins}"
COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.prod.yml)

cd "${APP_DIR}"

echo "==> Pull latest main"
git fetch origin
git reset --hard origin/main

echo "==> Build and start containers"
docker compose "${COMPOSE_FILES[@]}" up -d --build

echo "==> Run DB migrations"
docker compose "${COMPOSE_FILES[@]}" exec -T web flask db upgrade

echo "==> Check routes"
docker compose "${COMPOSE_FILES[@]}" exec -T web python scripts/check_routes.py

echo "==> Restart web"
docker compose "${COMPOSE_FILES[@]}" up -d web

echo "==> Health check"
docker compose "${COMPOSE_FILES[@]}" exec -T web python -c "import urllib.request; urllib.request.urlopen('http://localhost:5001/health', timeout=5); print('health: ok')"

echo "==> Recent logs"
docker compose "${COMPOSE_FILES[@]}" logs --tail=50 web
