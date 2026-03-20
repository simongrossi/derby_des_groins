# 🐷 Derby des Groins - Architecture du Projet

## Technologies Utilisées
- **Backend**: Python 3.x, Flask (Framework web)
- **Base de données**: SQLite avec SQLAlchemy (via Flask-SQLAlchemy)
- **Frontend**: HTML5, Jinja2 (Moteur de templates), Tailwind CSS (via CDN)
- **Tâches asynchrones**: `threading` (pour le fonctionnement en arrière-plan des courses automatiques)

## Structure des Modèles (Database Schema)
1. **Model `Config`** : Stocke la configuration de l'application (Heure des courses, horaire du marché, etc.).
2. **Model `User`** : Système de comptes (Pseudo, Mot de passe hashé, Solde en BitGroins `BG`, statut administrateur).
3. **Model `Pig`** : L'entité principale. Chaque cochon a un niveau, nom, emoji, stats (vitesse, endurance, etc.), propriétaire. Gère aussi l'historique de ses courses et le statut (vivant, aux enchères, abattoir).
4. **Model `Race`** : Les événements de courses, heure de lancement et résultats.
5. **Model `RaceParticipant`** : La liaison entre un cochon et une course avec position finale.
6. **Model `Bet`** : Les paris des utilisateurs sur un participant à une course, avec une cote et un statut gagné/perdu.
7. **Model `Auction`** : Le marché des enchères, contenant le prix de départ, l'enchère actuelle, et les IDs des vendeurs/acheteurs.

## Arborescence du Projet
\`\`\`
derby_des_groins/
├── app.py                  # Logique backend, routes Flask, modèles BDD
├── config.json             # Fichier généré ou géré par Flask(session secret)
├── derby.db                # Base de données SQLite générée
├── docs/                   # Documentation du projet
│   ├── architecture.md     # Technique et structure
│   └── regles_du_jeu.md    # Comment jouer
└── templates/              # Vues Jinja2/HTML
    ├── abattoir.html       # Le hall des cochons transformés
    ├── admin.html          # Paramétrage global
    ├── auth.html           # Inscription/Connexion
    ├── cimetiere.html      # Le panthéon des cochons légendaires
    ├── history.html        # Historique des paris des utilisateurs
    ├── index.html          # Accueil et affichage des courses
    ├── legendes_pop.html   # Les stars de la Pop Culture
    ├── marche.html         # Le marché aux enchères (Market open/close)
    └── mon_cochon.html     # Tableau de bord individuel du cochon
\`\`\`

## Choix de Design
La direction artistique est basée sur le **"dark mode" amusant** avec des dégradés intenses (rouge, jaune, violet), des polices sympathiques (Lilita One, Nunito) et l'utilisation omniprésente de l'emoji 🐷 pour donner un aspect léger et addictif.
L'approche choisie pour CSS est **Tailwind CDN**.
