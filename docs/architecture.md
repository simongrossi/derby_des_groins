# 🐷 Derby des Groins - Architecture du Projet

## Technologies Utilisées
- **Backend**: Python 3.x, Flask (Blueprint Based)
- **Base de données**: SQLite avec SQLAlchemy via Flask-SQLAlchemy
- **Scheduler**: APScheduler pour les tâches de fond (simulations de courses, mise à jour des stats Tamagotchi, clôture des enchères, délais vétérinaires)
- **Frontend**: HTML5, Jinja2, Tailwind CSS (CDN), Chart.js
- **API Temps-RÉEL**: Endpoints JSON pour les countdowns, les flux de résultats et l'état détaillé des cochons.

## Structure des Modèles (Database Schema)

1.  **`GameConfig`** : Stocke les paramètres globaux (horaires de courses, ouverture du marché, seuils d'aide d'urgence).
2.  **`User`** : Profil utilisateur, authentification (bcrypt), solde BitGroins (BG), statut admin et le bonus cumulé d'héritage (**`barn_heritage_bonus`**).
3.  **`Pig`** : Cœur du jeu.
    *   **Stats & Tamagotchi** : Faim, énergie, bonheur, poids, rareté, statistiques de course.
    *   **Généalogie** : Lignée (`lineage_name`), génération, parents (`sire_id`, `dam_id`), bonus de lignée.
    *   **Cycle de vie** : Retraite au haras (`retired_into_heritage`), abattoir (cimetière), mortalité.
    *   **Santé** : Blessures (`is_injured`), risque de blessure, deadline vétérinaire.
4.  **`CoursePlan`** : Système de planification permettant aux joueurs d'inscrire leurs cochons sur des créneaux futurs (respectant les quotas hebdo).
5.  **`Race`** : Sessions de courses planifiées ou terminées, incluant le statut de clôture et le vainqueur.
6.  **`Participant`** : Liaison entre un cochon (Joueur ou PNJ) et une course, incluant les cotes calculées et le résultat final.
7.  **`Bet`** : Paris des utilisateurs (Simple, Couplé Ordre, Tiercé Ordre) avec gestion des statuts de gain.
8.  **`BalanceTransaction`** : Journal comptable complet de chaque BitGroin dépensé ou gagné (traçabilité totale).
9.  **`Auction`** : Marché aux enchères temporisées pour l'achat/vente de cochons entre joueurs.
10. **`GrainMarket`** : Singleton partagé de la Bourse aux Grains. Stocke la position du curseur (cursor_x, cursor_y) sur la grille 5x5, le grain actuellement en vitrine (bloqué), et les métadonnées de la dernière transaction.

## Mécaniques Principales

- **Système Tamagotchi Dynamique** : Les stats (faim, énergie, bonheur) évoluent en temps réel selon le passage du temps (via `update_pig_state`).
- **Poids de Forme & Puissance** : 
    *   Chaque cochon a un **poids idéal** calculé selon ses statistiques (Force/Endurance vs Agilité).
    *   Le **delta de poids** (Trop lourd / Trop léger) modifie dynamiquement la vitesse réelle en course et peut augmenter le risque de blessure.
    *   La **Puissance** (`calculate_pig_power`) synthétise toutes les stats, l'état Tamagotchi et le poids.
- **Généalogie & Reproduction** :
    *   Possibilité de faire se reproduire deux cochons pour créer un descendant héritant d'une partie des statistiques.
    *   **Héritage** : Un cochon performant peut être mis à la retraite au haras, accordant un bonus de lignée permanent (`lineage_boost`) à ses descendants et à l'étable du joueur.
- **Planification & Courses** :
    *   Vue hebdomadaire permettant d'occuper les slots de courses.
    *   **Types de Courses** : Thématiques quotidiennes (Marathon le mercredi, Finale le vendredi) avec des caractéristiques et récompenses variées.
- **Économie & PMU** : 
    *   Tickets Bacon hebdomadaires pour limiter les risques.
    *   Cotes dynamiques basées sur les probabilités de victoire réelles (Calcul PMU).
    *   Marché aux enchères ouvert périodiquement avec système de surenchère.
- **Récupération Vétérinaire** : Mini-jeu (puzzle de soin) pour soigner un cochon blessé avant la deadline, sous peine de séquelles ou de mort.

## Arborescence du Projet

```text
derby_des_groins/
├── app.py                  # Initialisation Flask et migrations légères
├── models.py               # Définition de tous les modèles SQLAlchemy
├── extensions.py           # Instance db shared pour éviter les cycles
├── helpers.py              # Logique métier : calcul power, reproduction, PMU, transactions
├── data.py                 # Constantes du monde, echeanciers, types de courses
├── scheduler.py            # Configuration APScheduler (tâches cron)
├── routes/                 # Modules de routage par fonctionnalité
│   ├── auth.py             # Login / Logout / Inscription
│   ├── main.py             # Index, Classement, Historique, Légendes
│   ├── pig.py              # Gestion tamagotchi, nutrition, entraînement, reproduction
│   ├── bourse.py           # Bourse aux Grains (marché dynamique, grille, vitrine)
│   ├── race.py             # Calendrier, planification, visualisation des courses
│   ├── market.py           # Enchères et transactions de cochons
│   ├── abattoir.py         # Hall des cochons morts / cimetière
│   ├── admin.py            # Outils de gestion pour le maître du jeu
│   └── api.py              # Endpoints JSON pour l'UI dynamique
├── templates/              # Vues Jinja2 (v3.0 UI Responsive)
└── instance/               # Données locales SQLite
```

## Routes Importantes (Blueprints)
- `/` : Dashboard central et guichet des paris.
- `/pig/...` : Gestion des cochons (nutrition, entraînement, reproduction, étable).
- `/race/...` : Calendrier et suivi des courses en direct.
- `/market` : Accès aux ventes aux enchères.
- `/bourse` : Bourse aux Grains — marché dynamique de céréales avec grille de cotation partagée.
- `/classement` : Ranking global des éleveurs et trophées.
- `/history` : Journal complet des BitGroins et archives des courses.
- `/abattoir` : Hommage aux cochons disparus.

## Choix de Design
L'esthétique repose sur un **"Premium Dark Mode"** avec des accents vibrants. L'UI utilise massivement Tailwind CSS pour la réactivité et Chart.js pour visualiser les statistiques de performance des cochons.

## Roadmap Future
- **PMU Porcin Evolué** : Statistiques globales sur les cotes les plus rentables et tendances de gains.
- **Webhooks & Alertes** : Notifications pour les fins d'enchères ou les résultats de courses majeures.
- **Saisons & Ligues** : Mise en place de championnats par divisions avec remise des prix saisonnière.
