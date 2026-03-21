# 🐷 Derby des Groins™

Bienvenue dans le Derby des Groins™.

Ce projet fait suite à une réunion interne dont l’objectif initial était simple :
traiter un sujet précis.

Après plusieurs tentatives pour trouver un créneau (et 17 messages Teams), une réunion a finalement été organisée.

Elle a duré 1h42.

Plusieurs constats ont émergé :
- le sujet initial n’a pas été abordé
- plusieurs sujets non prévus ont été traités en profondeur
- certaines idées ont semblé, sur le moment, étonnamment pertinentes
- planifier une décision a pris plus de temps que la décision elle-même

Une proposition a alors été formulée.

Au départ, c’était une blague.

Déléguer la prise de décision à un système sans contrainte d’agenda.

**Les cochons.**

Personne n’a vraiment validé.
Personne n’a vraiment refusé.

Et personne n’a relancé le sujet initial.

### Plateforme alternative de prise de décision sans réunion ni calendrier

Chaque entité porcine est élevée, nourrie et entraînée pour évoluer dans un environnement compétitif.

Aucun conflit d’agenda.
Aucun “je te laisse proposer”.
Aucun “on se refait un point”.

Les cochons courent.
**Le plus rapide décide.**

**Fonctionnalités principales :**
- arbitrage instantané sans réunion
- disponibilité permanente (même le vendredi après-midi)
- génération d’idées non planifiées mais étonnamment efficaces

> 💡 **Idée originale** : apparue au moment exact où tout le monde avait oublié l’objectif de la réunion (proposée par Christophe).

Aujourd’hui, le système est opérationnel.

Les décisions sont prises en quelques secondes.

Le sujet initial… sera traité ultérieurement.

Les résultats sont concrets.

Ce qui pose une vraie question :

**Fallait-il vraiment faire cette réunion ?**

---

## 🎮 Concept

**Le Tamagotchi de cochons de course le plus porcin de l'internet.**

Élève ton cochon, nourris-le, entraîne-le, fais-le courir — et si t'es assez fou, risque sa vie dans le **Challenge de la Mort**. Spoiler : ça finit parfois en charcuterie.

Chaque joueur possède un **cochon virtuel** qu'il doit développer comme un Tamagotchi :

- **Nourrir** avec des céréales (Orge, Blé, Seigle, Triticale, Avoine, Maïs) — chaque aliment booste des compétences différentes
- **Entraîner** (Sprint, Cross-country, Obstacles, Sparring, Puzzles, Repos)
- **Gérer le poids de forme** du cochon : trop léger ou trop lourd, et ses courses deviennent moins propres
- **Envoyer à l'École porcine** pour répondre à des quiz tactiques et gagner des bonus de stats + XP
- **Faire courir** automatiquement à l'heure configurée contre les cochons des autres joueurs et des PNJ
- **Piloter la semaine** depuis un **dashboard d'accueil** qui met en avant la course du jour, le statut de ton cochon, tes paris restants et les derniers resultats
- **Planifier les sorties** dans la page **Courses** avec une vue semaine / mois
- **Parier** en simple, en **couple ordre** ou en **tierce ordre** avec des **Tickets Bacon** limites chaque semaine
- **Gérer les blessures** via le **Vétérinaire** et son puzzle d'urgence
- **Suivre ton compte** et changer ton mot de passe dans **Mon Profil**
- **Auditer l'activite** dans **Historique** : courses terminees, tickets et journal BitGroins
- **Oser le Challenge de la Mort** — mise x3 si top 3, mais dernier = abattoir 🔪

### 🧭 Vision long terme et rétention

Le projet vise un **jeu de bureau asynchrone** capable de rester amusant plusieurs semaines sans récompenser uniquement les joueurs les plus présents.

Axes prioritaires de la roadmap :
- **Saisons et ligues** : remises à zéro partielles, divisions pour les nouveaux, Hall of Fame persistant
- **Anti-snowball** : fatigue, repos utile, buffs de comeback et quotas de course
- **Lignée & héritage** : généalogie, retraite des cochons légendaires, bonus de porcherie
- **Conditions de course** : météo, thèmes hebdomadaires, poids plus lisible et plus stratégique
- **QoL asynchrone** : congés porcins, hibernation, webhooks Slack/Teams, planification de semaine
- **Meta sociale** : écuries, trophées `Saint Grouin`, statistiques globales type PMU porcin

### 📊 Compétences (Diagramme de Kiviat)


Chaque cochon possède 6 compétences visualisées en radar chart :

| Compétence | Effet en course |
|------------|----------------|
| ⚡ Vitesse | Sprint pur |
| 🫀 Endurance | Tenir sur la durée |
| 🤸 Agilité | Virages, esquives |
| 💪 Force | Résistance aux contacts |
| 🧠 Intelligence | Stratégie de dépassement |
| ❤️ Moral | Régularité, résistance au stress |

### 🌾 Nutrition

Inspirée des vrais taux d'inclusion recommandés pour l'alimentation porcine :

| Céréale | Coût | Boost principal | Valeur fourragère (vs maïs) |
|---------|------|----------------|---------------------------|
| Maïs 🌽 | 5 🪙 | Équilibré | 100 |
| Orge 🌾 | 8 🪙 | +Endurance +Force | 97 |
| Blé 🌿 | 10 🪙 | +Force +Vitesse | 105 |
| Seigle 🌱 | 7 🪙 | +Agilité +Intelligence | 102 |
| Triticale 🍃 | 9 🪙 | +Vitesse +Endurance | 100 |
| Avoine 🥣 | 6 🪙 | +Moral +Agilité | 82 |

> **Bourse aux Grains** : les prix ci-dessus sont les prix de base. Le cout reel est determine par la **Bourse aux Grains**, un marche dynamique ou tous les joueurs partagent un bloc 3x3 de cereales sur une grille 7x7 avec valeurs symetriques `[6,4,2,0,2,4,6]`. Le centre de la grille = surcout 0. Plus le bloc s'eloigne du centre, plus certaines cereales deviennent cheres (+5% par point). Chaque joueur peut deplacer le bloc avant d'acheter, et le dernier grain achete est bloque en vitrine jusqu'a ce qu'un concurrent achete autre chose.

### 🏪 Marché aux Cochons

Le marché génère automatiquement des cochons aux enchères avec 4 niveaux de rareté :

| Rareté | Stats | Durée de vie | Prix départ |
|--------|-------|-------------|-------------|
| ⚪ Commun | 5-20 | 20-30 courses | 15-30 🪙 |
| 🔵 Rare | 15-35 | 30-40 courses | 30-60 🪙 |
| 🟣 Épique | 25-50 | 40-50 courses | 60-120 🪙 |
| 🟡 Légendaire | 40-70 | 50-75 courses | 120-250 🪙 |

- Enchères avec **countdown en temps réel**
- Le meilleur enchérisseur remporte le cochon
- L'ancien enchérisseur est **automatiquement remboursé**
- Acheter un nouveau cochon **envoie l'ancien à l'abattoir**

### ⏳ Durée de vie, lignée et héritage

Chaque cochon a une **durée de vie limitée** en nombre de courses. Quand il atteint sa limite, il prend sa retraite et est transformé en **charcuterie premium** (Jambon Grand Cru, Pata Negra d'Exception...).

Le jeu gère désormais une couche **reproduction / lignée / héritage** :
- deux cochons actifs peuvent financer une **portée** pour faire naître un porcelet ;
- le porcelet hérite partiellement des stats, de l'origine et du bonus de lignée de ses parents ;
- un cochon légendaire ou déjà couvert de victoires peut prendre une **retraite d'honneur** et injecter un bonus permanent dans sa lignée et dans la porcherie du joueur ;
- plus la porcherie grandit, plus le **nourrissage devient coûteux** pour éviter l'empilement sans contrepartie.

### 💀 Le côté sombre

- **Challenge de la Mort** : mise ta fortune et la vie de ton cochon. Top 3 = x3 la mise. Dernier = cochon transformé en charcuterie.
- **L'Abattoir** (`/abattoir`) : vitrine de tous les cochons tombés au combat, exposés sous forme de jambons, saucissons, rillettes, boudins...
- **Le Cimetière des Légendes** (`/cimetiere`) : seuls les cochons avec 3+ victoires méritent une tombe. Les autres finissent en pâté.

---

## 🚀 Installation & Lancement

### 1. Cloner le projet
```bash
git clone <repo-url>
cd derby_des_groins
```

### 2. Installer les dépendances
```bash
pip install -r requirements.txt
```

> Note compatibilite : sur Python recent (notamment 3.14), le projet a besoin d'une version recente de `SQLAlchemy`. Le `requirements.txt` du depot est pingle pour eviter l'erreur `SQLCoreOperations` vue sur certains postes.

> Le projet utilise aussi `APScheduler` pour faire vivre le jeu en tache de fond : resolution des courses, controle des delais veterinaire et cloture des encheres sans dependre d'une visite sur le site.

### 3. Lancer l'application : `python app.py`
4. Accès local : `http://127.0.0.1:5000`

En usage local via `python app.py`, le scheduler demarre automatiquement dans le vrai process serveur. Si le projet est heberge via un import WSGI dedie, definir `DERBY_FORCE_SCHEDULER=1` sur le process qui doit piloter le monde de jeu.

**🔑 Accès test :**
- Les comptes par défaut (Christophe, Simon, etc.) utilisent le mot de passe : `mdp1234`
- Le compte `Christophe` dispose des droits administrateur.

La base de données SQLite est créée automatiquement au premier lancement avec 6 utilisateurs pré-configurés.

---

## 👥 Utilisateurs pré-configurés

| Joueur | Cochon | Emoji | Mot de passe |
|--------|--------|-------|-------------|
| Emerson | Groin de Tonnerre | 🐗 | `mdp1234` |
| Pascal | Le Baron du Lard | 🐷 | `mdp1234` |
| Simon | Saucisse Turbo | 🌭 | `mdp1234` |
| Edwin | Porcinator | 🐽 | `mdp1234` |
| Julien | Flash McGroin | 🐖 | `mdp1234` |
| Christophe | Père Cochon | 🏆 | `mdp1234` |

Note de demo:
- Le compte `Christophe` peut recevoir un second cochon seedé, `Patient Zero`, déjà blessé pour tester immédiatement le menu `Vétérinaire` et le puzzle de soins.

---

## 🏗️ Structure du projet

Le projet suit une architecture **Flask Blueprints** modulaire, découpée par domaine métier :

```
derby_des_groins/
├── app.py                  # Factory create_app(), migrations, seeds
├── extensions.py           # SQLAlchemy db, timezone partagés
├── models.py               # 10 modèles SQLAlchemy (User, Pig, Race, Bet, GrainMarket…)
├── data.py                 # Constantes de jeu (céréales, entraînements, raretés…)
├── helpers.py              # Logique métier (balance, courses, marché, paris…)
├── scheduler.py            # Tâches de fond APScheduler (courses, enchères, véto)
├── requirements.txt        # Dépendances Python
├── README.md
├── IDEAS.md                # Backlog d'idées et pistes de game design
├── .gitignore
│
├── routes/                 # 9 Blueprints Flask
│   ├── __init__.py         # Registre des blueprints
│   ├── auth.py             # register, login, logout, profil
│   ├── main.py             # index (dashboard), history, classement, légendes pop
│   ├── race.py             # courses (calendrier), plan_course, place_bet
│   ├── pig.py              # mon-cochon, adopt, feed, train, school, challenge, sacrifice
│   ├── bourse.py           # Bourse aux Grains — marché dynamique, grille, vitrine
│   ├── market.py           # marché, bid, sell-pig
│   ├── abattoir.py         # abattoir, cimetière
│   ├── admin.py            # admin panel, config, force-race
│   └── api.py              # vétérinaire, countdown, pig API, prix-groin
│
├── templates/
│   ├── _site_header.html   # Header partagé / navigation principale
│   ├── index.html           # Dashboard d'accueil — course du jour, tickets Bacon, actu & paris
│   ├── courses.html         # Calendrier des courses et planification
│   ├── auth.html            # Inscription / Connexion
│   ├── profil.html          # Mon Profil — compte, stats joueur, changement mdp
│   ├── history.html         # Historique complet : courses, paris et journal BitGroins
│   ├── mon_cochon.html      # Tamagotchi — stats, nourrir, entraîner, école, radar chart
│   ├── bourse.html          # Bourse aux Grains — grille 5x5, curseur partagé, vitrine
│   ├── marche.html          # Marché aux Cochons — enchères
│   ├── classement.html      # Classement général des joueurs
│   ├── legendes_pop.html    # Légendes porcines de la pop culture
│   ├── abattoir.html        # L'Abattoir — vitrine de charcuterie
│   ├── cimetiere.html       # Cimetière des Légendes — tombes des héros
│   ├── veterinaire.html     # Urgence vétérinaire — puzzle de soin
│   └── veterinaire_lobby.html # Clinique / salle d'attente du véto
│
└── instance/
    └── derby.db            # Base SQLite (créée au lancement)
```

### Architecture modulaire

| Module | Rôle | Contenu |
|--------|------|---------|
| `extensions.py` | Objets partagés | `db = SQLAlchemy()`, `APP_TIMEZONE` |
| `models.py` | Schéma de données | 10 modèles : `User`, `Pig`, `Race`, `Participant`, `Bet`, `BalanceTransaction`, `CoursePlan`, `Auction`, `GameConfig`, `GrainMarket` |
| `data.py` | Données statiques | Céréales, entraînements, école, raretés, origines, constantes d'équilibrage, grille Bourse |
| `helpers.py` | Logique métier | Gestion cochon, balance atomique, paris, courses, marché, vétérinaire, Bourse aux Grains |
| `scheduler.py` | Tâches de fond | Résolution courses, enchères, deadlines véto |
| `routes/` | 9 Blueprints | Chaque domaine a son fichier avec ses routes |
| `app.py` | Point d'entrée | Factory `create_app()`, migrations SQLite, seed utilisateurs |

## ⚙️ Stack technique

- **Backend** : Flask + Flask-SQLAlchemy + Flask Blueprints
- **Base de données** : SQLite
- **Scheduler** : APScheduler (résolution des courses, enchères, blessures)
- **Frontend** : Tailwind CSS (CDN) + Chart.js (radar chart) + Vanilla JS
- **Fonts** : Lilita One, Nunito, Creepster (pour l'ambiance abattoir)

## 🔄 Mécanique de jeu

1. Les courses ont lieu **à l'heure configurée** (par défaut une course quotidienne)
2. Les cochons des joueurs sont **automatiquement inscrits** si énergie > 20% et satiété > 20%
3. Les **stats du cochon influencent** ses chances de victoire, avec un **facteur poids** qui récompense le bon poids de forme
4. La page d'accueil sert de **dashboard bureau** : course du jour, statut du cochon, tickets Bacon restants, actu et accès rapide aux paris
5. La page **Courses** permet de voir les créneaux des semaines à venir et de planifier ses cochons à l'avance
6. Un **quota hebdomadaire** limite le nombre de courses planifiables par cochon pour préparer une vraie stratégie de calendrier
7. L'**École porcine** propose des quiz tactiques avec coût en énergie/satiété, gain de stats/XP et cooldown par cochon
8. Les blessures peuvent déclencher une **urgence vétérinaire** : un cochon blessé ne peut plus s'entraîner, aller à l'école, relever le Challenge de la Mort ni participer aux courses tant qu'il n'est pas soigné
9. Le **Vétérinaire** propose un puzzle chronométré : réussite = sauvetage, échec = issue fatale
10. Chaque joueur reçoit **3 Tickets Bacon par semaine** et ne peut placer **qu'un seul ticket par course**, au choix entre **simple gagnant**, **couple ordre** et **tierce ordre**
11. Les paris ferment **30 secondes** avant le départ
12. Après la course : **XP** selon le classement (1er: 100xp, 2e: 60xp, 3e: 40xp...)
13. Les éleveurs touchent des **récompenses de participation et de podium**, même sans parier
14. La faim diminue avec le temps — **nourris ton cochon** ou il ne pourra plus courir
15. Si un joueur tombe vraiment trop bas en caisse, une **prime d'urgence** l'aide à repartir
16. Le **marché** ne s'ouvre pour un nouveau compte qu'après un peu d'ancienneté ou quelques courses, pour limiter les abus de création de comptes
17. La page **Mon Profil** permet de consulter ses indicateurs de compte et de changer son mot de passe sans passer par l'admin
18. Les mouvements critiques de **BitGroins** (paris, enchères, récompenses) passent par des mises à jour atomiques côté base pour limiter les doubles clics et les conflits de concurrence
19. La page **Historique** centralise les courses terminées, les tickets déjà joués et un **journal credit/debit BitGroins** pour la traçabilité
20. Les courses, les enchères et les deadlines du vétérinaire sont gérées par un **scheduler de fond**, même si personne n'est connecté
21. La **Bourse aux Grains** remplace les prix fixes : un curseur sur une grille 5x5 partagée par tous les joueurs determine le prix et la qualite de la nourriture. Chaque joueur peut deplacer le curseur avant d'acheter, et le dernier grain achete est bloque en vitrine
22. Le **Classement** propose 5 onglets (General, Abattoir, Paris, Elevage, Mur de la Honte) avec 18+ awards automatiques et des charts detailles
23. La **Prime de pointage** de 15 🪙 est versee automatiquement a la premiere connexion de chaque journee pour garantir un revenu minimum
24. L'**equilibrage v2** divise les gains de stats par 5 (anti-snowball), reduit la duree de vie des cochons de moitie et nerf la strategie Economie en course

---

*Groin groin.* 🐷
