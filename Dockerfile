FROM python:3.12-slim

# gcc + libpq-dev : nécessaires pour compiler psycopg2-binary
# curl supprimé : healthcheck remplacé par Python pur (élimine nghttp2 CVE-2026-27135)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip pour éviter les vulnérabilités pip connues, puis installer les deps
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x docker-entrypoint.sh

EXPOSE 5001

# Healthcheck Python pur (pas de curl → pas de nghttp2)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request, sys; urllib.request.urlopen('http://localhost:5001/health', timeout=4); sys.exit(0)" || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
