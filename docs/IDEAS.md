# IDEAS (BACKLOG)

## Priorités produit proposées

### 1. Logiques de victoire sur le long terme

- Mettre en place des **saisons** courtes (mensuelles par défaut) avec :
  - remise à zéro partielle des classements,
  - conservation des trophées, du Hall of Fame et des métriques historiques,
  - divisions / ligues pour séparer nouveaux éleveurs et vétérans.
- Renforcer l'**anti-snowball** pour éviter qu'un joueur dominant n'écrase durablement la concurrence :
  - fatigue après sorties consécutives,
  - rendements décroissants à l'entraînement,
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
  - limiter les gains bruts, spécialisations (`sprinteur`, `roublard`, `marathonien`), garder le coût moral comme vrai arbitrage.

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

1. **Grille 5x5** : positions (1,1) a (5,5). Centre (3,3) = neutre.
2. **Axe X (Prix)** : modificateurs `[0.55, 0.78, 1.00, 1.28, 1.60]`.
3. **Axe Y (Qualite)** : modificateurs `[0.55, 0.78, 1.00, 1.28, 1.60]`.
4. **Prix final** = `base_cost * price_mod * feeding_multiplier`.
5. **Qualite finale** = tous les bonus (faim, energie, stats, poids) multiplies par `quality_mod`.
6. **Points de mouvement** = `max(1, total_achats_nourriture // 10)`.
7. **Vitrine** : le grain achete en dernier est bloque jusqu'au prochain achat d'un grain different.
8. **Etat partage** : le curseur et la vitrine sont communs a tous les joueurs (modele `GrainMarket`, singleton id=1).

## Direction forte à garder

- Jeu de bureau asynchrone : planification de la semaine plutôt qu'actions répétitives.
- Permettre à un joueur de venir 5 minutes le lundi pour planifier toute sa semaine.
