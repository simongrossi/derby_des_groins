# 💰 Panneau Admin Économie

Cette page documente **`/admin/economy`**, le panneau d'équilibrage du jeu.

## Objectif

Le but de cette page est de permettre d'ajuster l'économie sans retoucher le code ni la base à la main, puis de **prévisualiser l'impact** sur la circulation de BitGroins avant sauvegarde.

Le panneau se base sur deux sources :
- les **réglages persistés** dans `GameConfig`
- les **chiffres live** déjà présents en base (joueurs, cochons, paris, transactions, planning, coûts de céréales)

## Ce que montre la page

En haut de la page, un **snapshot live** résume l'état courant du jeu :
- BitGroins en circulation
- capacité hebdomadaire du planning
- taille moyenne des pelotons
- balance moyenne par joueur

Plus bas, la page expose aussi :
- une **projection personnalisée**
- une **distribution live** sur plusieurs semaines
- une matrice de **profils types** selon le nombre de cochons
- une **analyse des tickets** avec cotes, EV et cap de payout
- un résumé des **mouvements récents** par `reason_code`

## Réglages modifiables

Les blocs "Réglages appliqués" sont persistés via `GameConfig`.

### Récompenses
- bonus de bienvenue
- prime quotidienne
- prime de participation
- récompenses podium 1 / 2 / 3

### Cochons
- coût du cochon de secours
- coût du 2e cochon
- incrément de coût par cochon supplémentaire
- coût d'une portée
- pression de nourrissage par cochon supplémentaire

### Paris
- Tickets Bacon par semaine
- quota de courses par cochon
- mise minimum
- mise maximum
- cap de payout par ticket
- `house_edge` par type de ticket

### Multiplicateurs journaliers

Le panneau permet aussi d'éditer le **multiplicateur de récompense** de chaque jour de course.

Important :
- les **créneaux horaires**, thèmes et volumes de courses restent gérés dans **`/admin/races`**
- `Admin > Economie` agit ici sur le **multiplicateur de récompense**, pas sur l'horaire lui-même

## Comment fonctionne le simulateur

Le simulateur prend un scénario manuel :
- joueurs actifs
- cochons par joueur
- jours actifs par semaine
- courses par cochon
- stratégie d'inscription
- mise moyenne
- tickets utilisés par joueur
- type de ticket
- taille de champ
- horizon de projection en semaines

Puis il combine ce scénario avec des données live de la base :
- `User.balance`
- nombre de cochons vivants
- courses terminées et taille moyenne des champs
- paris récents sur 30 jours
- transactions récentes
- coût moyen et céréale la moins chère
- planning actuel et capacité hebdomadaire disponible

## Hypothèses de calcul

Le simulateur reste volontairement simple et lisible :
- les champs sont supposés **homogènes**
- les probabilités de pari sont calculées sur un **champ équilibré**
- la nourriture est estimée à partir de la **céréale la moins chère**
- le nombre de courses effectives est **borné par la capacité du planning**
- deux stratégies sont proposées :
  - `spread` : étalement sur la semaine
  - `focus_friday` : priorité aux meilleurs multiplicateurs disponibles

Les résultats affichent notamment :
- net par joueur / semaine
- delta global / semaine
- projection de circulation
- variation de circulation
- détail connexion / courses / paris / nourriture

## Ce qui est réellement appliqué au runtime

Le panneau n'est pas seulement décoratif : les réglages sont utilisés par le jeu.

Ils alimentent désormais :
- le bonus de bienvenue à l'inscription
- la prime quotidienne
- le nombre de Tickets Bacon
- le quota hebdomadaire de courses
- les coûts d'adoption et de portée
- la pression de nourrissage
- les récompenses de course
- les limites de mise
- le catalogue de types de pari et leur `house_edge`
- le cap de payout affiché sur `/paris`

## Point important sur les paris

Le **cap de payout** est appliqué au moment où le ticket est posé.

Concrètement :
- le jeu calcule d'abord une cote brute
- la cote est ensuite réduite si le payout dépasserait le cap configuré
- la cote effectivement stockée dans le ticket est celle qui sera payée plus tard

Cela évite qu'un changement d'admin modifie rétroactivement des tickets déjà placés.

## Limites connues

Le simulateur donne une **direction d'équilibrage**, pas une vérité absolue.

Il ne modélise pas encore :
- les écarts de niveau réels entre cochons
- les comportements opportunistes des joueurs
- les variations fines de la Bourse aux Grains
- les changements de meta liés aux nouvelles fonctionnalités

Pour un réglage fin, il faut donc croiser :
- la simulation
- les transactions récentes
- les volumes de tickets réellement posés
- l'évolution de la circulation sur plusieurs semaines
