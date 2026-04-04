# Release Updates

Journal compact des changements notables du projet.

Objectif:
- suivre les refactors et features livrees sans noyer `DONE.md`;
- garder une trace chronologique exploitable apres chaque phase;
- faciliter les reprises de contexte et la redaction de changelogs plus visibles plus tard.

## 2026-04-04

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
- creation de `services/main_page_service.py` pour deplacer la construction des contextes lourds de:
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
