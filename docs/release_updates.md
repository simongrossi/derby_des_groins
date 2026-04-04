# Release Updates

Journal compact des changements notables du projet.

Objectif:
- suivre les refactors et features livrees sans noyer `DONE.md`;
- garder une trace chronologique exploitable apres chaque phase;
- faciliter les reprises de contexte et la redaction de changelogs plus visibles plus tard.

## 2026-04-04

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
