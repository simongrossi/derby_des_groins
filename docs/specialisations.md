# Spécialisations des Cochons

## Principe

Chaque cochon possède un **profil de spécialisation** qui détermine ses forces et faiblesses sur les différents terrains. Le système est conçu comme un **pierre-papier-ciseaux** : chaque spécialisation excelle sur un terrain et souffre sur un autre.

## Les 5 Spécialisations

### ⚡ Sprinteur
- **Stat forte** : Vitesse (8)
- **Stat faible** : Endurance (4)
- **Terrain fort** : Plat 🛣️ — domine sur les lignes droites
- **Terrain faible** : Descente 🛷 — manque de contrôle en descente
- **Style** : Démarre fort, fatigue rapidement. Doit capitaliser sur les segments plats.

### ⛰️ Grimpeur
- **Stat forte** : Grimpe (8)
- **Stat faible** : Agilité (4)
- **Terrain fort** : Montée ⛰️ — à l'aise dans les côtes
- **Terrain faible** : Virage 🌀 — pataud dans les virages
- **Style** : Brille en montagne mais perd du terrain en virage. Idéal sur circuits vallonnés.

### 🫁 Endurant
- **Stat forte** : Endurance (8)
- **Stat faible** : Force (4)
- **Terrain fort** : Descente 🛷 — gère la descente avec régularité
- **Terrain faible** : Boue 🟤 — manque de puissance dans la boue
- **Style** : Régulier et constant. Gagne sur la durée, pas sur l'explosivité.

### 🌀 Agile
- **Stat forte** : Agilité (8)
- **Stat faible** : Grimpe (4)
- **Terrain fort** : Virage 🌀 — négocie les tournants avec brio
- **Terrain faible** : Montée ⛰️ — souffre dans les côtes
- **Style** : Technique et précis. Adore les circuits sinueux, redoute les cols.

### 💪 Costaud
- **Stat forte** : Force (8)
- **Stat faible** : Vitesse (4)
- **Terrain fort** : Boue 🟤 — traverse la boue comme un tank
- **Terrain faible** : Plat 🛣️ — trop lent sur terrain ouvert
- **Style** : Puissant mais lent. Excelle quand le terrain devient difficile.

## Tableau des Matchups

| Terrain | Sprinteur | Grimpeur | Endurant | Agile | Costaud |
|---------|-----------|----------|----------|-------|---------|
| 🛣️ Plat | **★★★** | ★★ | ★★ | ★★ | ★ |
| ⛰️ Montée | ★★ | **★★★** | ★★ | ★ | ★★ |
| 🛷 Descente | ★ | ★★ | **★★★** | ★★ | ★★ |
| 🌀 Virage | ★★ | ★ | ★★ | **★★★** | ★★ |
| 🟤 Boue | ★★ | ★★ | ★ | ★★ | **★★★** |

## Répartition des Stats

Chaque spécialisation dispose de **27 points** répartis sur 5 stats :
- **1 stat à 8** (spécialité)
- **1 stat à 4** (faiblesse)
- **3 stats à 5** (neutres)

Cette répartition garantit un **équilibre parfait** : sur un circuit aléatoire équilibré, chaque spécialisation a exactement **20% de chances de victoire** (vérifié sur 3000 simulations).

## Points d'Évolution

Le joueur peut **redistribuer les 27 points** entre les 5 stats (min 1, max 10 par stat). Cela permet de :
- Renforcer sa spécialité pour dominer encore plus son terrain
- Compenser sa faiblesse pour être plus polyvalent
- Créer un build hybride adapté à un circuit spécifique

## Interaction avec la Stratégie

La spécialisation détermine **OÙ** le cochon est fort. La stratégie (intensité par segment) détermine **QUAND** il pousse. La combinaison gagnante :
1. Identifier les segments favorables sur le circuit
2. Monter l'intensité sur ces segments (profiter du bonus)
3. Baisser l'intensité sur les segments défavorables (économiser l'énergie)
4. Profiter du drafting sur les segments neutres
