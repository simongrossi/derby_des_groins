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

### Phase 10 — Design, Responsive & Cohérence visuelle ✅
- [x] **10.1** Refonte complète du header (`_site_header.html`)
  - Menu hamburger mobile avec backdrop overlay cliquable
  - Balance compacte sur mobile, nav collapsible sous lg (1024px)
  - Backdrop `#nav-backdrop` cliquable pour fermer le menu
- [x] **10.2** Cohérence des breakpoints sur ~30 templates
  - `max-w-7xl` → `max-w-6xl` uniformisé
  - Grilles `xl:` ajout systématique de `md:` et `lg:` breakpoints
  - Titres `h1` responsifs : `text-3xl md:text-4xl lg:text-5xl`
- [x] **10.3** Standardisation `.card`, `.btn-primary`, `.form-input`
  - Couleurs unifiées sur tous les templates (gradient rose → orange)
  - Border/background glass effect cohérent (`rgba(255,255,255,0.055)`)
- [x] **10.4** Partials réutilisables
  - `_flash.html` : messages flash centralisés et intégrés dans tous les templates
  - `_footer.html` : footer partagé créé et intégré
- [x] **10.5** Migration Bootstrap → Tailwind dans `typing_game.html`
  - `.word-display` : `clamp(2rem, 8vw, 3.5rem)` pour responsive
  - `.input-box` : `clamp(1rem, 4vw, 1.5rem)`
- [x] **10.6** Intégration avatars pig dans tous les templates manquants

### Phase 11 — Bugfixes Docker & Sessions ✅
- [x] **11.1** Fix bug connexion admin/admin sur nouveau PC Docker
  - Cause racine : `SESSION_COOKIE_SECURE=True` (prod) + HTTP localhost = cookie refusé par le navigateur
  - Fix : `SECURE_COOKIES` env var (défaut `false`), à mettre `true` seulement derrière HTTPS
- [x] **11.2** Fix double initialisation `create_app()`
  - Gunicorn passé de `"app:create_app()"` → `"app:app"` pour éviter 2 appels
- [x] **11.3** `ensure_admin_user()` : transaction dédiée avant `seed_users()`
  - Admin committé indépendamment, immune aux échecs du seed général
- [x] **11.4** `docker-entrypoint.sh` : attente PostgreSQL conditionnelle
  - Skip si SQLite, timeout 30s → 40s, affichage de l'erreur au 1er essai

---

## TACHES RESTANTES

### Infrastructure / Environnement — Toutes terminees

*(Plus aucune tache d'infra restante)*

### Taches d'infra terminees

- [x] **1.7** SMTP credentials : deja gere via le panneau admin `/admin/notifications` (GameConfig en base)
- [x] **2.7** Sessions server-side : Flask-Session + SQLAlchemy/PostgreSQL (table `flask_sessions`, TTL 30 jours, prefixe `derby:`)
- [x] **2.8** Rate limiting : `Flask-Limiter 4.1.1` (storage en memoire)
  - Login/Register/Profil : 5 POST/min (anti brute-force)
  - Paris/Planning/Encheres : 10/min
  - Bourse move : 20/min, achats : 10/min
  - Blackjack deal/new : 15/min, hit/stand/double : 30/min
  - Actions cochon (feed/train) : 15/min, actions rares (breed/sacrifice) : 5/min
  - API GET (countdown, pig, replay...) : 30/min, live-state : 60/min
  - Galerie achats : 10/min, ventes : 5/min
  - Truffes : 10/min
  - Agenda (COMOP) : 10/min
  - Page 429 personnalisee (HTML + JSON pour les API)
  - Admin non limite (pas besoin)

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

### Phase 8 — Dockerisation + PostgreSQL ✅
- [x] **8.1** `Dockerfile` : image Python 3.12-slim, Gunicorn, healthcheck `/health`
- [x] **8.2** `docker-compose.yml` : services `web` + `db` (PostgreSQL 16-alpine), volume persistant `derby_pgdata`
- [x] **8.3** `docker-entrypoint.sh` : attente PostgreSQL + lancement Gunicorn (1 worker, 4 threads)
- [x] **8.4** `.env.example` : documentation de toutes les variables d'environnement
- [x] **8.5** `.dockerignore` : exclusion fichiers inutiles du build context
- [x] **8.6** `requirements.txt` : ajout `gunicorn==22.0.0` + `psycopg2-binary==2.9.9`
- [x] **8.7** Compatibilite PostgreSQL dans `app.py` `migrate_db()` :
  - `BOOLEAN DEFAULT 1/0` → `TRUE/FALSE`
  - Double quotes string defaults → single quotes
  - `json_object()` → `json_build_object()` (dialect-aware)
  - Table `trophy` creation redondante supprimee (`db.create_all()` suffit)
  - Noms de table quotes (`"user"`) dans les migrations SQL brutes
  - Pool engine conditionnel (SQLite vs PostgreSQL)
- [x] **3.1** `.env.example` cree
- [x] **3.2** Serveur WSGI Gunicorn configure
- [x] **2.1** Migration SQLite → PostgreSQL terminee

### Bugfix ✅
- [x] **BUG** Prime de pointage journaliere creditee en boucle (+15 a chaque page load)
  - Cause : `db.session.refresh(self)` ecrasait `last_daily_reward_at` avant le commit
  - Fix : flush le timestamp AVANT earn() pour le persister dans la transaction

### Phase 9 — Avatars cochons (pixel art) ✅
- [x] **9.1** Modele `PigAvatar` : bibliotheque d'avatars geree par l'admin
  - Champs : `name`, `filename`, `format` (png/svg), `created_at`
  - FK `Pig.avatar_id` → reference optionnelle vers un avatar
  - Propriete `Pig.avatar_url` pour acces direct au fichier
- [x] **9.2** Page admin `/admin/avatars` : gestion complete
  - Upload de fichiers PNG (64x64 pixel art) ou SVG
  - Collage de code SVG directement dans un textarea
  - Suppression d'avatar (delie automatiquement les cochons associes)
  - Lien ajoute dans la sidebar admin
- [x] **9.3** Selecteur d'avatar joueur sur `/mon-cochon`
  - Grille visuelle des avatars disponibles sous le selecteur d'emoji
  - Option "Pas d'avatar" pour revenir a l'emoji par defaut
  - Persistance via `POST /choose-avatar`
- [x] **9.4** Macro Jinja2 `_pig_avatar.html`
  - `pig_display(pig, size_class, img_size)` : affiche `<img>` si avatar, sinon `<span>` emoji
  - `style="image-rendering: pixelated"` pour le rendu pixel art net
- [x] **9.5** Integration dans tous les templates (20 fichiers)
  - Templates Jinja2 : index, courses, classement, profil, marche, cimetiere, abattoir, veterinaire, veterinaire_lobby, admin_pigs, mon_cochon
  - Templates JS (race_circuit.html, race_live.html) : helper `pigVisualHTML()` avec fallback emoji
  - SVG circuit : `<image>` SVG pour les marqueurs cochons avec avatar
  - Victory overlay, podium, lobby pre-course, scoreboard, stat cards
- [x] **9.6** Endpoints API enrichis avec `avatar_url`
  - `GET /api/pig` — avatar_url du cochon du joueur
  - `GET /api/race/<id>/replay` — avatar_url dans participant_meta
  - `GET /api/race/<id>/pre-race` — avatar_url par participant
- [x] **9.7** Stockage et persistance Docker
  - Dossier `static/avatars/` avec `.gitkeep`
  - Volume Docker `derby_avatars` monte sur `/app/static/avatars`

### Code optionnel (ameliorations futures)

| # | Tache | Effort | Detail |
|---|-------|--------|--------|
| 7 | **1.8** SRI sur CDN externes | 15 min | Bundler Tailwind en local plutot. Chart.js → pin version + SRI |
| 8 | **2.5** Batch `update_vitals()` | 30 min | Inutile si migration PostgreSQL (multi-writer). Sinon throttle 60s |

---

## VERIFICATION FINALE

| Test | Comment |
|------|---------|
| Docker | `docker compose up --build` → les 2 services demarrent sans erreur |
| Health | `curl http://localhost:5001/health` → `{"status": "ok", "database": "ok"}` |
| Site | `http://localhost:5001/` → le jeu fonctionne, login OK |
| Persistence | `docker compose down` puis `docker compose up` → les donnees persistent |
| Clean start | `docker compose down -v` puis `docker compose up` → re-seed correct |
| Securite | `curl -I /` : verifier Set-Cookie (HttpOnly, SameSite) |
| Performance | `/classement` avec 50+ users : 6 queries au lieu de 400+ |
| Redirect | Tester `/login?next=//evil.com` → doit rester sur le site |
| Debug | Verifier que `FLASK_DEBUG` n'est pas active en prod |
| Cookie sécurisé | Tester login en HTTP : doit fonctionner. En HTTPS avec `SECURE_COOKIES=true` : vérifier `Set-Cookie: Secure` |
