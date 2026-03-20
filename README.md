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
- **Parier** en simple, en **couple ordre** ou en **tierce ordre** avec des Groins-Coins (GC)
- **Gérer les blessures** via le **Vétérinaire** et son puzzle d'urgence
- **Suivre ton compte** et changer ton mot de passe dans **Mon Profil**
- **Auditer l'activite** dans **Historique** : courses terminees, tickets et journal BitGroins
- **Oser le Challenge de la Mort** — mise x3 si top 3, mais dernier = abattoir 🔪

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
| Maïs 🌽 | 5 GC | Équilibré | 100 |
| Orge 🌾 | 8 GC | +Endurance +Force | 97 |
| Blé 🌿 | 10 GC | +Force +Vitesse | 105 |
| Seigle 🌱 | 7 GC | +Agilité +Intelligence | 102 |
| Triticale 🍃 | 9 GC | +Vitesse +Endurance | 100 |
| Avoine 🥣 | 6 GC | +Moral +Agilité | 82 |

### 🏪 Marché aux Cochons

Le marché génère automatiquement des cochons aux enchères avec 4 niveaux de rareté :

| Rareté | Stats | Durée de vie | Prix départ |
|--------|-------|-------------|-------------|
| ⚪ Commun | 5-20 | 40-60 courses | 15-30 GC |
| 🔵 Rare | 15-35 | 60-80 courses | 30-60 GC |
| 🟣 Épique | 25-50 | 80-100 courses | 60-120 GC |
| 🟡 Légendaire | 40-70 | 100-150 courses | 120-250 GC |

- Enchères avec **countdown en temps réel**
- Le meilleur enchérisseur remporte le cochon
- L'ancien enchérisseur est **automatiquement remboursé**
- Acheter un nouveau cochon **envoie l'ancien à l'abattoir**

### ⏳ Durée de vie

Chaque cochon a une **durée de vie limitée** en nombre de courses. Quand il atteint sa limite, il prend sa retraite et est transformé en **charcuterie premium** (Jambon Grand Cru, Pata Negra d'Exception...).

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

```
derby_des_groins/
├── app.py                  # Backend Flask (modèles, routes, logique de jeu)
├── requirements.txt        # Dépendances Python
├── README.md
├── IDEAS.md                # Backlog d'idées et pistes de game design
├── instance/
│   └── derby.db            # Base SQLite (créée au lancement)
└── templates/
    ├── _site_header.html   # Header partagé / navigation principale
    ├── index.html           # Dashboard — courses & paris
    ├── auth.html            # Inscription / Connexion
    ├── history.html         # Historique complet : courses, paris et journal BitGroins
    ├── mon_cochon.html      # Tamagotchi — stats, nourrir, entraîner, école porcine, radar chart
    ├── profil.html          # Mon Profil — compte, stats joueur, changement de mot de passe
    ├── marche.html          # Marché aux Cochons — enchères
    ├── abattoir.html        # L'Abattoir — vitrine de charcuterie
    ├── veterinaire.html     # Urgence vétérinaire — puzzle de soin
    ├── veterinaire_lobby.html # Clinique / salle d'attente du véto
    └── cimetiere.html       # Cimetière des Légendes — tombes des héros
```

## ⚙️ Stack technique

- **Backend** : Flask + Flask-SQLAlchemy
- **Base de données** : SQLite
- **Frontend** : Tailwind CSS (CDN) + Chart.js (radar chart) + Vanilla JS
- **Fonts** : Lilita One, Nunito, Creepster (pour l'ambiance abattoir)

## 🔄 Mécanique de jeu

1. Les courses ont lieu **à l'heure configurée** (par défaut une course quotidienne)
2. Les cochons des joueurs sont **automatiquement inscrits** si énergie > 20% et satiété > 20%
3. Les **stats du cochon influencent** ses chances de victoire, avec un **facteur poids** qui récompense le bon poids de forme
4. L'**École porcine** propose des quiz tactiques avec coût en énergie/satiété, gain de stats/XP et cooldown par cochon
5. Les blessures peuvent déclencher une **urgence vétérinaire** : un cochon blessé ne peut plus s'entraîner, aller à l'école, relever le Challenge de la Mort ni participer aux courses tant qu'il n'est pas soigné
6. Le **Vétérinaire** propose un puzzle chronométré : réussite = sauvetage, échec = issue fatale
7. Chaque joueur ne peut placer **qu'un seul ticket par course**, au choix entre **simple gagnant**, **couple ordre** et **tierce ordre**
8. Les paris ferment **30 secondes** avant le départ
9. Après la course : **XP** selon le classement (1er: 100xp, 2e: 60xp, 3e: 40xp...)
10. Les éleveurs touchent des **récompenses de participation et de podium**, même sans parier
11. La faim diminue avec le temps — **nourris ton cochon** ou il ne pourra plus courir
12. Si un joueur tombe vraiment trop bas en caisse, une **prime d'urgence** l'aide à repartir
13. Le **marché** ne s'ouvre pour un nouveau compte qu'après un peu d'ancienneté ou quelques courses, pour limiter les abus de création de comptes
14. La page **Mon Profil** permet de consulter ses indicateurs de compte et de changer son mot de passe sans passer par l'admin
15. Les mouvements critiques de **BitGroins** (paris, enchères, récompenses) passent par des mises à jour atomiques côté base pour limiter les doubles clics et les conflits de concurrence
16. La page **Historique** centralise les courses terminées, les tickets déjà joués et un **journal credit/debit BitGroins** pour la traçabilité
17. Les courses, les enchères et les deadlines du vétérinaire sont gérées par un **scheduler de fond**, même si personne n'est connecté

---

*Groin groin.* 🐷
