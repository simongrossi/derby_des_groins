# Regles du Jeu - Derby des Groins

Document de reference des regles joueur actuellement en place dans le depot.

Important:
- la source de verite fonctionnelle reste le code;
- les valeurs numeriques ci-dessous correspondent aux reglages actifs au 27 mars 2026 dans le depot;
- une partie de ces valeurs est administrable depuis `/admin/economy` et `/admin/progression`;
- la page publique `/regles` est la synthese joueur exposee dans l'interface.

## 1. Demarrage

- A l'inscription, un joueur recoit un bonus de bienvenue administrable, actuellement `100` BitGroins.
- L'inscription cree aussi un premier cochon gratuitement.
- La premiere connexion de chaque journee verse une prime quotidienne administrable, actuellement `15` BitGroins.
- Si un joueur tombe trop bas en caisse, le jeu peut declencher une prime d'urgence pour eviter un blocage total.

## 2. Les 6 stats permanentes

Chaque cochon possede 6 stats de base:

| Stat | Code UI | Role |
|---|---|---|
| Vitesse | `VIT` | Acceleration et pointe |
| Endurance | `END` | Tenue sur la duree |
| Agilite | `AGI` | Virages, esquives, fluidite |
| Force | `FOR` | Impact, tenue au contact |
| Intelligence | `INT` | Choix de trajectoire, lecture de course |
| Moral | `MOR` | Regularite, resistance au stress |

Ces stats montent lentement via:
- la nourriture;
- les entrainements;
- l'ecole porcine;
- le Typing Derby;
- certains gains de course.

Le niveau n'ajoute pas automatiquement `+1 partout`. Il depend d'une courbe d'XP et donne surtout de la progression de carriere et un bonus d'humeur au level-up.

## 3. Niveau et XP

Regles actuelles:
- formule de seuil: `XP totale = 100 * niveau^1.5`;
- bonus au level-up: `+10` humeur;
- l'XP est cumulative: on ne "consomme" pas l'XP quand on change de niveau.

Seuils utiles:

| Niveau cible | XP totale requise |
|---|---:|
| 2 | 283 |
| 3 | 520 |
| 4 | 800 |
| 5 | 1118 |
| 6 | 1470 |

XP de course actuelle:

| Position | XP |
|---|---:|
| 1 | 100 |
| 2 | 60 |
| 3 | 40 |
| 4 | 25 |
| 5 | 15 |
| 6 | 10 |
| 7 | 5 |
| 8 | 3 |

## 4. Les jauges de forme

Les stats permanentes ne suffisent pas. La performance reelle depend aussi de l'etat courant du cochon.

### Energie

- un cochon ne peut plus courir si `energie <= 20`;
- l'energie remonte de `5/h` si la satiete reste au-dessus de `30`;
- sinon elle redescend de `1/h`;
- une course coute actuellement `15` energie;
- le veterinaire coute actuellement `10` energie;
- certains entrainements consomment beaucoup d'energie, le repos en rend.

### Satiete

- un cochon ne peut plus courir si `satiete <= 20`;
- la satiete baisse naturellement de `2/h`;
- une course coute actuellement `10` satiete;
- nourrir remonte la satiete immediatement.

### Humeur

- elle influence la forme generale et certains pre-requis d'entrainement;
- sous zone de confort, elle baisse avec la faim:
  - `-1/h` sous le seuil moyen;
  - `-3/h` en zone critique;
- au repos passif, elle peut remonter de `0.3/h` jusqu'a `60`;
- monter de niveau rend `+10` humeur;
- une mauvaise reponse a l'ecole en retire.

### Fraicheur

- la fraicheur reste a `100` pendant `48h` sans interaction positive;
- ensuite elle perd `5` points par jour ouvre;
- le week-end est neutralise par la treve bureau;
- toute interaction positive utile remet la fraicheur a `100`;
- apres plus de 3 jours sans interaction positive, un bonus "comeback" est prepare pour la prochaine course.

### Poids

- le poids ideal depend des stats et du niveau du cochon;
- un cochon trop eloigne de sa zone ideale perd de la performance;
- ce meme ecart augmente aussi son risque de blessure;
- nourrir, courir et s'entrainer peuvent faire bouger le poids.

## 5. Comment augmenter les stats

### 5.1 Nourriture

Les cereales donnent satiete, energie, poids et parfois des boosts de stats.

| Cereale | Cout de base | Effets directs |
|---|---:|---|
| Mais | 5 | +20 satiete, +5 energie, +0.5 kg, gains equilibres |
| Orge | 8 | +18 satiete, +8 energie, +0.9 kg, plutot endurance/force |
| Ble | 10 | +15 satiete, +12 energie, +0.8 kg, plutot force/vitesse |
| Seigle | 7 | +17 satiete, +6 energie, +0.3 kg, plutot agilite/intelligence |
| Triticale | 9 | +16 satiete, +10 energie, +0.4 kg, plutot vitesse/endurance |
| Avoine | 6 | +14 satiete, +15 energie, +0.2 kg, plutot moral/agilite |

Attention:
- ces couts sont des couts de base;
- le cout reel passe ensuite par la Bourse aux Grains et par la pression de nourrissage de la porcherie.

### 5.2 Entrainements

Actions principales actuelles:

| Entrainement | Cout | Effet principal |
|---|---|---|
| Sprint | -25 energie, -10 satiete | vitesse, un peu endurance |
| Cross-country | -22 energie, -12 satiete | endurance, un peu force |
| Obstacles | -20 energie, -8 satiete | agilite, un peu vitesse |
| Sparring | -18 energie, -9 satiete | force, un peu moral |
| Puzzles | -12 energie, -5 satiete | intelligence, un peu moral |
| Repos & Detente | rend de l'energie | recuperation, humeur |

Regles:
- un cochon blesse ne peut pas s'entrainer;
- si l'entrainement consomme de l'energie, il faut avoir l'energie necessaire;
- il faut aussi assez de satiete;
- certains entrainements exigent une humeur minimale.

### 5.3 Ecole porcine

Regles:
- cooldown partage avec le Typing Derby: `30 minutes`;
- une bonne reponse donne les gains complets du cours et l'XP associee;
- une mauvaise reponse donne un petit peu d'XP, mais retire de l'humeur;
- un cochon blesse ne peut pas aller a l'ecole.

Cours de base:

| Cours | Gains principaux |
|---|---|
| Strategie de Virage | intelligence, agilite |
| Nutrition de Course | endurance, moral |
| Gestion du Stress | moral, intelligence |
| Analyse Video | vitesse, agilite, intelligence |

### 5.4 Typing Derby

Regles:
- partage le cooldown de l'ecole;
- donne `20 XP` de base;
- donne surtout vitesse et agilite selon la performance au clavier;
- remet aussi la fraicheur a fond.

## 6. Courses

### Quota et acces

- quota hebdomadaire actuel: `3` courses par cochon vivant;
- un cochon blesse ne peut pas courir;
- un cochon avec `energie <= 20` ou `satiete <= 20` ne peut pas courir.

### Cout d'une course

Par course:
- `-15` energie;
- `-10` satiete;
- `-0.3 kg` environ.

### Penalites de rythme

Pour eviter le spam:
- moins de `24h` depuis la course precedente: multiplicateur de perf `0.90`;
- entre `24h` et `48h`: multiplicateur `0.95`.

### Recompenses BitGroins

Recompenses economiques actuelles:
- participation: `6` BitGroins;
- podium:
  - 1er: `25`
  - 2e: `12`
  - 3e: `6`

### Retraite automatique

Chaque cochon a un plafond `max_races`:
- si `races_entered >= max_races`, il prend sa retraite automatiquement;
- les cochons adoptes directement utilisent le plafond par defaut du modele, `80`;
- les cochons generes via le marche utilisent des plages de rarete:
  - commun: `20-30`
  - rare: `30-40`
  - epique: `40-50`
  - legendaire: `50-75`

## 7. Blessures, veterinaire et mort

La mortalite rapide ne vient pas d'un systeme de vieillesse "cache". Elle vient surtout des blessures.

Regles actuelles:
- risque de blessure borne entre `2%` et `18%` avant modificateurs;
- les 8 premieres courses ont une vraie protection de debut de carriere: le risque reelle monte progressivement;
- la fatigue, la faim et le mauvais poids aggravent le risque;
- si blessure:
  - le cochon est retire des courses;
  - il ne peut plus s'entrainer;
  - il ne peut plus aller a l'ecole;
  - il ne peut plus entrer dans le Challenge de la Mort.

Veterinaire:
- fenetre de sauvetage actuelle: `20 minutes`;
- le mini-jeu penalise maintenant une erreur de seulement `5 secondes`;
- une operation reussie:
  - sauve le cochon;
  - baisse son risque de blessure de `2 points`;
  - coute `10` energie et `5` humeur;
- si la deadline expire, le cochon peut mourir de blessure.

## 8. Paris

Regles structurelles:
- `3` Tickets Bacon maximum par semaine;
- `1` seul ticket par course et par joueur;
- fermeture des paris `30 secondes` avant le depart;
- mise mini `5`, maxi `500` BitGroins;
- si un cap payout admin est active, il plafonne le gain total du ticket.

Regle speciale:
- les paris a `3+ selections` exigent que le joueur ait son propre cochon dans la course.

Formats actuellement disponibles:

| Type | Selections | Regle |
|---|---:|---|
| win | 1 | trouver le gagnant |
| place | 1 | finir dans le top 3 |
| exacta | 2 | top 2 dans l'ordre |
| quinela_place | 2 | 2 cochons dans le top 3 |
| tierce_any | 3 | top 3 dans n'importe quel ordre |
| tierce | 3 | top 3 dans l'ordre |
| quarte | 4 | top 4 dans n'importe quel ordre |
| quarte_order | 4 | top 4 dans l'ordre |
| quinte | 5 | top 5 dans n'importe quel ordre |
| rafle | 5 | top 5 dans l'ordre |

## 9. Economie d'elevage

### Cochon et porcherie

- nombre maximum de cochons: `4`;
- cout actuel de la reproduction: `45` BitGroins;
- couts d'adoption progressifs:
  - passer a 1 cochon: `15`
  - passer a 2 cochons: `30`
  - passer a 3 cochons: `45`
  - passer a 4 cochons: `60`

### Pression de nourrissage

Chaque cochon supplementaire augmente le cout des cereales de `+20%`.

Multiplicateurs actuels:

| Cochons actifs | Multiplicateur |
|---|---:|
| 1 | x1.00 |
| 2 | x1.20 |
| 3 | x1.40 |
| 4 | x1.60 |

### Reproduction et heritage

- deux cochons actifs peuvent lancer une portee;
- le porcelet herite partiellement des stats, de l'origine, de la rarete et de la lignee;
- un cochon peut partir en retraite d'honneur s'il est legendaire ou s'il a au moins `3` victoires.

## 10. Bourse aux Grains

Regles actuelles:
- grille `7x7`;
- bloc `3x3` de cereales partage par tous les joueurs;
- surcharge par point de grille: `+5%`;
- centre = reference la moins punitive;
- points de mouvement:
  - minimum garanti: `1`;
  - puis `1` point par tranche de `10` achats de nourriture;
- vitrine:
  - le dernier grain achete est bloque pour tous;
  - il faut qu'un autre grain soit achete pour le debloquer.

La page `/bourse` expose deja une aide "comment ca marche", mais `/regles` est maintenant le hub complet pour comprendre l'impact economique.

## 11. Marche, galerie et objets

### Marche aux cochons

- debloque apres `3` courses disputees ou `24h` d'anciennete du compte;
- les surencheres remboursent automatiquement l'ancien meilleur enchereur;
- un cochon non vendu retourne a son proprietaire;
- les cochons du marche suivent les plages de stats / prix / duree de vie de leur rarete.

### Galerie et P2P

- la Galerie Lard-chande gere les equipements et cosmetiques;
- Le Bon Groin gere la revente d'objets entre joueurs.

## 12. Mini-jeux

### Truffes
- mini-jeu gratuit;
- `7` clics max;
- recompense actuelle: `20` BitGroins.

### Agenda / Whack-a-Reu
- `1` partie par jour;
- objectif: attraper `5` COMOPs en `30 secondes`;
- recompense actuelle: `50` BitGroins.

### Groin Jack
- mini-casino en BitGroins;
- mise standard entre `5` et `500`;
- deck 52 cartes + 2 jokers.

### Live
- replay anime de la derniere course terminee;
- utile pour comprendre la narration et les evenements de course.

## 13. Transparence dans l'interface

Avant la mise a plat de mars 2026, l'aide etait reelle mais trop dispersee:
- `Mon Cochon` expliquait deja une partie des jauges;
- `Bourse` avait ses regles express;
- `Paris` montrait surtout l'outil, moins la logique complete.

Desormais:
- `/regles` est la page centrale dans le menu principal;
- `Mon Cochon`, `Paris` et `Bourse` pointent vers les sections pertinentes;
- les regles joueur et les docs depot sont alignees.

## 14. Reglages admin qui peuvent faire bouger ces chiffres

Source de pilotage:
- `/admin/economy` pour l'economie, les tickets, les rewards, les couts, les caps de payout et les types de paris;
- `/admin/progression` pour l'energie, la satiete, la fraicheur, la courbe d'XP, l'XP de course, les multiplicateurs de progression et les couts veto.

Conclusion:
- le vocabulaire et les principes doivent rester stables;
- les valeurs, elles, peuvent evoluer via l'admin;
- la page `/regles` et ce fichier doivent donc rester coherents apres chaque reequilibrage important.
