# Release Updates

Journal compact des changements notables du projet.

Objectif:
- suivre les refactors et features livrees sans noyer `DONE.md`;
- garder une trace chronologique exploitable apres chaque phase;
- faciliter les reprises de contexte et la redaction de changelogs plus visibles plus tard.

## 2026-04-06

### Phase 11 — Dactylo Porcin et restructuration des mini-jeux
- séparation stricte du *Cochon Pendu* (pendu classique) et de la nouvelle *Académie Dactylographique* (jeu de vitesse de frappe) ;
- création de `routes/academie.py` et `templates/academie.html` pour héberger le nouveau jeu de frappe ;
- ajout de la prise en charge du clavier physique natif `keydown` dans le *Cochon Pendu* pour jouer plus confortablement ;
- mise en place de la table `academie_score` et du modèle `AcademieScore` (avec relation utilisateur) ;
- implémentation d'un algorithme de score complexe :
  - **Difficulté du mot** : +100 points/lettre, +50 points/lettre unique ;
  - **Bonus de temps** : système de timer dégressif ultra rapide (-50 points par seconde) ;
  - **Pénalité d'erreur** : -150 points par coquille.
- intégration d'un classement (Leaderboard) sur la page du jeu affichant le Top 15 ;
- ajout d'une entrée "Dactylo Porcin" dans le sous-menu de l'Arcade (`_site_header.html`).

---

## 2026-04-05

### Phase 10 — Gameplay settings adminables, bundle export/import et rééquilibrage

#### Nouveaux services
- création de `services/gameplay_settings_service.py` :
  - deux dataclasses immutables : `GameplaySettings` (cap entraînement, cooldown école, rendement décroissant) et `MinigameSettings` (tous les réglages Pendu, Agenda, Truffes) ;
  - lecture/écriture via `GameConfig` (blobs JSON `settings_gameplay` / `settings_minigames`) ;
  - builders de formulaire (`build_gameplay_settings_from_form`, `build_minigame_settings_from_form`) ;
  - parsers pour import de bundle (`parse_bundle_gameplay_settings`, `parse_bundle_minigame_settings`).
- création de `services/game_settings_bundle_service.py` :
  - `build_game_settings_bundle_json()` — sérialise **tous** les réglages admin en un seul JSON versionné (`schema_version: 1`) ;
  - `build_game_settings_bundle_filename()` — nom horodaté `derby-des-groins-settings-<timestamp>.json` ;
  - `import_game_settings_bundle()` — validation du schema, dispatch par section, appel des services de sauvegarde dédiés, invalidation du cache config.
- ajout dans `routes/admin.py` :
  - action `save_gameplay` et `save_minigames` dans `/admin/economy` ;
  - action `import_settings_bundle` (fichier ou JSON brut) dans `/admin/economy` ;
  - route `GET /admin/settings-bundle/export` — téléchargement direct du bundle JSON.

#### Règles poids cochon adminables (refactor `pig_power_service`)
- `PigWeightRules` est maintenant persisté en JSON dans `GameConfig` (`settings_pig_weight_rules`) ;
- `_load_weight_rules()` le recharge depuis la base (avec fallback sur les constantes statiques de `game_rules.py`) ;
- `get_pig_settings()` retourne désormais un champ `weight_rules: PigWeightRules` ;
- `calculate_target_weight_kg`, `get_weight_profile`, `generate_weight_kg_for_profile` sont branchés sur les règles live au lieu des constantes.

#### Rééquilibrages (`config/economy_defaults.py`, `config/game_rules.py`, `config/gameplay_defaults.py`)

| Paramètre | Avant | Après |
|---|---|---|
| `FEEDING_PRESSURE_PER_PIG` | 0.20 | 0.10 |
| `RACE_APPEARANCE_REWARD` | 6 | 12 🪙 |
| `RACE_POSITION_REWARDS` 2e/3e | 50 / 25 | 60 / 35 🪙 |
| `WEEKLY_RACE_QUOTA` | 3 | 5 |
| `TAX_THRESHOLD_1` | 2 000 | 3 000 🪙 |
| `TAX_THRESHOLD_2` | 5 000 | 10 000 🪙 |
| `PIG_DEFAULTS.max_races` | 80 | 40 |
| `PENDU_FREE_PLAYS_PER_DAY` | 3 | 2 |
| `VET_RESPONSE_MINUTES` | 20 | 720 (12 h) |

- la pression de nourrissage est abaissée pour réduire le coût des porcheries multi-cochons ;
- les récompenses de course et le quota hebdo montent pour encourager les joueurs occasionnels ;
- les seuils de taxe anti-baleine remontent pour ne pénaliser que les vrais accumulations ;
- la durée de vie par défaut des cochons est réduite de moitié (turnover plus rapide) ;
- le Cochon Pendu passe à 2 parties gratuites (équilibrage quotidien) ;
- la fenêtre vétérinaire passe à 12 h pour permettre aux joueurs bureau de réagir sur le temps de midi ou le soir.

#### Helpers renforcés
- `helpers/veterinary.py` :
  - `get_vet_window_seconds()` — fenêtre dynamique (lit `vet_response_minutes` via `get_pig_settings()`) ;
  - `get_vet_care_costs(base_energy, base_happiness, seconds_left)` — coûts progressifs selon le temps écoulé dans la fenêtre (pénalité doublée sur le bonheur en fin de fenêtre).
- `helpers/time_helpers.py` — `format_duration_short` gère maintenant les durées de plusieurs heures/jours (format `Xj YYh` / `Xh YYm`) pour l'affichage du délai vétérinaire.
- `helpers/config.py` — `init_default_config()` initialise les nouvelles clés : `settings_gameplay`, `settings_minigames`, `settings_pig_weight_rules`, `pig_default_max_races`.

#### Nouvelles suites de tests
- `tests/test_progression_balance.py` — vérifie les propriétés macroscopiques du système économique (gains nets, inflation) ;
- `tests/test_settings_bundle_service.py` — import/export du bundle JSON (round-trip, schema invalide, section inconnue) ;
- `tests/test_veterinary.py` — `get_vet_care_costs` (coûts minimaux, coûts en fin de fenêtre, cas limites).

Vérification locale :
- `python3 -m py_compile services/gameplay_settings_service.py services/game_settings_bundle_service.py helpers/veterinary.py helpers/time_helpers.py helpers/config.py services/pig_power_service.py services/pig_service.py routes/admin.py` : OK.

---

## 2026-04-04

### Phase 9 - Stabilisation de l'infra de test et finitions UI/maintenance
- ajout de `tests/support.py` et `tests/__init__.py` pour fournir:
  - une factory de test isolee;
  - un reset de schema base par base;
  - un seed minimal reutilisable pour les tests routes/integration;
- `config/app_config.py` utilise maintenant une base SQLite dediee en mode `testing` au lieu de retomber sur la base locale par defaut;
- rebranchement des suites fragiles vers cette infra isolee:
  - `tests/test_truffes.py`;
  - `tests/test_betting.py`;
  - `tests/test_auth_logs.py`;
  - `tests/test_admin_auth_logs.py`;
  - `tests/test_admin_hangman_words.py`;
- correction des hypotheses de test PMU pour planifier des courses encore ouvertes au moment de la prise de ticket;
- correction du quota Truffes pour qu'il descende aussi sur les comptes admin et arret des dependances implicites a la vieille SQLite locale;
- polissage du menu mobile en mode clair dans `templates/_site_header.html` et `templates/_theme_assets.html`;
- correction d'un oubli CSRF sur l'action rapide `Donner une friandise` de la page d'accueil (`templates/index.html`);
- passe de maintenance sur quelques appels deprecias:
  - `db.session.get(...)` a la place de `Query.get(...)` sur plusieurs chemins critiques;
  - horodatages UTC naifs centralises dans plusieurs modules metier.

Verification locale:
- `python3 -m py_compile config/app_config.py tests/support.py tests/test_betting.py tests/test_auth_logs.py tests/test_admin_auth_logs.py tests/test_admin_hangman_words.py tests/test_truffes.py helpers/auth.py services/bet_service.py services/finance_service.py services/auth_log_service.py routes/truffes.py services/classement_page_service.py models/user.py services/pig_service.py`: OK;
- `./.venv/bin/python -m unittest tests.test_truffes tests.test_betting tests.test_auth_logs tests.test_admin_auth_logs tests.test_admin_hangman_words`: OK.

### Phase 8 - Amincissement final du panneau admin (cochons, evenements, notifications, truffes, donnees, avatars)
- creation de `services/admin_pig_service.py` pour sortir de `routes/admin.py`:
  - le toggle vie/mort des cochons admin;
  - le soin immediat des cochons;
- creation de `services/admin_event_service.py` pour centraliser le declenchement des evenements globaux admin;
- creation de `services/admin_notification_service.py` pour centraliser:
  - la lecture/sauvegarde des reglages SMTP;
  - l'envoi de mail de test;
- creation de `services/admin_truffes_service.py` pour sortir la construction et la sauvegarde des reglages Truffes;
- creation de `services/admin_game_data_service.py` pour centraliser le CRUD admin de:
  - cereales;
  - entrainements;
  - lecons;
  - mots du pendu;
- creation de `services/admin_avatar_service.py` pour centraliser:
  - l'upload d'avatars;
  - l'edition SVG;
  - la suppression d'avatars;
  - les validations de format/taille/contenu;
- remplacement dans `routes/admin.py` des validations inline par des `ValidationError`/`BusinessRuleError` metier sur les formulaires admin sensibles;
- ajout des tests unitaires:
  - `tests/test_admin_avatar_service.py`;
  - `tests/test_admin_event_service.py`;
  - `tests/test_admin_game_data_service.py`;
  - `tests/test_admin_notification_service.py`.

Verification locale:
- `python3 -m py_compile routes/admin.py services/admin_avatar_service.py services/admin_event_service.py services/admin_game_data_service.py services/admin_notification_service.py services/admin_pig_service.py services/admin_truffes_service.py tests/test_admin_avatar_service.py tests/test_admin_event_service.py tests/test_admin_game_data_service.py tests/test_admin_notification_service.py`: OK;
- `./.venv/bin/python -m unittest tests.test_admin_avatar_service tests.test_admin_game_data_service tests.test_admin_notification_service tests.test_admin_event_service tests.test_admin_race_service tests.test_admin_user_service tests.test_admin_settings_service tests.test_auth_service tests.test_market_service`: OK.

### Phase 7 - Amincissement des pages courses et du panneau admin races/bets
- creation de `services/race_page_service.py` pour sortir de `routes/race.py` la construction des contextes de:
  - `/courses`;
  - `/paris`;
- creation de `services/admin_race_service.py` pour centraliser:
  - le contexte de `/admin/races`;
  - la sauvegarde de la configuration courses/marche/themes/PNJ;
  - l'import/export CSV des PNJ;
  - le `force race`;
  - l'annulation de course avec remboursement;
- creation de `services/admin_bet_service.py` pour centraliser:
  - l'affichage admin des tickets;
  - la reconciliation de masse des paris;
  - la reconciliation d'un ticket unitaire;
- ajout de `tests/test_admin_race_service.py`.

Verification locale:
- `python3 -m py_compile routes/admin.py services/admin_bet_service.py services/admin_race_service.py routes/race.py services/race_page_service.py tests/test_admin_race_service.py`: OK;
- `./.venv/bin/python -m unittest tests.test_admin_race_service tests.test_admin_user_service tests.test_admin_settings_service tests.test_auth_service tests.test_market_service`: OK.

### Phase 6 - Amincissement des blueprints auth, market, main et admin
- creation de `services/auth_service.py` pour sortir de `routes/auth.py`:
  - inscription;
  - login;
  - magic links;
  - changement de mot de passe;
- creation de `services/market_service.py` pour centraliser:
  - les surencheres;
  - la mise en vente des cochons;
  - les deplacements de la Bourse;
- creation initiale de `services/main_page_service.py` pour deplacer la construction des contextes lourds de:
  - l'accueil;
  - l'historique;
  - la page `/regles`;
  - la page `/classement`;
- creation de `services/admin_user_service.py` et `services/admin_settings_service.py` pour sortir une premiere partie de `routes/admin.py`:
  - droits admin;
  - reset mot de passe;
  - generation de token magic link;
  - ajustement de solde;
  - sauvegarde des reglages cochons;
  - validation/sauvegarde du JSON moteur de course;
  - sauvegarde des reglages Bourse;
- ajout de tests unitaires de service:
  - `tests/test_auth_service.py`;
  - `tests/test_market_service.py`;
  - `tests/test_admin_user_service.py`;
  - `tests/test_admin_settings_service.py`.

Verification locale:
- `python3 -m py_compile` sur les routes/services modifies: OK;
- `create_app('testing')`: OK;
- `./.venv/bin/python -m unittest tests.test_admin_user_service tests.test_admin_settings_service tests.test_auth_service tests.test_market_service`: OK.

### Phase 5 - Nettoyage du point d'entree, service paris et package models
- extraction des seeders et commandes CLI hors de `app.py` vers `cli/seeders.py`;
- ajout d'une configuration applicative a base de classes dans `config/app_config.py`;
- creation de `services/bet_service.py` pour deplacer la logique metier de `/bet` hors du blueprint;
- centralisation des constantes de verrouillage courses/paris dans `config/game_rules.py`;
- decoupage du monolithe `models.py` en package `models/` par domaine, avec re-export de compatibilite dans `models/__init__.py`;
- ajout d'un premier test de service pour les paris dans `tests/test_bet_service.py`.

Verification locale:
- `python3 -m py_compile` sur les fichiers modifies: OK;
- `./.venv/bin/python -m unittest tests.test_bet_service`: OK;
- creation de `create_app('testing')`: OK.

### Phase 4 - Achat et consommation de nourriture decouples
- ajout du modele `UserCerealInventory` pour stocker les cereales par joueur;
- la **Bourse aux Grains** devient l'unique point d'achat des cereales;
- `Mon Cochon` consomme maintenant le stock existant sans transaction financiere;
- ajout de services d'inventaire dans `services/pig_service.py`:
  - consultation du stock;
  - ajout de cereales au stock;
  - consommation du stock lors du nourrissage;
- simplification des routes `routes/bourse.py` et `routes/pig.py` autour des services;
- mise a jour des templates:
  - suppression du selecteur de cochon sur `/bourse`;
  - affichage du stock dans `Mon Cochon`;
  - etat `Rupture de stock` avec lien vers `/bourse`.

Commit:
- `a4f3d82` - `Separate cereal purchase from feeding`

### Phase 3 - Thin controllers pour les routes cochons
- refactor des routes `/feed`, `/train`, `/school`, `/challenge-mort`;
- gestion des erreurs par exceptions metier capturees dans les blueprints;
- orchestration metier deplacee vers `services/pig_service.py`.

Commit:
- `ae7246c` - `Refactor pig routes into thin controllers`

### Phase 2 - Centralisation des regles de gameplay
- creation de `config/game_rules.py`;
- remplacement des magic numbers principaux dans `models.py` et `services/pig_service.py`;
- clarification des formules de poids, puissance et seuils Tamagotchi.

Commit:
- `d60cfbc` - `Centralize pig gameplay rules`

### Phase 1 - Modeles anemiques et decouplage critique
- extraction de la logique metier hors de `models.py`;
- centralisation des exceptions dans `exceptions.py`;
- deplacement des actions finance et cochon vers les services dedies.

Commit:
- `628f9ee` - `Refactor models into thin SQLAlchemy DAOs`
