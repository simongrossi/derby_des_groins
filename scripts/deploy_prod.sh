#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.prod.yml)

echo "==> Pull latest code"
git pull --ff-only

echo "==> Build and start containers"
docker compose "${COMPOSE_FILES[@]}" up -d --build

echo "==> Run DB migrations"
docker compose "${COMPOSE_FILES[@]}" exec -T web flask db upgrade

echo "==> Restart web after migration"
docker compose "${COMPOSE_FILES[@]}" up -d web

echo "==> Health check"
docker compose "${COMPOSE_FILES[@]}" exec -T web python -c "import urllib.request; urllib.request.urlopen('http://localhost:5001/health', timeout=5); print('health: ok')"

echo "==> Recent logs"
docker compose "${COMPOSE_FILES[@]}" logs --tail=50 web
