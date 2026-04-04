# Release Updates

Journal compact des changements notables du projet.

Objectif:
- suivre les refactors et features livrees sans noyer `DONE.md`;
- garder une trace chronologique exploitable apres chaque phase;
- faciliter les reprises de contexte et la redaction de changelogs plus visibles plus tard.

## 2026-04-04

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
