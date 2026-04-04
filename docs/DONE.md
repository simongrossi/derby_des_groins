# DONE - Derby des Groins

Liste des fonctionnalités et idées déjà implémentées dans le projet.

> Note: pour les règles réellement actives et les réglages joueurs à jour, la référence n'est plus ce fichier mais [docs/regles_du_jeu.md](/D:/Programmation/derby_des_groins/docs/regles_du_jeu.md) et la page `/regles`.

## Architecture et découplage
- **Découplage critique des modèles** : les modèles SQLAlchemy ont été découpés dans un package `models/` par domaine (`user.py`, `pig.py`, `race.py`, etc.) avec un `models/__init__.py` de compatibilité.
- **Services métier extraits** : la logique de `User.pay()` / `User.earn()` / prime journalière vit désormais dans `services/finance_service.py`, et les actions `Pig.feed()` / `Pig.train()` / `Pig.study()` / vitals / mort / retraite dans `services/pig_service.py`.
- **Exceptions métier partagées** : un nouveau fichier `exceptions.py` centralise les erreurs métier comme `InsufficientFundsError`, `PigTiredError`, `UserNotFoundError` et `PigNotFoundError`.
- **Routes rebranchées** : les blueprints et helpers appellent maintenant explicitement les services, ce qui supprime les imports locaux dans les modèles et réduit les risques de dépendances circulaires.
- **Inventaire de céréales** : nouveau modèle `UserCerealInventory` pour séparer l'achat des grains (Bourse) de leur consommation (Mon Cochon).
- **Factory Flask nettoyée** : `app.py` s'appuie désormais sur `config/app_config.py` pour la configuration d'environnement, et les seeders/commandes CLI vivent dans `cli/seeders.py`.
- **Service de paris dédié** : la création des tickets PMU est maintenant centralisée dans `services/bet_service.py`, avec une route `/bet` allégée.
- **Auth et marché sortis des routes** : `services/auth_service.py` gère maintenant inscription, login, mot de passe et magic links, tandis que `services/market_service.py` porte les bids, ventes de cochons et déplacements Bourse.
- **Pages principales allégées** : les contextes lourds de l'accueil, de l'historique, des règles et du classement sont désormais assemblés dans `services/main_page_service.py`.
- **Admin commencé côté services** : `services/admin_user_service.py` et `services/admin_settings_service.py` prennent en charge une partie des actions admin utilisateurs et réglages pour réduire `routes/admin.py`.
- **Routes courses/admin encore amincies** : `services/race_page_service.py`, `services/admin_race_service.py` et `services/admin_bet_service.py` portent maintenant une partie des contextes lourds et actions admin liées aux courses, PNJ et tickets.
- **Panneau admin largement sorti en services** : les actions admin cochons, événements, notifications SMTP, réglages Truffes, CRUD des données de jeu et gestion des avatars délèguent désormais à `services/admin_pig_service.py`, `services/admin_event_service.py`, `services/admin_notification_service.py`, `services/admin_truffes_service.py`, `services/admin_game_data_service.py` et `services/admin_avatar_service.py`.
- **Validations admin homogénéisées** : les erreurs de parsing et de validation côté admin remontent maintenant via `ValidationError` / `BusinessRuleError` au lieu de branches inline et `ValueError` bruts dans `routes/admin.py`.

## Gestion des Courses
- **Gestion des courses vides / sous-peuplées** : Mise en place d'une règle configurable (`min_real_participants`) pour remplir automatiquement les courses avec des bots ou les annuler.
- **Remboursement automatique** : Les paris sur les courses annulées sont désormais automatiquement remboursés aux utilisateurs.
- **Scaling des Bots** : Les bots ajoutés aux courses s'adaptent désormais au niveau moyen des participants réels (90% à 110% de la puissance moyenne).

## Poids et Stratégie
- **Système de poids tactique** : Le poids influence désormais dynamiquement les statistiques de Force et d'Agilité.
    - **Surnourri** : Gain de Force (effet bulldozer) mais perte massive d'Agilité.
    - **Sous-poids** : Gain d'Agilité (très vif) mais perte de Force (manque d'impact).
- **Indicateurs visuels** : Affichage explicite des modificateurs de stats sur le tableau de bord et la page du cochon.

## Reproduction et Héritage
- **Système de reproduction** : Deux cochons actifs peuvent lancer une portée pour générer un porcelet.
- **Hérédité** : Les porcelets héritent partiellement des statistiques, de la rareté et de l'origine de leurs parents.
- **Retraite d'honneur & Héritage permanent** : Les cochons légendaires ou victorieux peuvent être mis à la retraite pour booster l'héritage de la porcherie et renforcer leur lignée.
- **Pression de nourrissage** : Le coût des céréales augmente avec le nombre de cochons dans la porcherie (+20% par cochon supplémentaire) pour équilibrer la progression.

## Bourse aux Grains (Marche dynamique)
- **Grille de cotation 7x7** : un bloc 3x3 partage entre tous les joueurs determine le prix des grains selon sa position sur la grille.
- **Points de mouvement** : chaque joueur accumule des points en achetant (1 pt / 10 achats) et peut deplacer le curseur pour influencer les prix.
- **Vitrine anti-spam** : le dernier grain achete est bloque pour tous jusqu'a ce qu'un autre grain soit achete, forcant la variete.
- **Prix dynamiques** : le cout final combine le modificateur Bourse, la pression de porcherie et le cout de base.
- **Qualite variable** : les bonus de faim, energie et stats sont multiplies par le modificateur de qualite de la grille.
- **Achat decouple de la consommation** : la Bourse est maintenant l'unique point d'achat des cereales, qui sont ajoutees a un stock joueur avant d'etre consommees plus tard.
- **Interface dediee** (`/bourse`) : grille visuelle, controles directionnels, cartes de cereales avec prix ajustes et achat pour stock global.
- **Modele GrainMarket** : singleton en base pour stocker l'etat partage du marche.

## Mon Cochon et alimentation
- **Consommation sur stock** : l'onglet nourrir de `Mon Cochon` ne facture plus directement. Il consomme `1` unite de cereal en stock.
- **Retour de stock en UI** : chaque cereale affiche maintenant la quantite disponible, avec etat `Rupture de stock` et lien vers `/bourse` si necessaire.

## Transparence joueur
- **Hub `Regles`** : une page publique `/regles` centralise maintenant les règles, jauges, paris, économie, Bourse, marché et mini-jeux.
- **Liens contextuels** : `Mon Cochon`, `Paris` et `Bourse` pointent vers les sections utiles du hub pour éviter les règles cachées.
- **Documentation alignée** : `README.md`, `docs/regles_du_jeu.md` et `docs/transparence_joueur.md` ont été mis à plat pour suivre les réglages actifs.

## Classement enrichi
- **5 onglets** : General, Abattoir & Cimetiere, Paris & Fortune, Elevage & Ecole, Mur de la Honte.
- **Palmares complet** : 18+ awards automatiques (Roi du Derby, Boucher en Chef, Kamikaze Supreme, Le Pigeon, etc.).
- **Charts supplementaires** : morts empilees par cause, donut des causes de deces, profit/perte paris, taux de reussite, courses disputees, win rate.
- **Mur de la Honte** : classements des pires performances (looser, boucher, pigeon, negligent, flambeur, rat fauche, gaveur).

## Équilibrage économique et progression (v2)
- **Nerf progression stats** : tous les gains de stats (entraînements et école) divisés par 5 pour éviter l'effet boule de neige. Un sprint donne +0.6 VIT (avant : +3.0), un cours de stratégie donne +0.5 INT (avant : +2.5).
- **Durée de vie réduite** : les `max_races_range` des cochons sont divisées par 2 pour accélérer le turnover et dynamiser l'économie.
  - Commun : 20-30 courses (avant : 40-60)
  - Rare : 30-40 courses (avant : 60-80)
  - Épique : 40-50 courses (avant : 80-100)
  - Légendaire : 50-75 courses (avant : 100-150)
- **Prime de pointage journalière** : +15 🪙 automatiques à la première connexion de la journée. Garantit un revenu minimum pour nourrir ses cochons sans dépendre de l'aide d'urgence.
- **Moteur de course rééquilibré** :
  - Récupération de fatigue en stratégie Économie (strat < 25) nerfée : de -0.5 à -0.1 par tour.
  - Bonus d'aspiration (drafting) réduit : de +1.5 à +0.8, pour éviter que les cochons endurants en Économie dominent systématiquement.

## Anti-farm et équité hardcore/casual (v3 — avril 2026)

Corrections de failles économiques majeures identifiées par simulation (voir `docs/IDEAS.md` section "Équilibrage Hardcore vs Casuals").

### Cochon Pendu limité
- **3 parties gratuites par joueur par jour**, puis 5 🪙 par partie supplémentaire.
- Avant : illimité, permettant ~1 200 🪙/heure (soit 1 semaine de courses en 1h).
- Fichiers : `routes/cochon_pendu.py`, `models.py` (`User.pendu_plays_today` + `User.last_pendu_at`).

### Cap quotidien d'entraînement
- **10 sessions par cochon par jour** (toutes disciplines confondues), avec alerte visuelle sous les 3 sessions restantes.
- Avant : illimité, permettant +24 VIT/jour avec refeed en boucle (ratio ×140 sur 30 jours vs casual).
- Fichiers : `routes/pig.py`, `models.py` (`Pig.daily_train_count` + `Pig.last_train_date`).

### Rendement décroissant à l'école
- Sessions 1–2 : 100% XP/stats ; session 3 : 50% ; sessions 4+ : 10%.
- Réduit le ratio XP école de ×24 à ×3.3 entre hardcore et casual.
- Fichiers : `models.py` (`Pig.study()`, `Pig._school_decay_multiplier()`), `data.py` (`SCHOOL_XP_DECAY_THRESHOLDS`).

### Comeback Bonus / Rested XP activé
- Seuil abaissé de 3 jours → **12 heures** d'inactivité pour déclencher `comeback_bonus_ready = True`.
- Sur la prochaine **victoire** avec le flag actif : ×2 XP, ×2 gains de stats, +10 bonheur.
- Avant : le flag était positionné mais les bonus ×2 n'étaient pas appliqués sur victoire (juste un trophée).
- Fichiers : `models.py` (`register_positive_interaction()`), `helpers/race.py`.

### Taxe progressive sur les crédits
- Solde > 2 000 🪙 → 20% de taxe sur chaque gain ; > 5 000 🪙 → 50%.
- Revenus de base exempts : prime quotidienne, secours d'urgence, remboursement portée.
- Fichiers : `services/finance_service.py` (`credit_user_balance()`), `data.py` (`TAX_THRESHOLD_*`, `TAX_RATE_*`).

### Caisse de Solidarité Porcine
- Les BitGroins taxés alimentent une cagnotte commune (`GameConfig.solidarity_fund`).
- Redistribution automatique de 30 🪙 aux joueurs tombant sous 50 🪙 (priorité sur l'emergency_relief de 20 🪙).
- Fichiers : `services/finance_service.py` (`maybe_grant_solidarity_relief()`).

### Plafond casino journalier
- **500 🪙 de gains nets maximum par joueur par jour** depuis le Blackjack et le Poker.
- Au-delà, les crédits casino sont suspendus jusqu'au lendemain.
- Fichiers : `services/finance_service.py` (`_apply_casino_cap()`), `models.py` (`User.daily_casino_wins` + `User.last_casino_date`).

## Mini-Jeux

### Groin Jack (`/blackjack`)
- Blackjack porcin jouable avec les BitGroins (mise 5–500 🪙).
- Deck 52 cartes + 2 Jokers avec effets aléatoires (carte bonus, perturbation croupier).
- Actions : Hit, Stand, Double (disponible uniquement sur la première main à 2 cartes).
- Blackjack naturel payé 3:2. Victoire = x2 mise. Égalité = remboursement intégral.
- Mise débitée à l'ouverture, gain/remboursement crédité via `finance_service`.

### Jeu des Truffes (`/truffes`)
- Mini-jeu de cherche-truffe sur grille 20×20.
- 7 clics maximum pour trouver la truffe cachée.
- Récompense en cas de succès : 20 🪙 crédités automatiquement.
- Sans mise, utilisable comme revenu d'appoint gratuit.

### La Légende du COMOP (`/agenda`)
- Mini-jeu réflexe sur un calendrier Porc-Look parodiant Outlook.
- Le Chef de Porc-jet (PDG adjoint) programme des COMOPs fantômes qui fuient le curseur de la souris.
- Quand la souris s'approche à moins de 60px, le COMOP se téléporte sur un autre créneau et le Chef envoie une notification Teams absurde ("On décale ! Faut qu'on soit plus Agi-Lards", "ASAP = As Swine As Possible", etc.).
- Toutes les 3-6 secondes, le COMOP se fige 0.5s (passe en doré) : fenêtre pour cliquer dessus.
- Piège "VRAI TRAVAIL" : des blocs verts apparaissent ; cliquer dessus fait perdre 2 secondes et déclenche une sanction du Chef de Porc-jet.
- Objectif : attraper 5 COMOPs en 30 secondes.
- Victoire : Erreur 404 "Illusion de Management" — le COMOP n'a jamais existé. Récompense : 50 🪙 + trophée "Ceinture Noire de Porc-Look".
- Cooldown : 1 partie par jour.
- Jeux de mots intégrés : Groin-storming, Point de Syn-Goret, Co-Porc, Stand-up de la Bauge, Bilan Lard-do, Porc-folio Manager, méthode Agi-Lard.

### Course en Direct (`/race/live`)
- Replay animé tour par tour de la dernière course terminée.
- Visualisation des positions, accélérations, drafting, fatigue et accrocs.
- Classement live mis à jour à chaque tour avec barre de progression globale.
- Données servies via un nouvel endpoint JSON dans `api.py`.

## Interface Admin v3
- **Tableau de bord complet** : Vue d'ensemble des statistiques vitales (utilisateurs, cochons en vie, courses terminées, masse monétaire totale/moyenne, paris en attente).
- **Panneau Économie** (`/admin/economy`) :
  - Réglage centralisé des récompenses, coûts, quotas, tickets, limites de mise, cap de payout et `house_edge` par type de pari.
  - Multiplicateurs journaliers éditables directement depuis l'admin.
  - Simulateur branché sur les données live de la base (circulation, paris récents, taille de champ, capacité hebdo, coûts de céréales).
  - Matrice de profils types, scénarios de distribution, analyse des tickets et résumé des mouvements récents.
  - Valeurs persistées via `GameConfig` puis réellement réutilisées par le runtime du jeu (inscription, récompenses, quotas, coûts et PMU).
- **Gestion des Courses** :
    - Interface de planification hebdomadaire avancée.
    - Contrôle granulaire des paramètres (heure des courses, durée de la bourse, seuils de participants).
    - Bouton "Force Race" pour déclencher une course immédiatement.
    - Annulation de course sécurisée avec remboursement automatique des parieurs.
    - Les contextes lourds de l'accueil, de l'historique, des règles et du classement ont été sortis du blueprint principal vers `services/main_page_service.py`.
    - Les pages `/courses`, `/paris` et plusieurs actions de `/admin/races` délèguent maintenant leurs contextes et opérations à des services dédiés.
- **Gestion des Joueurs** :
    - Ajustement manuel des soldes (BitGroins) avec journalisation.
    - Promotion/Rétrogradation des administrateurs.
    - Réinitialisation de mot de passe et génération de **Liens Magiques** (connexion sécurisée par token de 24h).
    - Une partie de ces actions est maintenant servie par `services/admin_user_service.py` au lieu d'être codée inline dans `routes/admin.py`.
- **Audit des Paris admin** :
    - La consultation et la réconciliation des tickets admin passent désormais par `services/admin_bet_service.py`.
- **Gestion des Cochons** : Liste complète avec filtres de vie, fonctions de résurrection/mise à mort administrative et soin immédiat (bouton Heal).
- **Événements Globaux** : Déclenchement manuel de bonus (pluie de nourriture, visite vétérinaire générale, bonus BitGroins pour tous).
- **Configuration SMTP** : Panneau de réglage pour l'envoi d'emails (notifications, liens magiques) avec test d'envoi en direct.
- **Éditeur de Données (CRUD)** : Interface complète pour ajouter, modifier ou désactiver les Céréales, Entraînements, Leçons d'école et mots du pendu sans toucher au code ni à la base de données brute.
- **Gestion des avatars** : Upload, édition SVG et suppression des avatars directement depuis l'admin avec validations centralisées côté service.
- **Seeding Automatique** : Migration automatique des données statiques (`data.py`) vers la base de données au premier lancement pour une flexibilité totale.

## Audit des Paris et Performance (v2.1)
- **Restriction paris complexes** : Les paris a 3+ selections (tierce, quarte, quinte, rafle) necessitent que le cochon du joueur participe a la course.
- **Limites de mise** : Minimum 5 BitGroins, maximum 500 BitGroins par pari (`MIN_BET_RACE`, `MAX_BET_RACE`).
- **Correction du calcul de cotes** : Suppression d'une fonction `calculate_bet_odds` dupliquee dans `helpers.py` qui omettait le facteur factoriel pour les paris non ordonnes, gonflant les cotes jusqu'a 122x. Une seule source de verite dans `race_service.py`.
- **Reequilibrage des marges** : quarte 1.30 -> 1.18, quinte 1.35 -> 1.15, two_of_four 1.15 -> 1.10, rafle differenciee du quinte (order_matters=True, house_edge=1.45).
- **Performance page d'accueil** : Reecriture de `build_course_schedule()` pour remplacer le pattern N+1 (10 962 appels SQL) par des requetes batch (~4 requetes). Temps de reponse : 19.3s -> 0.83s.
- **Stabilite QueuePool** : Configuration du pool SQLAlchemy (pool_size=10, max_overflow=20, pool_recycle=300), ajout teardown_appcontext, limitation a 3 courses par tick du scheduler.
- **Fix admin** : Correction du TypeError sur `/admin` lors du tri des participants avec `finish_position=None`.

## Achats et Équipements
- **La Galerie Lard-chande** (`/galerie-lard-chande`) : Hub d'achats réunissant 5 boutiques thématiques pour vos cochons (sport, pop-culture, soin esthétique, etc.).
- **Double Monnaie** : Les objets peuvent s'acheter soit en BitGroins réguliers (Glands), soit avec des Truffes.
- **Système de Fiabilité** : Chaque objet a un niveau de fiabilité permettant l'ajout d'objets surpuissants mais très risqués (ex: chez AliGoret).
- **Le Bon Groin** (`/le-bon-groin`) : Une plateforme de petites annonces Player-to-Player (P2P) pour vendre ses objets d'inventaire dont on ne se sert plus.

## UX et Navigation
- **Page dédiée aux Paris** (`/paris`) : Séparation claire entre l'inscription de ses cochons (`/courses`) et la prise de tickets (paris), facilitant la vie des parieurs.
- **Ouverture anticipée des courses par les parieurs** : Depuis `/paris`, un parieur peut cliquer sur un créneau futur de l'agenda défini par l'admin qui n'a pas encore de participants. Cela génère instantanément la course en la remplissant de cochons IA (PNJ), figeant ainsi l'accès pour les vrais joueurs mais permettant les prises de paris 24/7 sur la grille officielle.
- **Protection des paris (Anti-Annulation)** : Une course avec 0 participant humain (100% IA) ne s'annulera plus (même si le mode `empty_race_mode` de l'admin est sur `cancel`), **à condition qu'au moins un pari ait été placé dessus**. L'ordinateur la courra pour résoudre les gains/pertes des parieurs.
- **Homepage allégée** : Le tableau géant de prise de paris a été remplacé par une mini-carte qui indique le statut de la prochaine course et redirige vers `/paris`.
- **Navigation Menu** : Ajout du lien direct "💰 Paris" dans la barre principale, regroupement sémantique clair (Courses -> Paris -> Mon Cochon).
