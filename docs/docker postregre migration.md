Contexte
Le site tourne actuellement en local avec SQLite et le serveur de dev Flask. Pour la mise en production, il faut pouvoir cloner le repo sur n'importe quelle machine, lancer docker compose up, et le site est live avec PostgreSQL. Les taches restantes du TODO_PRODUCTION.md (migration PostgreSQL, Gunicorn, .env.example) sont couvertes par ce plan.

Fichiers a creer (5)
1. Dockerfile

Image python:3.12-slim
Install gcc, libpq-dev, curl (pour psycopg2 et healthcheck)
pip install -r requirements.txt
Copie du code, expose port 5001
HEALTHCHECK via curl http://localhost:5001/health
Entrypoint : docker-entrypoint.sh

2. docker-entrypoint.sh

Script bash qui attend que PostgreSQL soit pret (boucle Python avec psycopg2, max 30s)
Lance Gunicorn : gunicorn --bind 0.0.0.0:5001 --workers 1 --threads 4 --timeout 120 "app:create_app()"
1 worker pour eviter les doublons de scheduler APScheduler (suffisant pour le nombre de joueurs)

3. docker-compose.yml

Service db : postgres:16-alpine, volume nomme derby_pgdata, healthcheck pg_isready
Service web : build depuis le Dockerfile, depends_on: db (service_healthy), env vars configures
DERBY_FORCE_SCHEDULER=1 (Gunicorn n'est pas Werkzeug, donc le scheduler ne demarre pas sans ca)
DATABASE_URL=postgresql://derby:${POSTGRES_PASSWORD:-derby_secret}@db:5432/derby
env_file: .env avec defaults sensibles (fonctionne meme sans fichier .env)

4. .env.example

Toutes les variables documentees : POSTGRES_PASSWORD, SECRET_KEY, FLASK_ENV, DERBY_TIMEZONE, PORT

5. .dockerignore

Exclure : .venv/, __pycache__/, instance/, *.db, .git/, .env, .claude/, .gemini/, tests/


Fichiers a modifier (2)
6. requirements.txt
Ajouter :
gunicorn==22.0.0
psycopg2-binary==2.9.9
7. app.py — migrate_db() + create_app()
7a. Pool engine conditionnel (lignes 44-50) :
SQLite ne supporte pas pool_size/max_overflow. Ajouter un check sur le dialect :
pythondb_url = app.config['SQLALCHEMY_DATABASE_URI']
if 'sqlite' in db_url:
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}
else:
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True, 'pool_size': 10, 'max_overflow': 20,
        'pool_timeout': 60, 'pool_recycle': 300,
    }
7b. BOOLEAN defaults (lignes 113-142) :
BOOLEAN DEFAULT 1 → BOOLEAN DEFAULT TRUE, BOOLEAN DEFAULT 0 → BOOLEAN DEFAULT FALSE
(Syntaxe compatible SQLite 3.24+ ET PostgreSQL)
7c. Double quotes string defaults (lignes 121-123, 156) :
DEFAULT "commun" → DEFAULT 'commun' (PostgreSQL utilise les double quotes pour les identifiants)
7d. json_object → dialect-aware (lignes 215-222) :
pythonif db.engine.dialect.name == 'sqlite':
    conn.execute(db.text("UPDATE course_plan SET strategy_profile = json_object(...) WHERE ..."))
else:
    conn.execute(db.text("UPDATE course_plan SET strategy_profile = json_build_object(...)::text WHERE ..."))
7e. Trophy table creation (lignes 167-176) :
id INTEGER PRIMARY KEY → conditionnel (SERIAL PRIMARY KEY pour PostgreSQL) ou suppression (deja gere par db.create_all())

Sequence d'implementation

Modifier requirements.txt
Modifier app.py (5 corrections PostgreSQL)
Creer .dockerignore
Creer .env.example
Creer docker-entrypoint.sh
Creer Dockerfile
Creer docker-compose.yml


Verification

docker compose build — image se construit sans erreur
docker compose up — les 2 services demarrent, migrations OK, seeding OK
http://localhost:5001/health → {"status":"ok"}
http://localhost:5001/ → le jeu fonctionne
docker compose down puis docker compose up → les donnees persistent
docker compose down -v puis docker compose up → clean start, re-seed correct