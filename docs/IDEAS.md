# IDEAS (BACKLOG)

## Priorités produit proposées

### 1. Logiques de victoire sur le long terme

- Mettre en place des **saisons** courtes (mensuelles par défaut) avec :
  - remise à zéro partielle des classements,
  - conservation des trophées, du Hall of Fame et des métriques historiques,
  - divisions / ligues pour séparer nouveaux éleveurs et vétérans.
- Renforcer l'**anti-snowball** pour éviter qu'un joueur dominant n'écrase durablement la concurrence :
  - ✅ gains de stats divisés par 5 (entraînement et école),
  - ✅ durée de vie des cochons divisée par 2,
  - ✅ prime de pointage journalière (15 🪙),
  - ✅ moteur de course : récupération fatigue et aspiration nerfées,
  - fatigue après sorties consécutives (à explorer),
  - rendements décroissants à l'entraînement (à explorer),
  - buffs de comeback pour les cochons frais ou les joueurs moins actifs.
- Formaliser un **Hall of Fame** saisonnier :
  - vainqueur `Saint Grouin`,
  - meilleurs éleveurs,
  - cochons les plus rentables,
  - survivants emblématiques du `Challenge de la Mort`.

## Rythme des courses

- Éviter `1 course par heure` comme règle par défaut. Garder la main côté admin sur le rythme, avec une config simple `mode calme / normal / événement`.
- Ajouter des événements ponctuels `grosse course du soir` ou `grand prix du vendredi` pour donner des rendez-vous plus mémorables.

## Convention collective de la porcherie

- Ajouter une logique de `quota hebdomadaire` type `35 heures de l'auge` : un cochon ne peut courir que `2 à 3 courses maximum par semaine`.
- Forcer l'éleveur à choisir à l'avance ses sorties importantes selon les adversaires, le jour, les bonus de course ou l'état du cochon.
- Rendre la programmation des courses plus stratégique que le simple spam de participations.
- Ajouter une lecture claire de la semaine à venir dans l'interface : jours de course, quota restant, prochaine sortie planifiée.

## Calendrier des courses

- Ajouter un vrai menu `Liste des courses` ou `Calendrier des courses`.
- Afficher les courses à venir sur la semaine et idéalement sur le mois :
  - date, type de course, règle spéciale du jour, slots disponibles, cochons déjà inscrits.
- Permettre d'inscrire son cochon à l'avance sur une ou plusieurs courses selon son quota hebdomadaire.
- Ajouter une vue `planification` :
  - quota restant pour la semaine, jours déjà réservés, alertes de fatigue, buff potentiel si le cochon se repose avant une grande course.

## Statistiques, conditions de course et équilibrage

- Donner une vraie utilité aux statistiques secondaires via des **thèmes de course** et la **météo** :
  - `Pataugeoire du Lundi` (boue) : Force et Endurance favorisées.
  - Piste sèche pour favoriser la Vitesse.
  - Formats spéciaux pour Intelligence, Agilité ou Moral.
- Revoir l'**École porcine** pour éviter le maxage trop rapide des stats :
  - ✅ gains bruts divisés par 5 (fait),
  - spécialisations (`sprinteur`, `roublard`, `marathonien`) à explorer,
  - garder le coût moral comme vrai arbitrage.

## Fatigue, porc-out et RTT

- Malus de fatigue `Sueur de Porc` si sorties consécutives.
- Malus `Fièvre Porcine` (arrêt maladie) en cas de surmenage excessif.
- Buff `Frais comme un Porcelet` après un repos de 4 à 5 jours pour aider les joueurs occasionnels.

## Bauge, absences et survie passive

- Ajouter des `Congés Porcins` (hibernation après 36-48h d'absence).
- Faire baisser la faim de base très lentement pour que la survie ne soit pas une corvée.
- Ajouter un mode `Stagiaire Ramasse-Purin` pour maintenir le minimum vital durant les vacances réelles de l'éleveur.

## Pari mutuel porcin (PMU des Groins)

- Remplacer le spam de paris par des `Tickets Bacon` limités (ex: 3 tickets par semaine redonnés le lundi).
- Ajouter une logique `Copains comme Cochons` pour encourager les pronostics collectifs sur les cochons programmés en avance.

## Blessures et vétérinaire (Plus poussé)

- Un cochon pourrait se blesser pendant une course.
- En cas de blessure grave, passage chez le vétérinaire avec un mini-jeu type `Docteur Maboul` ou puzzle d'os chronométré.

## Reproduction et lignée (Next Steps)

- Ajouter un vrai **arbre généalogique** interactif ou historique de lignée pour raconter les familles de champions.

## Semaine de la porcherie

- Donner un thème et des règles spécifiques à chaque jour :
  - Lundi : Pataugeoire (Boue/Variance/Outsiders).
  - Mardi/Jeudi : Trot du Jambon (Stabilité/Sécurité).
  - Mercredi : Marathon (Endurance/Cardio).
  - Vendredi : Grande Finale du Cochon Rôti (Gains doublés).

## Méta-jeu et communauté

- Créer un système d'**écuries / clans** pour jouer en groupe.
- Ajouter des **alertes et webhooks** vers Slack / Teams (résultats, enchères, urgences).
  - ✅ Configuration SMTP et envoi d'emails en place (admin > Notifications).
  - ✅ Liens magiques de connexion envoyés par email si SMTP configuré.
  - Reste : notifications automatiques sur événements de jeu, intégration Slack/Teams.
- Faire du trophée physique (`Le Saint Grouin`) un vrai prolongement social IRL du jeu.

## Menus et interfaces manquants

- Menu **Calendrier / Planification** interactif.
- Menu **Généalogie / Arbre généalogique**.
- Dashboard avec pronostics communautaires.
- Page de **statistiques globales** (plus gros gains, cochons les plus rentables).

## Trophées et cérémonies

- trophées de fin de mois / trimestre / année.
- Remise cérémonielle IRL lors des réunions d'équipe.

## Ton du projet

- Assumer le ton absurde et cérémoniel (titres honorifiques, folklore maison).
- Transformer les blagues internes en features cosmétiques.

## Bourse aux Grains — evolutions possibles

La Bourse aux Grains est implementee. Evolutions futures envisageables :

- **Tendances de marche** : afficher un historique des positions du curseur sur les dernieres 24h/7j.
- **Bourse a terme** : permettre de bloquer un prix a l'avance en payant une prime.
- **Crises alimentaires** : evenements aleatoires qui deplacent brutalement le curseur (secheresse, recolte exceptionnelle).
- **Lobbying porcin** : alliances entre joueurs pour deplacer le curseur ensemble (cumul de points de mouvement).
- **Speculation de vitrine** : penalite BG si le meme joueur bloque la vitrine trop souvent.
- **Qualite des terroirs** : certaines origines de cochons reagissent mieux a certains grains (synergie pays/cereale).

### Algorithme de la Bourse aux Grains

1. **Grille 7x7** : valeurs symetriques `[6, 4, 2, 0, 2, 4, 6]`. Centre (3,3) = surcout 0.
2. **Bloc 3x3 mobile** : un bloc de 3x3 cases contient les 6 cereales disposees en croix/coins. Le centre du bloc = grain de base (mais). En position initiale (centre de la grille), le mais n'a aucun surcout.
3. **Surcout** : chaque point de grille = +5% du prix de base (`BOURSE_SURCHARGE_FACTOR = 0.05`). Un grain sur la case de valeur 4 coute 20% de plus.
4. **Prix final** = `base_cost * (1 + grid_value * 0.05) * feeding_multiplier`.
5. **Points de mouvement** = `max(1, total_achats_nourriture // 10)`.
6. **Contrainte du bloc** : le centre du bloc ne peut sortir des positions 1 a 5 pour que le bloc 3x3 reste entierement dans la grille 7x7.
7. **Vitrine** : le grain achete en dernier est bloque jusqu'au prochain achat d'un grain different.
8. **Etat partage** : le curseur et la vitrine sont communs a tous les joueurs (modele `GrainMarket`, singleton id=1).

### Algorithme de l'equilibrage v2

1. **Progression stats** : tous les gains d'entrainement et d'ecole divises par 5.
2. **Duree de vie** : `max_races_range` divisee par 2 pour toutes les raretes.
3. **Prime journaliere** : `DAILY_LOGIN_REWARD = 15.0` 🪙 a la premiere connexion du jour.
4. **Moteur de course** :
   - Recuperation fatigue en strategie Economie (strat < 25) : 0.5 → 0.1 par tour.
   - Bonus d'aspiration (drafting) : 1.5 → 0.8.
   - Ces deux nerfs empechent les cochons endurants en Economie de dominer systematiquement la fin de course.

## Direction forte à garder

- Jeu de bureau asynchrone : planification de la semaine plutôt qu'actions répétitives.
- Permettre à un joueur de venir 5 minutes le lundi pour planifier toute sa semaine.

---

## Équilibrage Hardcore vs Casuals

> **Problème identifié :** L'école a un cooldown fixe de 30 minutes (`SCHOOL_COOLDOWN_MINUTES = 30`). Un joueur actif 24h/24 peut enchaîner 48 sessions/jour ; un casual en fait 2. Le ratio d'avantage XP est de ×24. Cette section documente le déséquilibre avec des simulations basées sur le code réel, et propose des mécaniques correctives.

---

### Simulations chiffrées (basées sur le code)

Les valeurs utilisées sont extraites directement de `data.py` : XP école = 22–26 (moyenne 24), cooldown 30 min, 1ère place course = 100 BitGroins, quota 3 courses/semaine/cochon.

#### Simulation 1 — Gap XP École (sans correction, 30 jours)

| Profil | Sessions/jour | XP/session (moy.) | XP/jour | XP à 30 jours |
|--------|--------------|-------------------|---------|---------------|
| Hardcore (toutes les 30 min, 24h/24) | 48 | 24 | 1 152 | **34 560** |
| Casual (2 sessions/jour) | 2 | 24 | 48 | **1 440** |

**Ratio : ×24 en faveur du hardcore.** Un casual ne peut jamais combler cet écart.

#### Simulation 2 — Impact du rendement décroissant (proposition A1)

Règle : sessions 1–2 à 100% XP, session 3 à 50%, sessions 4+ à 10%.

| Profil | Sessions 1-2 | Sessions 3+ | XP/jour | XP à 30 jours |
|--------|-------------|-------------|---------|---------------|
| Hardcore | 2 × 24 = 48 | 46 × 2.4 = 110 | **~158** | ~4 740 |
| Casual | 2 × 24 = 48 | 0 | **48** | 1 440 |

**Ratio réduit de ×24 à ×3.3.** Gain massif pour l'équité sans pénaliser le casual.

#### Simulation 3 — Écart économique BitGroins (30 jours, sans correction)

Hypothèses : hardcore = 4 cochons, tous gagnent chaque semaine ; casual = 1 cochon, 1 victoire/semaine. Quota : 3 courses/semaine/cochon.

| Profil | Victoires/semaine | Gains/semaine | Gains à 30 jours (~4.3 sem.) |
|--------|-------------------|---------------|------------------------------|
| Hardcore (4 cochons × 3 courses × 100) | 12 | 1 200 | **~5 143** |
| Casual (1 cochon × 1 victoire) | 1 | 100 | **~428** |

**Ratio : ×12 économique.** S'ajoute à l'écart XP pour creuser un fossé sur toutes les dimensions.

#### Simulation 4 — Impact de la taxe progressive (proposition C1)

Règle : gains taxés à 20% au-delà de 2 000 BitGroins, 50% au-delà de 5 000.

| Profil | Sans taxe à 30j | Avec taxe à 30j | Effet |
|--------|-----------------|-----------------|-------|
| Hardcore | ~5 143 | ~2 500 (plafonnement effectif) | Ralenti fortement après semaine 2 |
| Casual | ~428 | ~428 (non taxé) | Aucun impact négatif |

L'excédent prélevé alimente une **Caisse de Solidarité** redistribuée aux joueurs en difficulté.

---

### Groupe A — Anti-Farm

#### A1. Rendement décroissant à l'école *(priorité HAUTE)*

**Description :** Appliquer un multiplicateur XP dégressif par jour calendaire sur le cochon actif :
- Sessions 1–2 : `school_xp_multiplier = 1.0` (100%)
- Session 3 : `school_xp_multiplier = 0.5` (50%)
- Sessions 4+ : `school_xp_multiplier = 0.1` (10%) + coût énergie ×2

Le compteur repart à zéro à minuit UTC.

**Impact :** Ratio ×24 → ×3.3 (voir Simulation 2). Quick win à faible effort.

**Fichiers concernés :**
- `data.py` — ajouter constante `SCHOOL_XP_DECAY_THRESHOLDS`
- `routes/pig.py` — endpoint `/school`, lire le compteur quotidien du cochon avant d'appliquer le multiplicateur
- `services/economy_service.py` — si la logique de multiplicateur est centralisée ici
- `models.py` — ajouter champ `Pig.daily_school_sessions` (int, reset quotidien)

---

#### A2. Surmenage / Risque de blessure exponentiel *(priorité MOYENNE)*

**Description :** Tracker les actions (école + entraînement) dans une fenêtre glissante de 2h sur le cochon :
- Actions 1–2 : `injury_risk` normal (actuel : MIN=2.0, MAX=18.0)
- Actions 3–4 : `injury_risk × 1.5`
- Actions 5+ : `injury_risk × 2.5` → force à passer chez le vétérinaire (`VET_RESPONSE_MINUTES = 20`)

**Impact :** Frein naturel au farm intensif ; le hardcore doit gérer la récupération comme une ressource.

**Fichiers concernés :**
- `models.py` — `Pig` : ajouter `activity_window_start` (datetime) et `activity_window_count` (int)
- `routes/pig.py` — incrémenter et vérifier le compteur avant chaque action école/entraînement
- `helpers/race.py` — la formule `effective_risk` existe déjà, y injecter le multiplicateur de surmenage

---

#### A3. Dette de Carrière (max_races) *(priorité MOYENNE)*

**Description :** Si une course est lancée avec `energy < 20` ou `hunger < 20`, retirer 2 `max_races` au lieu de 1. Pénalise la négligence du cochon, décourage les courses en mode "zombie".

**Impact :** Indirect mais dissuasif ; réduit la durée de vie effective des cochons sur-utilisés.

**Fichiers concernés :**
- `routes/race.py` — vérifier energy/hunger au moment de l'inscription
- `services/race_service.py` — ajuster le décrément de `pig.max_races`

---

### Groupe B — Rested XP / Aide Casuals

#### B1. Bonus "Cochon Reposé" (Rested XP) *(priorité HAUTE)*

**Description :** Si aucune interaction avec le cochon depuis ≥ 12h, passer `pig.comeback_bonus_ready = True`. À la prochaine **victoire de course** : ×2 XP + ×2 gains stats + ×2 bonheur. Le flag se consomme en une fois.

Le champ `comeback_bonus_ready` existe déjà dans `models.py` — il suffit de l'alimenter automatiquement.

**Impact :** Récompense directement le joueur casual qui revient après une longue absence. Aucun impact sur le hardcore (son cochon n'atteint jamais 12h sans interaction).

**Fichiers concernés :**
- `models.py` — `Pig.comeback_bonus_ready` (existant)
- `services/pig_service.py` — ajouter vérification `last_interaction_at` au moment d'une action pig
- `services/race_service.py` — appliquer le bonus ×2 si flag actif, puis reset

---

#### B2. Mode Pension / Stagiaire (Automation) *(priorité BASSE — complexe)*

**Description :** Payer 50 BitGroins → une IA effectue automatiquement 3 sessions école dans la journée pour le cochon (aux créneaux optimaux). Money sink + aide directe aux casuals.

**Impact :** Permet au casual de "jouer" sans être connecté. Complexe à implémenter proprement.

**Fichiers concernés :**
- Nouveau `services/automation_service.py`
- `routes/pig.py` — endpoint d'activation du mode pension
- Scheduler (APScheduler ou Celery) pour déclencher les sessions différées

---

#### B3. Courses Asynchrones (Contre-la-montre) *(priorité BASSE — gros chantier)*

**Description :** Inscription ouverte toute la journée ; comparaison des temps à minuit. Le joueur soumet son cochon quand il est disponible, sans contrainte de présence en temps réel.

**Impact :** Élimine la contrainte horaire, ideal pour le "jeu de bureau asynchrone" défini comme direction forte. Chantier majeur sur le moteur de course.

**Fichiers concernés :**
- `models.py` — `Race` : nouveau mode `async`
- `race_engine.py` — séparer inscription et résolution
- Scheduler — tâche de résolution quotidienne à minuit

---

### Groupe C — Money Sinks (vider les poches des riches)

#### C1. Taxe progressive sur les gains *(priorité HAUTE)*

**Description :** À chaque crédit de BitGroins (via `credit_user_balance` dans `finance_service.py`), vérifier le solde du joueur :
- Solde > 2 000 → gain taxé à 20%
- Solde > 5 000 → gain taxé à 50%

Les BitGroins prélevés sont versés dans une **Caisse de Solidarité** (solde d'un compte système).

**Impact :** Plafonnement effectif à ~2 500 BitGroins pour le hardcore après 2 semaines (voir Simulation 4). Le casual sous 2 000 n'est jamais taxé.

**Fichiers concernés :**
- `services/finance_service.py` — modifier `credit_user_balance` pour injecter la taxe
- `services/economy_service.py` — gérer le compte Caisse de Solidarité
- `models.py` — `GameConfig` (existant) : seuils configurables `TAX_THRESHOLD_1 = 2000`, `TAX_RATE_1 = 0.20`, etc.

---

#### C2. Caisse de Solidarité IA *(priorité HAUTE — liée à C1)*

**Description :** Cagnotte alimentée par la taxe C1. Logique automatique :
- Si `user.balance < 50 BitGroins` : attribuer un **"Ticket Bacon d'Or"** (inscription gratuite à la prochaine course)
- Remplace/complète l'emergency relief actuel (20 BitGroins si < 10 BitGroins)

**Impact :** Redistribution automatique vers les joueurs en difficulté. Donne un plancher de dignité sans inflation monétaire.

**Fichiers concernés :**
- `services/economy_service.py` — logique de distribution du Ticket Bacon d'Or
- `models.py` — `GameConfig` pour le seuil, `User` ou `Pig` pour tracker le ticket gratuit

---

#### C3. Courses High Roller / Weekend VIP *(priorité MOYENNE)*

**Description :** Inscription à 500–1 000 BitGroins, gains en prestige et trophées uniques (pas de BitGroins supplémentaires). Disponibles les weekends uniquement (configurable via `GameConfig`).

**Impact :** Money sink volontaire pour les riches ; crée un événement récurrent mémorable.

**Fichiers concernés :**
- `models.py` — `Race` : champ `entry_fee`, `is_vip`
- `routes/race.py` — validation entry fee + restriction temporelle
- `services/race_service.py` — déduction entry fee via `debit_user_balance`

---

#### C4. Boss IA "Le Sanglier Noir" *(priorité MOYENNE)*

**Description :** Apparition aléatoire dans certaines courses (probabilité configurable). Stats proches du maximum. Si les joueurs perdent contre lui, le Sanglier absorbe une partie des mises/gains. Crée un risque et un event narratif.

**Impact :** Money sink dynamique et imprédictible. Génère de l'engagement sans punir systématiquement.

**Fichiers concernés :**
- `race_engine.py` — génération de NPC avec profil "boss"
- `data.py` — configuration NPC `SANGLIER_NOIR_STATS`

---

#### C5. Boutique cosmétique *(priorité BASSE)*

**Description :** Avatars animés, skins cochons, titres de chat. Coût en milliers de BitGroins. Aucun impact sur les stats ou les courses.

**Impact :** Money sink pur ; motivant pour les joueurs riches sans créer d'avantage compétitif. Long à concevoir et intégrer.

**Fichiers concernés :**
- Nouveau `routes/shop.py`
- `models.py` — ownership des cosmétiques (table `UserCosmetic`)

---

### Groupe D — Social & Solidarité

#### D1. Sponsoring (Investisseur ↔ Éleveur) *(priorité BASSE — complexe)*

**Description :** Un joueur riche finance le cochon d'un joueur pauvre (nourriture, vétérinaire, inscription de course). En échange, il récupère 30% des gains de course du sponsorisé pendant N semaines.

**Impact :** Crée un lien social, draine les richesses des whales vers les casuals de façon organique. Complexe à équilibrer et à implémenter.

**Fichiers concernés :**
- `models.py` — nouveau modèle `SponsorContract`
- `services/economy_service.py` — split automatique des gains à chaque victoire

---

### Tableau récapitulatif des priorités

| Priorité | Idée | Effort | Impact équité |
|----------|------|--------|---------------|
| 🔴 HAUTE | A1. Rendement décroissant école | Faible | Très fort (×24 → ×3.3) |
| 🔴 HAUTE | B1. Rested XP (comeback_bonus_ready) | Très faible | Fort |
| 🔴 HAUTE | C1. Taxe progressive | Moyen | Fort |
| 🔴 HAUTE | C2. Caisse Solidarité IA | Moyen | Fort |
| 🟡 MOYENNE | A2. Surmenage / blessure exponentiel | Moyen | Moyen |
| 🟡 MOYENNE | A3. Dette de carrière (max_races) | Faible | Moyen |
| 🟡 MOYENNE | C3. High Roller weekend | Moyen | Moyen |
| 🟡 MOYENNE | C4. Boss IA Sanglier Noir | Moyen | Moyen |
| 🟢 BASSE | B2. Pension / Automation | Fort | Moyen |
| 🟢 BASSE | C5. Boutique cosmétique | Fort | Faible |
| 🟢 BASSE | B3. Courses Asynchrones | Très fort | Moyen |
| 🟢 BASSE | D1. Sponsoring | Très fort | Moyen |

---

### Simulation — Joueur qui enchaîne tous les mini-jeux (session marathon)

> **Hypothèse :** Un joueur se connecte et joue de façon continue. On simule une journée complète (24h) en enchaînant toutes les actions disponibles, et on identifie ce qui se casse ou devient absurde.

#### Ressources de départ (cochon niveau 1, rareté Commune)

| Ressource | Valeur initiale |
|-----------|----------------|
| Energy | 80 |
| Hunger | 60 |
| Happiness | 70 |
| BitGroins | 15 (daily login) |
| XP | 0 |

---

#### Bloc 1 — Entraînement (la faille silencieuse)

L'entraînement **n'a aucun cooldown**. La seule limite est l'énergie et la faim. Or la nourriture restaure l'énergie (Avoine : +15 énergie, Triticale : +10).

**Cycle exploit :** Sprint (-25 énergie, -10 faim, +0.6 VIT) → Feed Avoine (+15 énergie, +15 faim, coût ~6 BitGroins) → Sprint → Feed → ...

| Itération | Énergie avant | Énergie après sprint | Énergie après avoine | Faim après sprint | Faim après avoine | Coût |
|-----------|--------------|---------------------|---------------------|-------------------|-------------------|------|
| 1 | 80 | 55 | 70 | 60 | 50 | -6 BG |
| 2 | 70 | 45 | 60 | 50 | 40 | -6 BG |
| 3 | 60 | 35 | 50 | 40 | 30 | -6 BG |
| 4 | 50 | 25 | 40 | 30 | 20 | -6 BG |
| 5 | 40 | 15 | 30 | 20 | 10 | -6 BG |
| 6 | 30 | 5 | 20 | 10 | 0 → bloqué faim | — |

→ 5 cycles faisables avant d'être bloqué par la faim. Passage à d'autres céréales (Orge +30 faim, +8 énergie, ~8 BG).

**Sur 24h, avec refeed constant :** ~40 sprints/jour théorique (limité par budget BitGroins). À 0.6 VIT/sprint → **+24 VIT en une journée**. Un casual fera 3 sprints max.

**Problème identifié : l'entraînement est le farm le plus silencieux du jeu.** Aucun cooldown, stats non plafonnées par jour. Le cout en nourriture est le seul frein, mais les mini-jeux remplissent le porte-monnaie.

---

#### Bloc 2 — École + Typing Challenge (30 min partagés)

Les deux actions partagent le même cooldown de 30 min. Impossible d'alterner pour doubler les gains.

| Heure | Action | XP | Stat | BitGroins |
|-------|--------|----|------|-----------|
| H+0 | École (bonne réponse) | +24 | +0.5 INT | 0 |
| H+0.5 | Typing (WPM > 40) | +20 | +1.5 VIT | 0 |
| H+1 | École | +24 | +0.5 INT | 0 |
| ... | ... | ... | ... | ... |
| H+24 | 48 sessions total | **+1 056 XP** | mix stats | 0 |

Comportement attendu, déjà documenté (Simulation 1 & 2 ci-dessus). Pas de nouvelle surprise ici.

---

#### Bloc 3 — Mini-jeux économiques (la vraie source d'argent infinie)

| Mini-jeu | Limite | Gain/session | Gain/jour théorique | Problème |
|----------|--------|-------------|---------------------|----------|
| Cochon Pendu | **Aucune** | 50 BG (victoire) | **Illimité** | ⚠️ Faille majeure |
| Truffes | 1 gratuit/jour, puis 2 BG/partie | 20 BG | ~10 BG net si bon | Marginal |
| Agenda (GROSMOP) | 2/jour | 50 BG | 100 BG/jour | Raisonnable |
| Blackjack/Poker | **Aucune** | Variable | **Illimité** | ⚠️ Faille majeure |

**Cochon Pendu — simulation sur 1h de jeu intensif :**

Le dictionnaire de mots est connu, les erreurs max sont 7. Un joueur qui connaît le jeu (ou note les mots) peut viser ~80% de taux de victoire.

- 1 partie ≈ 2 minutes (mots courts, devinettes rapides)
- 30 parties/heure × 80% win rate = 24 victoires
- 24 × 50 BG = **1 200 BitGroins/heure**

Comparaison : gagner toutes ses courses à la 1ère place avec 4 cochons = **1 200 BitGroins/semaine**. Le Cochon Pendu en génère autant en 1 heure.

**En 24h de jeu (irréaliste mais révélateur) : 28 800 BitGroins** — soit l'équivalent économique de 240 semaines de courses.

**Blackjack/Poker :** Avec la même logique, un joueur en avance peut farmer indéfiniment (si le moteur n'a pas de house edge suffisant ou de bankroll management). À vérifier séparément.

---

#### Bilan d'une journée marathon (joueur hardcore, 1 cochon)

| Catégorie | Hardcore (8h de jeu actif) | Casual (1h) | Ratio |
|-----------|---------------------------|-------------|-------|
| XP école/typing | 480 XP (16 sessions) | 60 XP (2 sessions) | ×8 |
| Stats entraînement | +12 VIT (20 sprints + refeed) | +1.2 VIT (2 sprints) | ×10 |
| BitGroins mini-jeux | ~4 800 BG (Pendu) | 50 BG (1 partie) | **×96** |
| BitGroins courses | +106 BG (1ère place + apparition) | +106 BG (idem) | ×1 |
| Daily login | 15 BG | 15 BG | ×1 |
| **Total BitGroins/jour** | **~5 000 BG** | **~171 BG** | **×29** |

---

#### Problèmes identifiés par criticité

**🔴 CRITIQUE — Cochon Pendu sans limite de parties**
- Gain : 50 BG/victoire, aucun cooldown, aucune limite quotidienne
- Un joueur habile peut générer 1 000+ BG/heure
- Rend toutes les autres mécaniques économiques obsolètes
- Fix suggéré : 3 parties gratuites/jour, puis coût 5 BG/partie supplémentaire (similar aux Truffes)

**🔴 CRITIQUE — Entraînement sans cooldown ni cap quotidien**
- Stat gains illimités par jour si refeed en boucle
- Le coût en nourriture est le seul frein, mais le Cochon Pendu supprime ce frein
- À 40 sprints/jour : +24 VIT (un casual en fera +1.2 en une semaine → ×140 sur 30 jours)
- Fix suggéré : cap à 5 entraînements/jour par type, ou cooldown de 20 min entre entraînements

**🟡 IMPORTANT — Blackjack/Poker sans limite**
- Permet en théorie d'accumuler des BitGroins illimités si le joueur est bon
- L'edge de la maison doit être vérifiée ; si le jeu est équitable, la variance seule ne protège pas
- Fix suggéré : limite quotidienne de mises totales (ex. 500 BG/jour max de gains nets)

**🟡 IMPORTANT — Agenda GROSMOP : 100 BG/jour garanti**
- 2 parties, 50 BG chacune, gagnable à chaque fois si bon réflexes
- Génère plus que 1 course gagnée (100 BG vs 106 BG 1ère place) sans contrainte de cochon
- Fix suggéré : garder tel quel (somme raisonnable), mais à surveiller si les autres sinks sont corrigés

**🟢 OK — Truffes**
- 1 gratuit/jour puis 2 BG/partie pour 20 BG de gain → marge nette s'érode vite
- Mécanisme sain, auto-régulé par le coût de replay

**🟢 OK — Courses**
- Quota 3/semaine/cochon bien calibré
- Gain plafonné naturellement (106 BG max/semaine/cochon)
- Principal problème : l'écart vient des autres mécaniques, pas des courses

---

### Recommandations correctives (ordre de priorité)

| # | Problème | Fix minimal | Fichiers |
|---|----------|-------------|---------|
| 1 | Cochon Pendu illimité | Max 3 parties gratuites/jour, puis coût croissant | `routes/cochon_pendu.py`, `data.py` |
| 2 | Entraînement sans cap | Cap 5 sessions/jour par type d'entraînement | `routes/pig.py`, `models.py` (champ `daily_train_count`), `data.py` |
| 3 | Blackjack/Poker sans limite | Plafond de gains nets journaliers (500 BG) | `routes/blackjack.py`, `routes/poker.py`, `services/finance_service.py` |
