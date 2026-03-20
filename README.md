# 🐷 Derby des Groins

**Le Tamagotchi de cochons de course le plus porcin de l'internet.**

Élève ton cochon, nourris-le, entraîne-le, fais-le courir — et si t'es assez fou, risque sa vie dans le **Challenge de la Mort**. Spoiler : ça finit parfois en charcuterie.

> 💡 *Idée originale née lors d'une réunion interne, proposée par Christophe. Comme quoi, les meilleures idées viennent quand on ne s'y attend pas.*

---

## 🎮 Concept

Chaque joueur possède un **cochon virtuel** qu'il doit développer comme un Tamagotchi :

- **Nourrir** avec des céréales (Orge, Blé, Seigle, Triticale, Avoine, Maïs) — chaque aliment booste des compétences différentes
- **Entraîner** (Sprint, Cross-country, Obstacles, Sparring, Puzzles, Repos)
- **Faire courir** automatiquement toutes les heures contre les cochons des autres joueurs et des PNJ
- **Parier** sur les courses avec des Groins-Coins (GC)
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

### 3. Lancer
```bash
python app.py
```

### 4. Ouvrir
```
http://localhost:5000
```

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

---

## 🏗️ Structure du projet

```
derby_des_groins/
├── app.py                  # Backend Flask (modèles, routes, logique de jeu)
├── requirements.txt        # Dépendances Python
├── README.md
├── instance/
│   └── derby.db            # Base SQLite (créée au lancement)
└── templates/
    ├── index.html           # Dashboard — courses & paris
    ├── auth.html            # Inscription / Connexion
    ├── history.html         # Historique des paris
    ├── mon_cochon.html      # Tamagotchi — stats, nourrir, entraîner, radar chart
    ├── marche.html          # Marché aux Cochons — enchères
    ├── abattoir.html        # L'Abattoir — vitrine de charcuterie
    └── cimetiere.html       # Cimetière des Légendes — tombes des héros
```

## ⚙️ Stack technique

- **Backend** : Flask + Flask-SQLAlchemy
- **Base de données** : SQLite
- **Frontend** : Tailwind CSS (CDN) + Chart.js (radar chart) + Vanilla JS
- **Fonts** : Lilita One, Nunito, Creepster (pour l'ambiance abattoir)

## 🔄 Mécanique de jeu

1. Les courses ont lieu **toutes les heures pile** (14h00, 15h00...)
2. Les cochons des joueurs sont **automatiquement inscrits** si énergie > 20% et satiété > 20%
3. Les **stats du cochon influencent** ses chances de victoire
4. Les paris ferment **30 secondes** avant le départ
5. Après la course : **XP** selon le classement (1er: 100xp, 2e: 60xp, 3e: 40xp...)
6. Le vainqueur reçoit des **bonus de stats**
7. La faim diminue avec le temps — **nourris ton cochon** ou il ne pourra plus courir
8. L'énergie se régénère naturellement (si bien nourri)

---

*Groin groin.* 🐷
