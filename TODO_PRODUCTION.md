# Derby des Groins — TODO avant mise en production

> Audit realise le 24/03/2026.
> **Qualite du code** (6 points) : corriges.
> **Refactorisation helpers.py** : terminee.
> **Corrections code** (securite + perf + logging) : terminees.

---

## TACHES TERMINEES

### Phase 1 — Securite (code) ✅
- [x] **1.1** SECRET_KEY dynamique via `os.environ.get('SECRET_KEY')` + warning en prod
- [x] **1.2** Compte admin conditionne a `FLASK_ENV != production`
- [x] **1.3** Debug mode desactive par defaut (`FLASK_DEBUG=false`)
- [x] **1.4** Cookies session securises (`HttpOnly`, `SameSite=Lax`, `Secure` en prod)
- [x] **1.5** Validation redirect `next` avec `urlparse` (bloque `//evil.com`)
- [x] **1.6** Magic link URL via `url_for()` ou `BASE_URL` env (plus de Host header injection)

### Phase 2 — Performance ✅
- [x] **2.2** Requetes N+1 `/classement` : remplacees par 6 queries batch (avant: ~400 pour 100 users)
- [x] **2.3** 6 index supplementaires ajoutes (pig, bet, user, participant, balance_tx, course_plan)
- [x] **2.4** Context processor `inject_injured_pig_nav` cache en session (TTL 30s)
- [x] **2.6** Cache memoire `get_config()` avec TTL 10s + invalidation sur `set_config()`

### Phase 3 — Observabilite ✅
- [x] **3.3** Logging structure : middleware `after_request` (method, path, status, user_id)
- [x] **3.4** Health check `/health` (verifie DB + scheduler)

### Phase 4 — Refactorisation ✅
- [x] **4.1** `helpers.py` (1887 lig.) → package `helpers/` (830 lig., 8 modules)

### Qualite du code (session precedente) ✅
- [x] Suppression `update_item.py`
- [x] `except Exception: pass` → logging
- [x] 13 usages `|safe` → styles inline propres
- [x] Validation horaire HH:MM stricte
- [x] `_send_email` : message generique cote client
- [x] Mot de passe SMTP masque dans le HTML

---

## TACHES RESTANTES

### Infrastructure / Environnement (non-code)

| # | Tache | Effort | Detail |
|---|-------|--------|--------|
| 1 | **3.1** Creer `.env.example` | 2 min | SECRET_KEY, FLASK_DEBUG, DATABASE_URL, SMTP_*, etc. |
| 2 | **3.2** Serveur WSGI Gunicorn | 5 min | `gunicorn -w 4 -b 0.0.0.0:5000 'app:create_app()'` |
| 3 | **1.7** SMTP credentials en env vars | 10 min | Migrer smtp_password de GameConfig vers env vars |
| 4 | **2.1** Migration SQLite → PostgreSQL | 2-4h | 1 writer SQLite = bloquant multi-users. Script migration a creer |
| 5 | **2.7** Sessions server-side | 30 min | Flask-Session + Redis ou PostgreSQL |
| 6 | **2.8** Rate limiting | 10 min | `flask-limiter` : login 5/min, paris 10/min, API 30/min |

### Code optionnel (ameliorations futures)

| # | Tache | Effort | Detail |
|---|-------|--------|--------|
| 7 | **1.8** SRI sur CDN externes | 15 min | Ajouter `integrity=` + `crossorigin=` sur Tailwind/Chart.js/Fonts |
| 8 | **2.5** Batch `update_vitals()` | 30 min | 1 UPDATE par cochon a chaque page → batch ou cache |
| 9 | **2.6b** Cache classement | 20 min | Cache 5min sur `/classement` (deja optimise en queries batch) |
| 10 | **2.6c** Cache cereales/trainings | 10 min | Donnees quasi-statiques, cache au demarrage |

---

## VERIFICATION FINALE

| Test | Comment |
|------|---------|
| Securite | `curl -I /` : verifier Set-Cookie (HttpOnly, SameSite) |
| Performance | `/classement` avec 50+ users : 6 queries au lieu de 400+ |
| Health | `curl /health` → `{"status": "ok", "database": "ok"}` |
| Redirect | Tester `/login?next=//evil.com` → doit rester sur le site |
| Debug | Verifier que `FLASK_DEBUG` n'est pas active en prod |
