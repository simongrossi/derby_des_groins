# IDEAS (BACKLOG)

## Priorités produit proposées

### 1. Logiques de victoire sur le long terme

- Mettre en place des **saisons** courtes (mensuelles par défaut) avec :
  - remise à zéro partielle des classements,
  - conservation des trophées, du Hall of Fame et des métriques historiques,
  - divisions / ligues pour séparer nouveaux éleveurs et vétérans.
- Renforcer l'**anti-snowball** pour éviter qu'un joueur dominant n'écrase durablement la concurrence :
  - ✅ gains de stats divisés par 5 (entraînement et école),
  - ✅ durée de vie des cochons divisée par 2,
  - ✅ prime de pointage journalière (15 🪙),
  - ✅ moteur de course : récupération fatigue et aspiration nerfées,
  - fatigue après sorties consécutives (à explorer),
  - rendements décroissants à l'entraînement (à explorer),
  - buffs de comeback pour les cochons frais ou les joueurs moins actifs.
- Formaliser un **Hall of Fame** saisonnier :
  - vainqueur `Saint Grouin`,
  - meilleurs éleveurs,
  - cochons les plus rentables,
  - survivants emblématiques du `Challenge de la Mort`.

## Rythme des courses

- Éviter `1 course par heure` comme règle par défaut. Garder la main côté admin sur le rythme, avec une config simple `mode calme / normal / événement`.
- Ajouter des événements ponctuels `grosse course du soir` ou `grand prix du vendredi` pour donner des rendez-vous plus mémorables.

## Convention collective de la porcherie

- Ajouter une logique de `quota hebdomadaire` type `35 heures de l'auge` : un cochon ne peut courir que `2 à 3 courses maximum par semaine`.
- Forcer l'éleveur à choisir à l'avance ses sorties importantes selon les adversaires, le jour, les bonus de course ou l'état du cochon.
- Rendre la programmation des courses plus stratégique que le simple spam de participations.
- Ajouter une lecture claire de la semaine à venir dans l'interface : jours de course, quota restant, prochaine sortie planifiée.

## Calendrier des courses

- Ajouter un vrai menu `Liste des courses` ou `Calendrier des courses`.
- Afficher les courses à venir sur la semaine et idéalement sur le mois :
  - date, type de course, règle spéciale du jour, slots disponibles, cochons déjà inscrits.
- Permettre d'inscrire son cochon à l'avance sur une ou plusieurs courses selon son quota hebdomadaire.
- Ajouter une vue `planification` :
  - quota restant pour la semaine, jours déjà réservés, alertes de fatigue, buff potentiel si le cochon se repose avant une grande course.

## Statistiques, conditions de course et équilibrage

- Donner une vraie utilité aux statistiques secondaires via des **thèmes de course** et la **météo** :
  - `Pataugeoire du Lundi` (boue) : Force et Endurance favorisées.
  - Piste sèche pour favoriser la Vitesse.
  - Formats spéciaux pour Intelligence, Agilité ou Moral.
- Revoir l'**École porcine** pour éviter le maxage trop rapide des stats :
  - ✅ gains bruts divisés par 5 (fait),
  - spécialisations (`sprinteur`, `roublard`, `marathonien`) à explorer,
  - garder le coût moral comme vrai arbitrage.

## Fatigue, porc-out et RTT

- Malus de fatigue `Sueur de Porc` si sorties consécutives.
- Malus `Fièvre Porcine` (arrêt maladie) en cas de surmenage excessif.
- Buff `Frais comme un Porcelet` après un repos de 4 à 5 jours pour aider les joueurs occasionnels.

## Bauge, absences et survie passive

- Ajouter des `Congés Porcins` (hibernation après 36-48h d'absence).
- Faire baisser la faim de base très lentement pour que la survie ne soit pas une corvée.
- Ajouter un mode `Stagiaire Ramasse-Purin` pour maintenir le minimum vital durant les vacances réelles de l'éleveur.

## Pari mutuel porcin (PMU des Groins)

- Remplacer le spam de paris par des `Tickets Bacon` limités (ex: 3 tickets par semaine redonnés le lundi).
- Ajouter une logique `Copains comme Cochons` pour encourager les pronostics collectifs sur les cochons programmés en avance.

## Blessures et vétérinaire (Plus poussé)

- Un cochon pourrait se blesser pendant une course.
- En cas de blessure grave, passage chez le vétérinaire avec un mini-jeu type `Docteur Maboul` ou puzzle d'os chronométré.

## Reproduction et lignée (Next Steps)

- Ajouter un vrai **arbre généalogique** interactif ou historique de lignée pour raconter les familles de champions.

## Semaine de la porcherie

- Donner un thème et des règles spécifiques à chaque jour :
  - Lundi : Pataugeoire (Boue/Variance/Outsiders).
  - Mardi/Jeudi : Trot du Jambon (Stabilité/Sécurité).
  - Mercredi : Marathon (Endurance/Cardio).
  - Vendredi : Grande Finale du Cochon Rôti (Gains doublés).

## Méta-jeu et communauté

- Créer un système d'**écuries / clans** pour jouer en groupe.
- Ajouter des **alertes et webhooks** vers Slack / Teams (résultats, enchères, urgences).
  - ✅ Configuration SMTP et envoi d'emails en place (admin > Notifications).
  - ✅ Liens magiques de connexion envoyés par email si SMTP configuré.
  - Reste : notifications automatiques sur événements de jeu, intégration Slack/Teams.
- Faire du trophée physique (`Le Saint Grouin`) un vrai prolongement social IRL du jeu.

## Menus et interfaces manquants

- Menu **Calendrier / Planification** interactif.
- Menu **Généalogie / Arbre généalogique**.
- Dashboard avec pronostics communautaires.
- Page de **statistiques globales** (plus gros gains, cochons les plus rentables).

## Trophées et cérémonies

- trophées de fin de mois / trimestre / année.
- Remise cérémonielle IRL lors des réunions d'équipe.

## Ton du projet

- Assumer le ton absurde et cérémoniel (titres honorifiques, folklore maison).
- Transformer les blagues internes en features cosmétiques.

## Bourse aux Grains — evolutions possibles

La Bourse aux Grains est implementee. Evolutions futures envisageables :

- **Tendances de marche** : afficher un historique des positions du curseur sur les dernieres 24h/7j.
- **Bourse a terme** : permettre de bloquer un prix a l'avance en payant une prime.
- **Crises alimentaires** : evenements aleatoires qui deplacent brutalement le curseur (secheresse, recolte exceptionnelle).
- **Lobbying porcin** : alliances entre joueurs pour deplacer le curseur ensemble (cumul de points de mouvement).
- **Speculation de vitrine** : penalite BG si le meme joueur bloque la vitrine trop souvent.
- **Qualite des terroirs** : certaines origines de cochons reagissent mieux a certains grains (synergie pays/cereale).

### Algorithme de la Bourse aux Grains

1. **Grille 7x7** : valeurs symetriques `[6, 4, 2, 0, 2, 4, 6]`. Centre (3,3) = surcout 0.
2. **Bloc 3x3 mobile** : un bloc de 3x3 cases contient les 6 cereales disposees en croix/coins. Le centre du bloc = grain de base (mais). En position initiale (centre de la grille), le mais n'a aucun surcout.
3. **Surcout** : chaque point de grille = +5% du prix de base (`BOURSE_SURCHARGE_FACTOR = 0.05`). Un grain sur la case de valeur 4 coute 20% de plus.
4. **Prix final** = `base_cost * (1 + grid_value * 0.05) * feeding_multiplier`.
5. **Points de mouvement** = `max(1, total_achats_nourriture // 10)`.
6. **Contrainte du bloc** : le centre du bloc ne peut sortir des positions 1 a 5 pour que le bloc 3x3 reste entierement dans la grille 7x7.
7. **Vitrine** : le grain achete en dernier est bloque jusqu'au prochain achat d'un grain different.
8. **Etat partage** : le curseur et la vitrine sont communs a tous les joueurs (modele `GrainMarket`, singleton id=1).

### Algorithme de l'equilibrage v2

1. **Progression stats** : tous les gains d'entrainement et d'ecole divises par 5.
2. **Duree de vie** : `max_races_range` divisee par 2 pour toutes les raretes.
3. **Prime journaliere** : `DAILY_LOGIN_REWARD = 15.0` 🪙 a la premiere connexion du jour.
4. **Moteur de course** :
   - Recuperation fatigue en strategie Economie (strat < 25) : 0.5 → 0.1 par tour.
   - Bonus d'aspiration (drafting) : 1.5 → 0.8.
   - Ces deux nerfs empechent les cochons endurants en Economie de dominer systematiquement la fin de course.

## Direction forte à garder

- Jeu de bureau asynchrone : planification de la semaine plutôt qu'actions répétitives.
- Permettre à un joueur de venir 5 minutes le lundi pour planifier toute sa semaine.
