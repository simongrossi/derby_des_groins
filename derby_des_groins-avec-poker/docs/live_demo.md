# Page Live & Mode Démo

## Page `/live`

La page Live permet de visualiser en temps réel (tour par tour) le replay d'une course terminée ou de lancer une course de démonstration.

### Fonctionnalités

#### Visualisation de course
- **Piste animée** : les cochons avancent sur une piste avec effet de terrain
- **Barre de segments** : affiche les 10 segments du circuit avec couleurs et icônes
- **Compteur de tours** : "Tour X / Total"
- **Classement live** : mise à jour à chaque tour avec positions, distances, fatigue, énergie

#### Indicateurs en temps réel sur chaque cochon
- **Barres d'énergie** (vert) et **de fatigue** (orange) sur la carte du cochon
- **Terrain actuel** : icône du segment traversé (🛣️, ⛰️, 🛷, 🌀, 🟤)
- **Badge d'événement** :
  - 🌬️ Tête (vent) — leader avec pénalité de vent
  - 💨 Aspiration — bénéficie du drafting
  - 🥵 Fatigue — fatigue élevée (>60)
  - 🫨 Faux pas — le cochon a trébuché
  - 💀 Épuisé — énergie critique (<15)
  - 🏁 Arrivée — a franchi la ligne
- **Badge de spécialisation** dans le scoreboard (⚡ Sprinteur, ⛰️ Grimpeur, etc.)

#### Contrôles
- **Pause / Lecture** : arrêter/reprendre l'animation
- **Recommencer** : relancer depuis le tour 1
- **🎮 Démo** : lancer une course simulée avec l'éditeur de stratégie

## Mode Démo

Le mode démo génère une course complète simulée avec 5 cochons prédéfinis, chacun ayant une spécialisation différente.

### Les 5 cochons de démo

| Cochon | Emoji | Spécialisation | Propriétaire |
|--------|-------|----------------|--------------|
| Rillette Express | 🐷 | Sprinteur | Alice |
| Boudin Turbo | 🐽 | Endurant | Bob |
| Saucisse Flash | 🌭 | Agile | Charlie |
| Groin de Tonnerre | 🐗 | Grimpeur | Diane |
| Jambon Volant | 🥓 | Costaud | Émile |

### Éditeur de Stratégie

Panneau visible uniquement en mode démo, permet de configurer chaque cochon :

#### Courbe d'intensité (SVG interactif)
- **10 points draggables** (un par segment du circuit)
- Glisser verticalement pour ajuster l'intensité (0-100)
- Ligne et aire colorées par cochon
- Icônes de terrain au-dessus du graphique
- Tooltip avec valeur numérique pendant le drag

#### Allocation de stats
- **5 stats** avec boutons +/- : Vitesse, Endurance, Grimpe, Agilité, Force
- **27 points** à répartir (min 1, max 10 par stat)
- Compteur de points restants
- Badge de spécialisation avec description

#### Bouton "Relancer"
Régénère une nouvelle course avec les paramètres modifiés (stratégie + stats).

## Architecture technique

### Chargement
1. Tentative de charger le replay de la dernière course réelle (`/api/race/latest/replay`)
2. Si échec → fallback automatique en mode démo
3. Le replay est enrichi (`enrichReplay()`) : normalisation des tours, calcul de totalDistance

### Format de replay
Le `replay_json` stocké en base peut être :
- **Ancien format** : liste brute de tours → encapsulé dans `{ turns: [...] }`
- **Nouveau format** : objet avec `turns`, `segments`, `participant_meta`, etc.

### Équilibrage vérifié
Le moteur de démo a été validé par simulation Monte Carlo (3000 courses) :
- Chaque spécialisation gagne ~20% des courses
- Position moyenne ~3.0 pour chaque spec
- Le bug d'ordonnancement (pig #1 always winning) a été corrigé par shuffle aléatoire
