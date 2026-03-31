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
- **Consulter les Règles** (`/regles`) — hub public qui explique les stats, jauges, économie, marchés et paris avec les réglages actifs
- **Faire courir** automatiquement à l'heure configurée contre les cochons des autres joueurs et des PNJ
- **Parier avec des limites** : mise entre 5 et 500 BitGroins, paris complexes (3+ selections) reserves aux joueurs dont le cochon participe
- **Piloter la semaine** depuis un **dashboard d'accueil** qui met en avant la course du jour, le statut de ton cochon, tes paris restants et les derniers resultats
- **Planifier les sorties** dans la page **Courses** avec une vue semaine / mois
- **Parier** en simple, en **couple ordre** ou en **tierce ordre** avec des **Tickets Bacon** limites chaque semaine
- **Gérer les blessures** via le **Vétérinaire** et son puzzle d'urgence
- **Suivre ton compte** et changer ton mot de passe dans **Mon Profil**
- **Auditer l'activite** dans **Historique** : courses terminees, tickets et journal BitGroins
- **Piloter l'economie** depuis **Admin > Economie** avec un simulateur live branche sur les chiffres actuels de la base
- **Oser le Challenge de la Mort** — mise x3 si top 3, mais dernier = abattoir 🔪
- **Jouer au Groin Jack** (`/blackjack`) — blackjack porcin avec mise en BitGroins, Jokers et double
- **Chercher des Truffes** (`/truffes`) — mini-jeu gratuit sur grille 20×20, 7 clics pour gagner 20 🪙
- **La Légende du GROSMOP** (`/agenda`) — mini-jeu réflexe : le Chef de Porc-jet t'invite au GROSMOP mais l'annule sans cesse. Attrape 5 GROSMOPs fantômes en 30s sur le calendrier Porc-Look pour gagner 50 🪙 et le titre "Ceinture Noire de Porc-Look"
- **Regarder la Course en Direct** (`/race/live`) — replay animé tour par tour de la dernière course
- **Faire du shopping** (`/galerie-lard-chande`) — acheter des équipements et cosmétiques dans les 5 boutiques de La Galerie Lard-chande avec vos Glands et Truffes
- **Vendre et Acheter d'occasion** (`/le-bon-groin`) — marchander vos objets avec les autres joueurs sur Le Bon Groin

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

### Option A — Docker (recommande)

```bash
git clone <repo-url>
cd derby_des_groins
cp .env.example .env        # optionnel : personnaliser SECRET_KEY, etc.
docker compose up -d
```

> **Note** : Pour un déploiement derrière un reverse proxy HTTPS, ajouter `SECURE_COOKIES=true` dans le fichier `.env`. Par défaut (`false`), les sessions fonctionnent en HTTP pur (localhost).

Le site est accessible sur `http://localhost:5001`. PostgreSQL et Gunicorn sont configures automatiquement.

- `docker compose down` : arrete les services (les donnees persistent)
- `docker compose down -v` : arrete et supprime les donnees (clean restart)
- `docker compose logs -f web` : voir les logs de l'application

### Option B — Developpement local (SQLite)

```bash
git clone <repo-url>
cd derby_des_groins
pip install -r requirements.txt
python app.py
```

Acces local : `http://127.0.0.1:5000`

> **Warning `SECRET_KEY non definie`** : ce message est normal en dev local, l'app fonctionne avec une cle par defaut. Pour le supprimer, definir la variable d'environnement avant de lancer : `set SECRET_KEY=nimportequoi1234` (Windows) ou `export SECRET_KEY=nimportequoi1234` (Mac/Linux). En production, utilisez une vraie cle secrete.

> Note compatibilite : sur Python recent (notamment 3.14), le projet a besoin d'une version recente de `SQLAlchemy`. Le `requirements.txt` du depot est pingle pour eviter l'erreur `SQLCoreOperations` vue sur certains postes.

En usage local via `python app.py`, le scheduler demarre automatiquement. Si le projet est heberge via un import WSGI dedie, definir `DERBY_FORCE_SCHEDULER=1` sur le process qui doit piloter le monde de jeu.

### Acces test

- Les comptes par defaut (Christophe, Simon, etc.) utilisent le mot de passe : `mdp1234`
- Le compte `Christophe` dispose des droits administrateur.

La base de donnees est creee automatiquement au premier lancement avec 6 utilisateurs pre-configures.

---

## 👥 Utilisateurs pré-configurés

| Joueur | Cochon | Emoji | Mot de passe | Admin |
|--------|--------|-------|-------------|-------|
| Emerson | Groin de Tonnerre | 🐗 | `mdp1234` | |
| Pascal | Le Baron du Lard | 🐷 | `mdp1234` | |
| Simon | Saucisse Turbo | 🌭 | `mdp1234` | |
| Edwin | Porcinator | 🐽 | `mdp1234` | |
| Julien | Flash McGroin | 🐖 | `mdp1234` | |
| Christophe | Père Cochon | 🏆 | `mdp1234` | ✅ |
| admin | Grand Admin | 👑 | `admin` | ✅ |

Note de demo:
- Le compte `Christophe` peut recevoir un second cochon seedé, `Patient Zero`, déjà blessé pour tester immédiatement le menu `Vétérinaire` et le puzzle de soins.

## 📚 Documentation utile

- [Architecture](/D:/Programmation/derby_des_groins/docs/architecture.md)
- [Règles du jeu](/D:/Programmation/derby_des_groins/docs/regles_du_jeu.md)
- [Transparence joueur](/D:/Programmation/derby_des_groins/docs/transparence_joueur.md)
- [Panneau Admin Économie](/D:/Programmation/derby_des_groins/docs/admin_economie.md)

---

## 🏗️ Structure du projet

Le projet suit une architecture **Flask Blueprints** modulaire, découpée par domaine métier :

```
derby_des_groins/
├── app.py                  # Factory create_app(), Flask-Session init, migrations, seeds
├── extensions.py           # SQLAlchemy db, timezone partagés
├── models.py               # 19 modèles SQLAlchemy (User, Pig, Race, Bet, GrainMarket…)
├── data.py                 # Constantes de jeu (céréales, entraînements, raretés…)
├── race_engine.py          # Moteur de simulation de course
├── scheduler.py            # Tâches de fond APScheduler (courses, enchères, véto)
├── requirements.txt        # Dépendances Python
├── Dockerfile              # Image Python 3.12-slim + Gunicorn
├── docker-compose.yml      # Services web + PostgreSQL 16
├── docker-entrypoint.sh    # Attente DB + lancement Gunicorn
├── .env.example            # Variables d'environnement documentées
├── .dockerignore
├── README.md
├── .gitignore
│
├── routes/                 # 15 Blueprints Flask
│   ├── __init__.py         # Registre des blueprints
│   ├── auth.py             # register, login, logout, profil, magic-link login
│   ├── main.py             # index (dashboard), history, classement, règles, légendes pop
│   ├── race.py             # courses (calendrier), plan_course, place_bet, circuit live
│   ├── pig.py              # mon-cochon, adopt, feed, train, school, challenge, sacrifice
│   ├── bourse.py           # Bourse aux Grains — marché dynamique, grille, vitrine
│   ├── galerie.py          # Galerie Lard-chande & Le Bon Groin (Boutiques et P2P)
│   ├── market.py           # marché, bid, sell-pig
│   ├── abattoir.py         # abattoir, cimetière
│   ├── blackjack.py        # Groin Jack — blackjack porcin
│   ├── truffes.py          # Jeu des Truffes — grille 20x20
│   ├── agenda.py           # La Légende du GROSMOP — mini-jeu réflexe calendrier
│   ├── admin.py            # panneau admin complet (dashboard, economie, races, users, etc.)
│   ├── api.py              # vétérinaire, countdown, pig API, live-state, avatars
│   └── health.py           # Health check /health
│
├── helpers/                # Package helpers modulaire (8 modules)
│   ├── __init__.py         # Re-exports pour compatibilité
│   ├── config.py           # get_config, set_config, caching
│   ├── db.py               # Row-level locking helpers
│   ├── time_helpers.py     # Cooldown, formatage durées
│   ├── veterinary.py       # Deadlines véto, logique abattoir
│   ├── race.py             # Planification courses, cotes, historique
│   ├── game_data.py        # Cache céréales/trainings/leçons (TTL 5min)
│   └── market_helpers.py   # Statut unlock marché
│
├── services/               # Couche logique métier (8 modules)
│   ├── finance_service.py  # Transactions BitGroins atomiques
│   ├── pig_service.py      # Création cochon, stats, poids
│   ├── race_service.py     # Résolution courses, XP, récompenses
│   ├── market_service.py   # Enchères, remboursement auto
│   ├── galerie_service.py  # Boutiques + marketplace P2P
│   ├── marketplace_service.py
│   ├── economy_service.py  # Réglages d'équilibrage + simulateur admin
│   └── game_settings_service.py
│
├── templates/              # 38 templates Jinja2
│   ├── _pig_avatar.html    # Macro Jinja2 pig_display() (avatar pixel art ou emoji)
│   ├── _flash.html         # Partial flash messages (succès, erreurs, warnings)
│   ├── _footer.html        # Footer partagé (liens, version)
│   ├── _site_header.html   # Header partagé / navigation principale
│   ├── 429.html            # Page d'erreur 429 (rate limit)
│   ├── index.html          # Dashboard d'accueil
│   ├── regles.html         # Hub public des règles joueur
│   ├── courses.html        # Calendrier des courses (groupé par jour)
│   ├── race_circuit.html   # Circuit Live SVG 2D
│   ├── mon_cochon.html     # Tamagotchi — stats, nourrir, entraîner, radar chart
│   ├── bourse.html         # Bourse aux Grains
│   ├── marche.html         # Marché aux Cochons — enchères
│   ├── classement.html     # Classement (5 onglets)
│   ├── history.html        # Historique (3 onglets)
│   ├── admin_avatars.html   # Gestion avatars pixel art (upload PNG/SVG/code SVG)
│   ├── admin_economy.html  # Pilotage économique + simulateur live
│   ├── admin_*.html        # Admin dashboard + 8 sous-pages
│   └── ...                 # + 20 autres pages
│
├── static/                 # CSS, JS, images
│   └── avatars/            # Avatars pixel art (PNG/SVG) — volume Docker persistant
├── instance/               # Base SQLite (dev local uniquement)
└── tests/                  # Tests pytest
```

### Architecture modulaire

| Module | Rôle | Contenu |
|--------|------|---------|
| `extensions.py` | Objets partagés | `db = SQLAlchemy()`, `APP_TIMEZONE` |
| `models.py` | Schéma de données | 20 modèles SQLAlchemy (dont PigAvatar) |
| `data.py` | Données statiques | Céréales, entraînements, école, raretés, origines, constantes |
| `helpers/` | Logique métier | 8 modules : config, DB, temps, véto, courses, game data, marché |
| `services/` | Couche métier | 8 modules : finance, cochon, courses, enchères, boutiques, economie |
| `scheduler.py` | Tâches de fond | Résolution courses, enchères, deadlines véto, historique marché |
| `routes/` | 15 Blueprints | Chaque domaine a son fichier avec ses routes |
| `app.py` | Point d'entrée | Factory `create_app()`, migrations, seed utilisateurs |

## ⚙️ Stack technique

- **Backend** : Flask + Flask-SQLAlchemy + Flask-Session + Flask Blueprints
- **Base de données** : PostgreSQL (Docker) / SQLite (dev local)
- **Sessions** : Flask-Session côté serveur (SQLAlchemy/PostgreSQL, table `flask_sessions`, TTL 30 jours)
- **Serveur WSGI** : Gunicorn (1 worker, 4 threads)
- **Conteneurisation** : Docker Compose (web + PostgreSQL 16)
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
21. Le **Groin Jack** (`/blackjack`) permet de miser des BitGroins dans un blackjack porcin : deck 52 cartes + 2 Jokers, actions Hit/Stand/Double, blackjack naturel payé 3:2
22. Le **Jeu des Truffes** (`/truffes`) est un mini-jeu gratuit : trouver la truffe cachée en 7 clics sur une grille 20×20 rapporte 20 🪙
23. La **Course en Direct** (`/race/live`) propose un replay animé tour par tour de la dernière course avec positions, événements et classement live
24. La **Bourse aux Grains** remplace les prix fixes : un curseur sur une grille 5x5 partagée par tous les joueurs determine le prix et la qualite de la nourriture. Chaque joueur peut deplacer le curseur avant d'acheter, et le dernier grain achete est bloque en vitrine
25. Le **Classement** propose 5 onglets (General, Abattoir, Paris, Elevage, Mur de la Honte) avec 18+ awards automatiques et des charts detailles
26. La **Prime de pointage** de 15 🪙 est versee automatiquement a la premiere connexion de chaque journee pour garantir un revenu minimum
27. L'**equilibrage v2** divise les gains de stats par 5 (anti-snowball), reduit la duree de vie des cochons de moitie et nerf la strategie Economie en course
28. Les **avatars pixel art** permettent de remplacer l'emoji par un visuel personnalise (PNG 64x64 ou SVG) gere par l'admin dans `/admin/avatars`. Les joueurs choisissent leur avatar dans `/mon-cochon`
29. Le panneau **`/admin/economy`** permet d'ajuster les rewards, les coûts, les tickets, les caps de payout, le house edge par type de pari et les multiplicateurs journaliers, avec une simulation basee sur les donnees live de la base
30. **La Légende du GROSMOP** (`/agenda`) est un mini-jeu réflexe : le Chef de Porc-jet programme des GROSMOPs sur le calendrier Porc-Look mais les annule dès que ta souris s'approche. Attrape 5 GROSMOPs gelés en 30 secondes pour gagner 50 🪙. Piège : cliquer sur "VRAI TRAVAIL" fait perdre 2 secondes. Victoire = trophée "Ceinture Noire de Porc-Look"

---

*Groin groin.* 🐷
