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

### Phase 5 — Circuit Live (visualisation de course synchronisee) ✅
- [x] **5.1** `templates/race_circuit.html` : circuit SVG 2D plein ecran
  - Piste elliptique generee a partir des segments terrain reels
  - Segments colores par type (PLAT/MONTEE/DESCENTE/BOUE/VIRAGE) + icones
  - Animation des cochons (emojis) le long du circuit via `getPointAtLength()`
  - Panel stats lateral (vitesse, fatigue, phase strategie, terrain, events)
  - Camera follow mode (zoom sur le cochon en tete)
  - Controles : pause, vitesse x0.5/x1/x2/x4, fermer
  - Toasts flottants (trebuchement, sprint, franchissement ligne)
  - Ecran victoire anime avec podium top 5
- [x] **5.2** Lobby pre-course (T-50s avant depart)
  - Affiche participants + cotes + apercu segments colores + countdown
  - Countdown dramatique 10-9-8...3-2-1-GO! plein ecran
- [x] **5.3** Synchronisation multi-joueurs
  - `GET /api/race/live-state` : phase (idle/pre_race/countdown/racing) + seconds_to_start
  - Tous les clients pollent toutes les 3-4s → meme overlay au meme moment
  - Detection auto `finished_race_id` → fetch replay → animation simultanee
- [x] **5.4** Endpoints API
  - `GET /api/race/live-state` — synchro phase de course
  - `GET /api/race/<id>/pre-race` — participants + segments pour lobby
  - `GET /api/race/<id>/bets-spectator` — paris en cours (mode spectateur)
  - `GET /circuit` — page standalone du circuit
- [x] **5.5** Segments pre-generes
  - `Race.preview_segments_json` : colonne ajoutee au modele
  - `ensure_next_race()` genere les segments a la creation de course
  - `run_race_if_needed()` reutilise ces segments → circuit preview = course reelle
- [x] **5.6** Integration `race_live.html`
  - Bouton 🏟️ Circuit Live dans la barre de controle
  - Overlay iframe plein ecran (`position:fixed; inset:0; z-index:10000`)
  - Polling auto : ouverture overlay a T-50s, rechargement replay a la fin

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

### Phase 6 — Caches supplementaires ✅
- [x] **2.6b** Cache classement : cache memoire 5 min sur `_build_classement_data()`
  - Extraction de la logique en sous-fonction cacheable
  - `_classement_cache` dict avec TTL 300s
- [x] **2.6c** Cache cereales/trainings/lecons : cache memoire 5 min
  - `_game_data_cache` dict avec TTL 300s dans `helpers/game_data.py`
  - `invalidate_game_data_cache()` appele automatiquement via `after_request` sur le blueprint admin apres tout POST /admin/data/*

### Phase 7 — UX / Templates ✅
- [x] **7.1** Calendrier des courses : refonte du layout
  - Ancien : grille 7 colonnes avec header LUN-DIM trompeur, meme date repetee 7+ fois
  - Nouveau : groupement par jour (soft-card par date), creneaux horaires en lignes compactes
  - Ajout `date_key` + `date_label` dans la route pour groupby Jinja2
  - Chaque jour affiche : numero, nom jour + mois, theme, nombre de creneaux
  - Creneaux : heure, cochons inscrits (emojis), badges statut (Prochaine/Planifiable/N partants)
- [x] **7.2** Circuit Live : ecran idle au lieu d'ecran noir
  - Nouveau overlay `#idle-overlay` avec message "Aucune course en cours"
  - Affiche le temps restant avant la prochaine course si disponible
  - Boutons "Retour au Live" et "Fermer"
  - Se masque automatiquement quand une course passe en pre_race/countdown/racing
- [x] **7.3** Historique : onglets interactifs (Courses / Journal BitGroins / Mes Paris)
  - Les 3 sections etaient affichees simultanement sur une longue page
  - Transformees en vrais onglets avec show/hide JS
  - Navigation par URL hash (#courses, #bitgroins, #paris)
  - Styles ring actif par onglet (yellow/cyan/pink)

### Bugfix ✅
- [x] **BUG** Prime de pointage journaliere creditee en boucle (+15 a chaque page load)
  - Cause : `db.session.refresh(self)` ecrasait `last_daily_reward_at` avant le commit
  - Fix : flush le timestamp AVANT earn() pour le persister dans la transaction

### Code optionnel (ameliorations futures)

| # | Tache | Effort | Detail |
|---|-------|--------|--------|
| 7 | **1.8** SRI sur CDN externes | 15 min | Bundler Tailwind en local plutot. Chart.js → pin version + SRI |
| 8 | **2.5** Batch `update_vitals()` | 30 min | Inutile si migration PostgreSQL (multi-writer). Sinon throttle 60s |

---

## VERIFICATION FINALE

| Test | Comment |
|------|---------|
| Securite | `curl -I /` : verifier Set-Cookie (HttpOnly, SameSite) |
| Performance | `/classement` avec 50+ users : 6 queries au lieu de 400+ |
| Health | `curl /health` → `{"status": "ok", "database": "ok"}` |
| Redirect | Tester `/login?next=//evil.com` → doit rester sur le site |
| Debug | Verifier que `FLASK_DEBUG` n'est pas active en prod |
