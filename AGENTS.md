# AGENTS.md

## 1. Project overview
Flask web backend (Blueprint-based modular architecture) for a virtual betting/game system ("Derby des Groins").

Stack:
- Backend: Flask 3, SQLAlchemy, Flask-Migrate, APScheduler, Gunicorn
- Database: PostgreSQL (Docker/prod) / SQLite (local fallback)
- Frontend: Jinja2 SSR, Tailwind (CDN), Chart.js, Vanilla JS

## 2. Run / build / test commands
- Docker (PostgreSQL): `docker compose up -d --build`
- Local (SQLite): `python app.py`
- Migrations:
  - `export FLASK_APP=app:app`
  - `flask db migrate -m "description"`
  - `flask db upgrade`
- Seed: `flask seed-db`
- Tests: `pytest`

Inside Docker:
- Always use: `docker compose exec web flask ...`

## 3. Agent working rules
- Make **small, targeted changes only**
- Do NOT perform global refactors unless explicitly requested
- Do NOT introduce new frameworks (React, Vue, etc.)
- Reuse existing helpers/services before adding new abstractions
- Read adjacent files before modifying a module
- Keep routes thin; business logic belongs in `services/`
- Do NOT rewrite files for formatting or style only

## 4. Architecture conventions
- `routes/`: HTTP layer only (validation, auth, response)
  - MUST NOT contain business logic
- `services/`: all business/game logic
  - MUST be used by routes and scheduler
- `models.py`: single source of truth for SQLAlchemy models
- `scheduler.py`: async orchestration (races, events)
  - avoid heavy per-row DB loops

## 5. Security and compatibility constraints
- NEVER modify user balance directly
  - MUST use `record_balance_transaction`
- Preserve transaction integrity (commit / rollback consistency)
- Any change to `models.py` REQUIRES a migration (Alembic)
- Do NOT rely on `db.create_all()` for schema updates
- Do NOT break `.env` compatibility (cookies, sessions, DB config)
- Do NOT rename environment variables without full propagation
- Assume existing production data must remain valid

## 6. Verification triggers
- If `models.py` changes:
  - MUST run `flask db migrate` and review migration impact
  - Check compatibility with existing data (NULL / defaults / constraints)

- If `services/` or financial logic changes:
  - Verify transaction integrity (commit / rollback)
  - Check no direct balance mutation bypasses transaction system

- If `routes/` changes:
  - Ensure no business logic is introduced
  - Validate response consistency (HTML / JSON)

- If `scheduler.py` changes:
  - Check DB load (no N+1 / loops)
  - Ensure jobs remain idempotent

- If `templates/` or frontend JS changes:
  - Validate rendering (no broken variables or JS errors)

- If `requirements.txt` or `Dockerfile` changes:
  - MUST rebuild: `docker compose up -d --build`

- If `.env` or config changes:
  - Verify session handling and cookies still work
  - Validate DB connection

- If `app.py` changes:
  - Verify app boots correctly
  - Check `/health` endpoint: `curl http://localhost:5001/health`
