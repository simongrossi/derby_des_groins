# 🐷 Derby des Groins - Architecture du Projet

## Technologies Utilisées
- **Backend**: Python 3.x, Flask (Blueprint Based)
- **Base de données**: PostgreSQL (Docker) / SQLite (dev local) via Flask-SQLAlchemy
- **Sessions**: Flask-Session côté serveur (SQLAlchemy/PostgreSQL, table `flask_sessions`, TTL 30 jours)
- **Scheduler**: APScheduler pour les tâches de fond (simulations de courses, mise à jour des stats Tamagotchi, clôture des enchères, délais vétérinaires)
- **Frontend**: HTML5, Jinja2, Tailwind CSS (CDN), Chart.js
- **API Temps-RÉEL**: Endpoints JSON pour les countdowns, les flux de résultats et l'état détaillé des cochons.

## Structure des Modèles (Database Schema)

1.  **`GameConfig`** : Stocke les paramètres globaux (horaires de courses, ouverture du marché, seuils d'aide d'urgence, réglages d'économie, house edge et multiplicateurs journaliers).
2.  **`User`** : Profil utilisateur, authentification (bcrypt), solde BitGroins (🪙), statut admin, le bonus cumulé d'héritage (**`barn_heritage_bonus`**) et la date de dernière prime journalière (**`last_daily_reward_at`**).
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
10. **`GrainMarket`** : Singleton partagé de la Bourse aux Grains. Stocke la position du curseur (cursor_x, cursor_y) sur la grille 7x7, le grain actuellement en vitrine (bloqué), et les métadonnées de la dernière transaction.
11. **`Shop` & `Item`** : Modèles de base pour la Galerie Lard-chande (nom de la boutique, items vendables avec leur coût double-monnaie et effet).
12. **`InventoryItem`** : Modèle de la possession d'objets des joueurs avec la quantité de chacun d'eux.
13. **`MarketplaceListing`** : Représente une annonce entre joueurs dans Le Bon Groin pour vendre leurs objets inventoriés.

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
    *   Paramètres d'économie pilotables depuis **`/admin/economy`** avec persistance en base.
    *   Simulation admin basée sur les chiffres live pour estimer l'inflation et les sinks.
    *   Marché aux enchères ouvert périodiquement avec système de surenchère.
- **Récupération Vétérinaire** : Mini-jeu (puzzle de soin) pour soigner un cochon blessé avant la deadline, sous peine de séquelles ou de mort.

## Arborescence du Projet

```text
derby_des_groins/
├── app.py                  # Initialisation Flask, Flask-Session et migrations légères
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
│   ├── galerie.py          # Galerie Lard-chande & marketplace Le Bon Groin
│   ├── race.py             # Calendrier, planification, visualisation des courses
│   ├── market.py           # Enchères et transactions de cochons
│   ├── abattoir.py         # Hall des cochons morts / cimetière
│   ├── admin.py            # Panneau admin complet (dashboard, economie, races, users, SMTP...)
│   ├── blackjack.py        # Mini-jeu Groin Jack (blackjack porcin)
│   ├── truffes.py          # Mini-jeu Jeu des Truffes (cherche-truffe)
│   ├── agenda.py           # Mini-jeu La Légende du COMOP (réflexe calendrier)
│   └── api.py              # Endpoints JSON pour l'UI dynamique + replay course
├── services/               # Couche métier dédiée
│   ├── economy_service.py  # Réglages d'équilibrage, snapshots live et simulateur
│   └── ...
├── templates/              # Vues Jinja2 (v3.0 UI Responsive)
│   ├── admin_base.html     # Layout admin partagé (sidebar + nav mobile)
│   ├── admin_dashboard.html # Stats globales, économie, actions rapides
│   ├── admin_economy.html  # Réglages d'économie + simulateur + analyses
│   ├── admin_races.html    # Planning courses, marché, forcer/annuler
│   ├── admin_pigs.html     # Filtres cochons, soigner, tuer/réanimer
│   ├── admin_users.html    # Gestion joueurs, mdp, admin, liens magiques, solde
│   ├── admin_events.html   # Événements globaux
│   ├── admin_notifications.html # Config SMTP + test email
│   ├── admin_data.html     # CRUD céréales/entraînements/leçons
│   └── admin_data_form.html # Éditeur d'item universel
└── instance/               # Données locales SQLite
```

## Routes Importantes (Blueprints)
- `/` : Dashboard central et guichet des paris.
- `/pig/...` : Gestion des cochons (nutrition, entraînement, reproduction, étable).
- `/race/...` : Calendrier et suivi des courses en direct.
- `/galerie-lard-chande/...` : La Galerie Lard-chande, ses 5 magasins.
- `/le-bon-groin/...` : La marketplace P2P des différents objets.
- `/market` : Accès aux ventes aux enchères.
- `/bourse` : Bourse aux Grains — marché dynamique de céréales avec grille de cotation partagée.
- `/classement` : Ranking global des éleveurs et trophées.
- `/history` : Journal complet des BitGroins et archives des courses.
- `/abattoir` : Hommage aux cochons disparus.
- `/blackjack` : Mini-jeu Groin Jack — blackjack porcin avec mise en BitGroins.
- `/truffes` : Mini-jeu Jeu des Truffes — cherche-truffe sur grille 20×20.
- `/agenda` : Mini-jeu La Légende du COMOP — réflexe calendrier Porc-Look (50 🪙).
- `/race/live` : Replay animé de la dernière course tour par tour.
- `/auth/magic/<token>` : Connexion par lien magique (généré par l'admin, expire 24h).
- `/admin/dashboard` : Vue d'ensemble admin (stats, économie, actions rapides).
- `/admin/economy` : Réglage des rewards, coûts, quotas, tickets, caps de payout et simulation live.
- `/admin/races` : Planning des courses, marché, forcer/annuler des courses.
- `/admin/pigs` : Gestion cochons avec filtres, soins, tuer/réanimer.
- `/admin/users` : Gestion avancée des joueurs (mdp, admin, solde, liens magiques).
- `/admin/events` : Événements globaux (nourriture, véto, bonus).
- `/admin/notifications` : Configuration SMTP et test d'envoi d'emails.
- `/admin/data` : CRUD des données de jeu (céréales, entraînements, leçons).

## Choix de Design
L'esthétique repose sur un **"Premium Dark Mode"** avec des accents vibrants. L'UI utilise massivement Tailwind CSS pour la réactivité et Chart.js pour visualiser les statistiques de performance des cochons.

### Contraintes templates obligatoires
Chaque template de page complète (hors partials `_*.html`, pages d'erreur et layouts fullscreen type `race_circuit.html`) **doit** inclure :
- `{% include '_site_header.html' %}` en haut du `<body>` (navigation principale)
- `{% include '_footer.html' %}` juste avant `</body>` (footer partagé avec liens et copyright)
- `{% include '_flash.html' %}` pour les messages flash si la page utilise des formulaires ou des actions

Les pages exemptées de footer : `429.html` (erreur), `auth.html` (login/register), `admin_base.html` (layout admin séparé), `race_circuit.html` (plein écran SVG).

## Équilibrage v2
- **Progression nerfée** : les gains de stats par entraînement et école ont été divisés par 5 (anti-snowball).
- **Durée de vie réduite** : les `max_races_range` ont été divisées par 2 pour accélérer le turnover.
- **Prime de pointage** : 15 🪙 automatiques à la première connexion de chaque jour (`DAILY_LOGIN_REWARD`).
- **Moteur de course** : récupération de fatigue en stratégie Économie nerfée (0.5 → 0.1), bonus d'aspiration réduit (1.5 → 0.8).
- **Admin Economie** : la plupart des variables monétaires et PMU sont désormais ajustables sans déploiement, avec un simulateur pour projeter la circulation.

## Roadmap Future
- **PMU Porcin Evolué** : Statistiques globales sur les cotes les plus rentables et tendances de gains.
- **Webhooks & Alertes** : ✅ Config SMTP en place. Reste : notifications automatiques (résultats de courses, fins d'enchères), intégration Slack/Teams.
- **Saisons & Ligues** : Mise en place de championnats par divisions avec remise des prix saisonnière.
