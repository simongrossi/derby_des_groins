# Course Engine - Moteur de Course

## Vue d'ensemble

Le moteur de course du Derby des Groins simule des courses de cochons tour par tour, inspiré du jeu de plateau **Flamme Rouge**. Chaque course est découpée en **segments de terrain** avec des effets différenciés, et les cochons avancent en fonction de leurs stats, leur stratégie, leur fatigue et les interactions de peloton.

## Structure d'une course

### Segments de terrain (10 segments)
Chaque course est composée de **10 segments** de terrain, répartis de manière équilibrée :
- Chacun des 5 types de terrain apparaît **au moins 1 fois** (5 garantis)
- Les 5 segments restants sont tirés aléatoirement
- Les longueurs varient de ±30% autour de la moyenne (60m par segment pour 600m total)

### Types de terrain

| Terrain | Icône | Stat clé | Fatigue | Description |
|---------|-------|----------|---------|-------------|
| PLAT | 🛣️ | Vitesse | ×0.9 | Terrain ouvert, favorise les sprinters |
| MONTEE | ⛰️ | Grimpe | ×1.3 | Côte difficile, fatigue élevée |
| DESCENTE | 🛷 | Endurance | ×0.8 | Descente technique, peu fatigant |
| VIRAGE | 🌀 | Agilité | ×1.1 | Tournants serrés, risque de faux pas |
| BOUE | 🟤 | Force | ×1.2 | Terrain lourd, très fatigant |

## Calcul de vitesse (par tour)

```
vitesse = BASE_SPEED × terrainMult × intensityMult × energyPenalty × fatigueDebuff
```

### Composantes :

1. **BASE_SPEED** = 8 m/tour (identique pour tous)

2. **terrainMult** = `baseMult × (1 + (keyStat - 5) × STAT_SCALE)`
   - `baseMult` = 0.90 (identique pour tous les terrains)
   - `STAT_SCALE` = 0.07 (±7% par point de stat)
   - Exemples : stat 8 → ×1.21, stat 5 → ×1.00, stat 4 → ×0.93

3. **intensityMult** = `0.70 + (intensity / 100) × 0.50`
   - Intensité 0 → ×0.70, intensité 100 → ×1.20
   - Contrôlé par la stratégie du joueur (1 valeur par segment)

4. **energyPenalty** : en dessous de 25 d'énergie, malus progressif (×0.55 à ×1.00)

5. **fatigueDebuff** : au-dessus de 40 de fatigue, malus progressif
   - fatigue 40 → ×1.00, fatigue 70 → ×0.80, fatigue 100 → ×0.60

6. **Variation aléatoire** : ±2.5m (simule le tirage de cartes Flamme Rouge)

## Mécanique de peloton

### Aspiration (Drafting)
- **Condition** : être 2-15m derrière le cochon devant
- **Bonus vitesse** : +10%
- **Récupération fatigue** : -2.2 par tour
- **Économie d'énergie** : +0.5 par tour

### Pénalité de tête (Leader)
- Le cochon en **1ère position** subit :
  - **Malus vitesse** : -8% (vent de face)
  - **Fatigue supplémentaire** : +1.8 par tour
- **Indication visuelle** : badge "🌬️ Tête (vent)"
- Appliqué dès le tour 1 (pas de tours gratuits)

### Faux pas (Stumble)
- Probabilité de base : 2% (plat) à 6% (virage/boue)
- Réduit par la stat Agilité : `chance × max(0.2, 1 - agilité/12)`
- Pénalité : vitesse ×0.35 pour ce tour

## Fatigue et Énergie

### Fatigue
```
fatigueGain = (intensity / 100) × 2.5 × terrainFatigueMult
+ 1.8 si leader
- 2.2 si drafting
- 0.8 si intensity < 20 (récupération)
```
- Plage : 0-100
- Effet : malus de vitesse au-dessus de 40

### Énergie
```
energyDelta = -(intensity / 100) × 1.8
+ 0.7 si intensity < 20 (repos)
+ 0.5 si drafting
```
- Plage : 0-100
- Effet : malus de vitesse en dessous de 25
- Badge "💀 Épuisé" quand énergie < 15

## Stratégie

Chaque cochon dispose d'un **profil d'intensité** : 10 valeurs (0-100), une par segment. Ce profil détermine :
- La vitesse (intensité élevée = plus rapide)
- La consommation de fatigue (intensité élevée = fatigue plus vite)
- La consommation d'énergie (intensité élevée = énergie baisse plus vite)

### Approches stratégiques :
- **Conservateur** (30-50) : économise énergie, moins de fatigue, compte sur le drafting
- **Agressif** (70-90) : rapide mais fatigue vite, risque d'épuisement en fin de course
- **Adaptatif** : ajuste l'intensité selon le terrain (fort sur ses segments, repos ailleurs)

## Données de replay

Chaque tour génère un état pour chaque cochon :
```json
{
  "id": 1, "name": "...", "emoji": "🐷",
  "distance": 145.3,
  "fatigue": 32.1,
  "energy": 78.5,
  "is_finished": false,
  "stumbled": false,
  "has_draft": true,
  "is_leader": false,
  "current_terrain": "MONTEE"
}
```

Le replay complet est stocké en base (`Race.replay_json`) pour la visualisation sur la page `/live`.
