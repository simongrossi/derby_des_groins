# 🐷 Derby des Groins - Architecture du Projet

## Technologies Utilisées
- **Backend**: Python 3.x, Flask
- **Base de données**: SQLite avec SQLAlchemy via Flask-SQLAlchemy
- **Frontend**: HTML5, Jinja2, Tailwind CSS (CDN), Chart.js
- **Fonctionnement temps réel léger**: endpoints JSON pour le countdown, les résultats et l'état du cochon

## Structure des Modèles (Database Schema)
1. **Model `GameConfig`** : stocke la configuration de l'application (heure des courses, horaire du marché, durée d'ouverture).
2. **Model `User`** : comptes utilisateurs, mot de passe hashé, solde en BitGroins `BG`, statut administrateur.
3. **Model `Pig`** : cœur du jeu. Contient les stats, l'état tamagotchi, la progression, la rareté, l'origine, la mortalité, le challenge de la mort, le suivi de l'**École porcine** et les champs de **blessure / urgence vétérinaire**.
4. **Model `Race`** : événements de course, planification et résultat final.
5. **Model `Participant`** : participants d'une course, qu'ils soient issus d'un joueur ou d'un PNJ.
6. **Model `Bet`** : paris des utilisateurs sur une course, avec cote, statut et gains.
7. **Model `Auction`** : marché des enchères pour les cochons, avec vendeur, acheteur et état de la vente.

## Mécaniques principales
- **Tamagotchi porcin** : faim, énergie, bonheur et progression évoluent dans le temps.
- **Nutrition** : chaque céréale coûte des BG et modifie la satiété, l'énergie et certaines stats.
- **Entraînement** : les séances consomment des ressources et améliorent des compétences ciblées.
- **École porcine** : des quiz tactiques accordent XP et bonus de stats, avec un cooldown indépendant par cochon.
- **Blessures et vétérinaire** : les cochons blessés sont bloqués hors des activités risquées jusqu'au puzzle de soin ou à l'expiration du timer.
- **Courses automatiques** : les cochons aptes sont inscrits, la puissance moyenne sert à calculer probabilités et cotes.
- **Garde-fous économiques** : un seul pari par course, cotes avec marge maison, prime d'urgence et retour automatique des cochons invendus.
- **Profil joueur** : une vue dédiée permet de suivre ses indicateurs et de changer son mot de passe.
- **Marché** : enchères limitées dans le temps avec résolution automatique.
- **Mort / retraite / abattoir** : les cochons ont une durée de vie et peuvent finir en charcuterie mémorable.

## Arborescence du Projet
\`\`\`
derby_des_groins/
├── app.py                  # Logique backend, routes Flask, modèles BDD
├── IDEAS.md                # Pistes de game design et backlog d'idées
├── README.md               # Vue d'ensemble du projet
├── requirements.txt        # Dépendances Python
├── instance/
│   └── derby.db            # Base SQLite générée au lancement
├── docs/                   # Documentation du projet
│   ├── architecture.md     # Technique et structure
│   └── regles_du_jeu.md    # Comment jouer
└── templates/              # Vues Jinja2/HTML
    ├── _site_header.html   # Header partagé et navigation principale
    ├── abattoir.html       # Le hall des cochons transformés
    ├── admin.html          # Paramétrage global
    ├── auth.html           # Inscription/Connexion
    ├── cimetiere.html      # Le panthéon des cochons légendaires
    ├── history.html        # Historique des paris des utilisateurs
    ├── index.html          # Accueil et affichage des courses
    ├── legendes_pop.html   # Les stars de la Pop Culture
    ├── marche.html         # Le marché aux enchères (Market open/close)
    ├── profil.html         # Profil joueur, statistiques et changement de mot de passe
    ├── classement.html     # Classement des joueurs
    ├── mon_cochon.html     # Tableau de bord individuel du cochon, entraînement et école
    ├── veterinaire.html    # Interface d'urgence et puzzle de soin
    └── veterinaire_lobby.html # Salle d'attente / overview du vétérinaire
\`\`\`

## Routes importantes
- `/` : accueil, courses ouvertes et paris.
- `/mon-cochon` : gestion des cochons vivants.
- `/profil` : vue compte joueur et changement de mot de passe.
- `/feed` et `/train` : actions tamagotchi principales.
- `/school` : soumission d'un quiz de l'école porcine.
- `/veterinaire` et `/veterinaire/<id>` : salle d'attente ou urgence d'un cochon blessé.
- `/marche` et `/bid` : visualisation et enchères du marché.
- `/api/vet/solve`, `/api/vet/timeout` : résolution ou expiration de l'opération vétérinaire.
- `/api/countdown`, `/api/latest_result`, `/api/pig` : endpoints JSON pour l'UI.

## Choix de Design
La direction artistique est basée sur le **"dark mode" amusant** avec des dégradés intenses (rouge, jaune, violet), des polices sympathiques (Lilita One, Nunito) et l'utilisation omniprésente de l'emoji 🐷 pour donner un aspect léger et addictif.
L'approche choisie pour CSS est **Tailwind CDN**.
