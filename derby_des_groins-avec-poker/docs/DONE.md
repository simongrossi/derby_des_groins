# DONE - Derby des Groins

Liste des fonctionnalités et idées déjà implémentées dans le projet.

> Note: pour les règles réellement actives et les réglages joueurs à jour, la référence n'est plus ce fichier mais [docs/regles_du_jeu.md](/D:/Programmation/derby_des_groins/docs/regles_du_jeu.md) et la page `/regles`.

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
- **Interface dediee** (`/bourse`) : grille visuelle, controles directionnels, selecteur de cochon, cartes de cereales avec prix ajustes.
- **Modele GrainMarket** : singleton en base pour stocker l'etat partage du marche.

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
- **Gestion des Joueurs** :
    - Ajustement manuel des soldes (BitGroins) avec journalisation.
    - Promotion/Rétrogradation des administrateurs.
    - Réinitialisation de mot de passe et génération de **Liens Magiques** (connexion sécurisée par token de 24h).
- **Gestion des Cochons** : Liste complète avec filtres de vie, fonctions de résurrection/mise à mort administrative et soin immédiat (bouton Heal).
- **Événements Globaux** : Déclenchement manuel de bonus (pluie de nourriture, visite vétérinaire générale, bonus BitGroins pour tous).
- **Configuration SMTP** : Panneau de réglage pour l'envoi d'emails (notifications, liens magiques) avec test d'envoi en direct.
- **Éditeur de Données (CRUD)** : Interface complète pour ajouter, modifier ou désactiver les Céréales, Entraînements et Leçons d'école sans toucher au code ni à la base de données brute.
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
