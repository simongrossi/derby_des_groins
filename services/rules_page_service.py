from config.economy_defaults import COMPLEX_BET_MIN_SELECTIONS
from config.grain_market_defaults import (
    BOURSE_GRID_SIZE,
    BOURSE_MIN_MOVEMENT,
    BOURSE_MOVEMENT_DIVISOR,
)
from content.stats_metadata import STAT_LABELS
from helpers.config import get_config
from helpers.game_data import get_cereals_dict, get_school_lessons_dict, get_trainings_dict
from helpers.time_helpers import format_duration_short
from services.economy_service import (
    get_adoption_cost_for_active_count,
    get_bet_limits,
    get_configured_bet_types,
    get_daily_login_reward_value,
    get_economy_settings,
    get_feeding_multiplier_for_count,
    get_progression_settings,
    get_race_reward_settings,
    get_weekly_race_quota_value,
    get_welcome_bonus_value,
    xp_for_level_value,
)
from services.gameplay_settings_service import get_gameplay_settings, get_minigame_settings
from services.pig_power_service import get_pig_settings


def _fmt_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.1f}"


def _format_stat_changes(stats):
    parts = []
    for key, value in (stats or {}).items():
        amount = float(value or 0.0)
        if abs(amount) < 0.001:
            continue
        label = STAT_LABELS.get(key, key[:3].upper())
        parts.append(f"{'+' if amount > 0 else ''}{_fmt_number(amount)} {label}")
    return ", ".join(parts) if parts else "Aucun gain de stat direct"


def build_rules_page_context():
    economy = get_economy_settings()
    progression = get_progression_settings()
    gameplay = get_gameplay_settings()
    minigames = get_minigame_settings()
    rewards = get_race_reward_settings(economy)
    bet_limits = get_bet_limits(economy)
    bet_types = get_configured_bet_types(economy)
    cereals = get_cereals_dict()
    trainings = get_trainings_dict()
    lessons = get_school_lessons_dict()

    hero_cards = [
        {'label': "Bonus d'inscription", 'value': f"{get_welcome_bonus_value(economy):.0f} 🪙", 'note': "Crédité à la création du compte."},
        {'label': 'Prime quotidienne', 'value': f"{get_daily_login_reward_value(economy):.0f} 🪙", 'note': "Versée à la première connexion du jour."},
        {'label': 'Quota de courses', 'value': f"{get_weekly_race_quota_value(economy)} / semaine", 'note': "Par cochon vivant."},
        {'label': 'Tickets Bacon', 'value': f"{economy.weekly_bacon_tickets} / semaine", 'note': "Un seul ticket par course."},
        {'label': 'Fenêtre vétérinaire', 'value': format_duration_short(get_pig_settings().vet_response_minutes * 60), 'note': "Au-delà, le cochon peut mourir."},
        {
            'label': 'Mise par ticket',
            'value': f"{bet_limits['min_bet_race']:.0f} à {bet_limits['max_bet_race']:.0f} 🪙",
            'note': f"Cap payout : {bet_limits['max_payout_race']:.0f} 🪙" if bet_limits['max_payout_race'] > 0 else "Pas de cap payout actif.",
        },
    ]

    adoption_rows = []
    pig_max_slots = get_pig_settings().max_slots
    for active_count in range(pig_max_slots):
        adoption_rows.append({
            'label': f"Passer à {active_count + 1} cochon{'s' if active_count + 1 > 1 else ''}",
            'cost': get_adoption_cost_for_active_count(active_count, settings=economy),
        })

    feeding_rows = []
    for active_count in range(1, pig_max_slots + 1):
        feeding_rows.append({
            'stable_size': active_count,
            'multiplier': get_feeding_multiplier_for_count(active_count, settings=economy),
        })

    level_rows = []
    previous_total_xp = 0
    for level in range(2, 7):
        total_xp = xp_for_level_value(level, progression)
        level_rows.append({
            'level': level,
            'total_xp': total_xp,
            'xp_delta': total_xp - previous_total_xp,
        })
        previous_total_xp = total_xp

    race_xp_rows = [
        {'position': position, 'xp': xp_value}
        for position, xp_value in sorted(progression.race_position_xp.items())
        if xp_value > 0
    ]

    cereal_rows = [
        {
            'emoji': cereal['emoji'],
            'name': cereal['name'],
            'cost': cereal['cost'],
            'hunger': cereal.get('hunger_restore', 0),
            'energy': cereal.get('energy_restore', 0),
            'weight': cereal.get('weight_delta', 0),
            'stats': _format_stat_changes(cereal.get('stats', {})),
        }
        for cereal in cereals.values()
    ]

    training_rows = [
        {
            'emoji': training['emoji'],
            'name': training['name'],
            'energy_cost': training.get('energy_cost', 0),
            'hunger_cost': training.get('hunger_cost', 0),
            'min_happiness': training.get('min_happiness', 0),
            'weight': training.get('weight_delta', 0),
            'stats': _format_stat_changes(training.get('stats', {})),
        }
        for training in trainings.values()
    ]

    lesson_rows = [
        {
            'emoji': lesson['emoji'],
            'name': lesson['name'],
            'xp': lesson.get('xp', 0),
            'wrong_xp': lesson.get('wrong_xp', 0),
            'energy_cost': lesson.get('energy_cost', 0),
            'hunger_cost': lesson.get('hunger_cost', 0),
            'stats': _format_stat_changes(lesson.get('stats', {})),
        }
        for lesson in lessons.values()
    ]

    bet_rows = [
        {
            'icon': meta['icon'],
            'label': meta['label'],
            'selection_count': meta['selection_count'],
            'goal': "Top {} {}".format(meta['top_n'], "dans l'ordre" if meta['order_matters'] else "dans n'importe quel ordre"),
            'return_pct': meta['theoretical_return_pct'],
            'description': meta['description'],
            'is_complex': meta['selection_count'] >= COMPLEX_BET_MIN_SELECTIONS,
        }
        for _, meta in sorted(bet_types.items(), key=lambda item: (item[1]['selection_count'], item[1]['label']))
    ]

    sections = [
        {
            'id': 'demarrage',
            'emoji': '🐣',
            'title': 'Bien démarrer',
            'summary': "Le jeu donne un capital de départ, un premier cochon gratuit et quelques garde-fous pour éviter le soft-lock.",
            'bullets': [
                f"À l'inscription, tu reçois {get_welcome_bonus_value(economy):.0f} BitGroins et un premier cochon gratuit.",
                f"La première connexion de chaque journée crédite {get_daily_login_reward_value(economy):.0f} BitGroins.",
                "Le menu Mon Cochon affiche toujours les jauges, les courses restantes et les blocages éventuels avant de lancer une action.",
                "Si ta caisse tombe vraiment trop bas, le jeu peut déclencher une prime d'urgence pour te débloquer.",
            ],
        },
        {
            'id': 'progression',
            'emoji': '📈',
            'title': 'Stats, niveau et progression',
            'summary': "Les stats permanentes montent par actions ciblées. Le niveau dépend de l'XP cumulée, pas du nombre de clics.",
            'bullets': [
                "Chaque action ne travaille pas les mêmes stats: nourrir, entraîner, école et Typing Derby ont des rôles différents.",
                f"Le passage de niveau suit la formule actuelle `XP totale = {progression.level_xp_base:.0f} × niveau^{progression.level_xp_exponent:.1f}`.",
                f"Chaque level-up donne actuellement +{_fmt_number(progression.level_happiness_bonus)} d'humeur.",
                f"L'école et le Typing Derby partagent un cooldown de {gameplay.school_cooldown_minutes} minutes.",
                f"Le Typing Derby donne {int(round(progression.typing_xp_reward))} XP de base, puis ajoute surtout de la vitesse et de l'agilité selon ta performance.",
                f"🏋️ Entraînement : max {gameplay.train_daily_cap} sessions par cochon par jour (toutes disciplines). Alerte visuelle dès qu'il reste moins de 3 sessions.",
                (
                    "🎓 École et Typing Derby : rendement décroissant partagé par jour. "
                    + ", ".join(
                        f"avant {threshold} session(s) = {int(round(multiplier * 100))}%"
                        for threshold, multiplier in gameplay.school_xp_decay_thresholds
                    )
                    + f", puis plancher à {int(round(gameplay.school_xp_decay_floor * 100))}%."
                ),
            ],
        },
        {
            'id': 'etat',
            'emoji': '🫀',
            'title': 'Énergie, satiété, humeur, fraîcheur et poids',
            'summary': "Ce sont les jauges de forme du moment. Elles bougent vite et déterminent si un cochon est vraiment prêt à courir.",
            'bullets': [
                f"La satiété baisse d'environ {progression.hunger_decay_per_hour:.1f} point(s) par heure.",
                f"Si la satiété reste au-dessus de {progression.energy_regen_hunger_threshold:.0f}, l'énergie remonte de {progression.energy_regen_per_hour:.1f}/h. En dessous, l'énergie redescend de {progression.energy_drain_per_hour:.1f}/h.",
                f"Quand la satiété est trop basse, l'humeur fond plus vite: -{progression.mid_hunger_happiness_drain_per_hour:.1f}/h sous le seuil de confort, puis -{progression.low_hunger_happiness_drain_per_hour:.1f}/h en zone critique. Au repos, elle peut remonter doucement jusqu'à {progression.passive_happiness_regen_cap:.0f}.",
                f"La fraîcheur reste à 100 pendant {progression.freshness_grace_hours:.0f} h sans interaction positive, puis perd {progression.freshness_decay_per_workday:.0f} points par jour ouvré. Le week-end est mis en trêve.",
                "Toute interaction positive utile remet la fraîcheur à 100. Un retour après plus de 12h sans interaction prépare un bonus comeback pour la prochaine course.",
                "🌟 Comeback Bonus actif : si le cochon n'a pas été touché depuis +12h et qu'il gagne sa prochaine course, il reçoit ×2 XP, ×2 gains de stats et +10 bonheur. Le bonus se consomme en une seule victoire.",
                "Le poids idéal dépend des stats et du niveau. Mon Cochon affiche maintenant la cible exacte en kg, sa zone sûre et le multiplicateur de blessure lié au poids.",
                f"Un cochon ne peut plus courir si son énergie ou sa satiété tombe à 20 ou moins.",
                f"Les snacks de bureau servent juste à remonter un peu la satiété: {gameplay.snack_share_daily_limit} partage(s) maximum par jour.",
            ],
        },
        {
            'id': 'courses',
            'emoji': '🏁',
            'title': 'Courses, quotas et récompenses',
            'summary': "Les courses rapportent XP et BitGroins, mais elles usent le cochon et le calendrier impose des arbitrages.",
            'bullets': [
                "Un cochon ne participe à une course que s'il a été inscrit explicitement par son propriétaire via la page Courses. Les places non prises sont complétées par des PNJ.",
                f"Chaque cochon vivant peut être planifié sur {economy.weekly_race_quota} course(s) par semaine.",
                f"Chaque course coûte actuellement {progression.race_energy_cost:.0f} énergie, {progression.race_hunger_cost:.0f} satiété et {abs(progression.race_weight_delta):.1f} kg environ.",
                f"Si un cochon recourt en moins de 24 h, sa perf prend un multiplicateur de {progression.recent_race_penalty_under_24h:.2f}. Entre 24 h et 48 h, le multiplicateur passe à {progression.recent_race_penalty_under_48h:.2f}.",
                f"La présence rapporte {rewards['appearance_reward']:.0f} 🪙, puis le podium ajoute {rewards['position_rewards'].get(1, 0):.0f}/{rewards['position_rewards'].get(2, 0):.0f}/{rewards['position_rewards'].get(3, 0):.0f} 🪙.",
                "Les mini-jeux restent des appoints quotidiens, mais la boucle de carrière et de progression doit maintenant redevenir la course.",
                "Le niveau n'entre pas directement comme une stat magique en course: il sert surtout via l'XP cumulée, la forme, le poids et les stats construites.",
                "Mon Cochon affiche aussi les courses restantes du cochon. Quand ce plafond est atteint, il prend automatiquement sa retraite de course.",
            ],
        },
        {
            'id': 'risques',
            'emoji': '🩹',
            'title': 'Blessures, vétérinaire, mort et retraite',
            'summary': "La mort rapide ne vient pas de l'âge seul: elle est surtout liée aux blessures non soignées à temps.",
            'bullets': [
                f"Le risque de blessure est borné entre {get_pig_settings().injury_min_risk:.0f}% et {get_pig_settings().injury_max_risk:.0f}% avant modificateurs.",
                "Les 8 premières courses bénéficient d'une vraie protection de début de carrière: le risque réel monte progressivement pour éviter les morts absurdes trop tôt.",
                "Fatigue, faim et mauvais poids aggravent ce risque à chaque arrivée. Un cochon bien nourri accumule environ 2× moins de risque par course.",
                f"🩺 Le risque descend naturellement de {get_pig_settings().injury_risk_decay_per_hour:.2f} pt/h au repos. Un cochon bien soigné (énergie > 60, satiété > 50) décroît ×{get_pig_settings().injury_risk_good_care_multiplier:.0f} plus vite. Le repos est récompensé !",
                f"En cas de blessure, le cochon est bloqué tant qu'il n'est pas soigné. La fenêtre vétérinaire active est de {format_duration_short(get_pig_settings().vet_response_minutes * 60)}, plus une période de grâce de {format_duration_short(get_pig_settings().vet_grace_minutes * 60)} avant la mort effective.",
                "Les deadlines vétérinaires sont gelées pendant la trêve du weekend.",
                f"Une opération réussie réduit le risque de blessure de {get_pig_settings().injury_risk_vet_reduction:.0f} points. Plus tu attends, plus l'intervention coûte en énergie et en humeur (base: {progression.vet_energy_cost:.0f} énergie / {progression.vet_happiness_cost:.0f} humeur).",
                f"Un champion peut quitter la piste en retraite d'honneur dès {get_pig_settings().retirement_min_wins} victoires, ou immédiatement s'il est légendaire.",
            ],
        },
        {
            'id': 'paris',
            'emoji': '🎟️',
            'title': 'Paris et Tickets Bacon',
            'summary': "Les paris sont limités en nombre, ferment juste avant le départ et peuvent être plafonnés pour protéger l'économie.",
            'bullets': [
                f"Chaque joueur dispose de {economy.weekly_bacon_tickets} Ticket(s) Bacon par semaine et ne peut poser qu'un seul ticket par course.",
                f"Les mises doivent rester entre {bet_limits['min_bet_race']:.0f} et {bet_limits['max_bet_race']:.0f} BitGroins.",
                "Les paris ferment 30 secondes avant le départ.",
                f"Les tickets complexes à {COMPLEX_BET_MIN_SELECTIONS}+ sélections exigent que ton propre cochon participe à la course.",
                f"Le cap payout actif est de {bet_limits['max_payout_race']:.0f} 🪙." if bet_limits['max_payout_race'] > 0 else "Aucun cap payout n'est actif en ce moment: les gains suivent simplement la cote effective calculée à la prise de ticket.",
                "Le montant affiché par la cote est le montant réellement crédité si le ticket gagne.",
                "Si une course est annulée (participants insuffisants ou simulation sans résultat), tous les tickets sont remboursés intégralement.",
                "Historique conserve les tickets joués, leurs cotes prises au moment du pari et les mouvements de BitGroins associés.",
            ],
        },
        {
            'id': 'economie',
            'emoji': '🪙',
            'title': 'Économie, élevage et circulation des BitGroins',
            'summary': "L'économie ne repose pas que sur les paris: connexion, courses, coût des cochons et pression de nourrissage comptent autant.",
            'bullets': [
                f"Le deuxième cochon et les suivants coûtent de plus en plus cher. La porcherie est plafonnée à {get_pig_settings().max_slots} cochons.",
                f"La portée coûte actuellement {economy.breeding_cost:.0f} 🪙 et mélange stats, origine, rareté et lignée des parents.",
                f"Chaque cochon supplémentaire augmente le coût de nourrissage de +{economy.feeding_pressure_per_pig * 100:.0f}% sur tous les achats.",
                "💸 Taxe progressive anti-baleine : solde > 3 000 🪙 → 20% de taxe sur les crédits économiques entrants ; > 10 000 🪙 → 50%. Les revenus de base, les remboursements et les gains de paris sont exempts pour garder les tickets honnêtes.",
                "🤝 Caisse de Solidarité : les BitGroins taxés alimentent une cagnotte. Si tu tombes sous 50 🪙, tu reçois automatiquement 30 🪙 depuis cette caisse.",
                "Le journal de compte dans Historique est la source de vérité pour comprendre d'où viennent et où partent les BitGroins.",
                "Les panneaux admin Économie et Progression permettent de recalibrer ces valeurs sans redéployer le jeu.",
            ],
        },
        {
            'id': 'bourse',
            'emoji': '🌾',
            'title': 'Bourse aux Grains',
            'summary': "La nourriture est un marché partagé, pas une simple boutique à prix fixes.",
            'bullets': [
                f"La Bourse utilise une grille {BOURSE_GRID_SIZE}×{BOURSE_GRID_SIZE} avec un bloc 3×3 de céréales déplaçable par tous les joueurs.",
                "Chaque case de distance par rapport au centre ajoute ou retire une surcharge. Le centre est la référence la moins punitive.",
                f"Tu gagnes au moins {BOURSE_MIN_MOVEMENT} point de mouvement, puis 1 point supplémentaire par tranche de {BOURSE_MOVEMENT_DIVISOR} achats de nourriture.",
                "Le dernier grain acheté passe en vitrine et devient bloqué tant qu'un autre grain n'a pas été acheté à sa place.",
                "Sur la page Bourse, le sélecteur de cochon sert seulement à choisir qui reçoit le grain; les prix, eux, sont communs à tout le monde.",
            ],
        },
        {
            'id': 'marche',
            'emoji': '🏪',
            'title': 'Marché, galerie et objets',
            'summary': "Le Marché gère les cochons, la Galerie les équipements, et chaque circuit a ses propres verrous.",
            'bullets': [
                "Le marché aux cochons se débloque après 3 courses disputées ou 24 heures d'ancienneté de compte.",
                "Les surenchères remboursent automatiquement l'ancien enchérisseur.",
                "Si un cochon mis en vente ne trouve pas preneur, il retourne chez son propriétaire au lieu de disparaître.",
                "Les cochons du marché utilisent des raretés avec leurs propres plages de stats, de prix et de durée de carrière.",
                "La Galerie Lard-chande et Le Bon Groin ajoutent la couche d'objets, d'équipements et de revente entre joueurs.",
            ],
        },
        {
            'id': 'mini-jeux',
            'emoji': '🎮',
            'title': 'Mini-jeux et à-côtés',
            'summary': "Les mini-jeux servent à détendre le rythme bureau tout en injectant un peu de monnaie ou de progression.",
            'bullets': [
                f"🐷 Cochon Pendu : {minigames.pendu_free_plays_per_day} parties gratuites par jour, puis {minigames.pendu_extra_play_cost:.0f} 🪙 par partie supplémentaire. Le quota restant est affiché sous le bouton Rejouer.",
                f"Truffes est un revenu d'appoint gratuit sur {minigames.truffe_max_clicks} clics (limite quotidienne configurable, puis rejouer coûte quelques 🪙).",
                "🎰 Groin Jack : mini-casino en BitGroins. Plafond de 500 🪙 de gains nets par jour — au-delà, les crédits casino sont suspendus jusqu'au lendemain.",
                f"Agenda / Whack-a-Réu se joue {minigames.agenda_max_plays_per_day} fois par jour et récompense les réflexes avec une prime plus modeste qu'une vraie journée de course.",
                "Le replay Live sert à comprendre les arrivées, les accrocs et la narration d'une course terminée.",
            ],
        },
        {
            'emoji': '🥊',
            'title': "L'Octogroin — duel de boue PvP",
            'summary': "Arène 1v1 à résolution simultanée. Deux cochons programment 3 actions par manche et tentent de se pousser hors de la flaque avant la fin de la 5ᵉ manche.",
            'bullets': [
                f"Mise par joueur : entre {int(float(get_config('octogroin_min_stake', '10'))):d} et {int(float(get_config('octogroin_max_stake', '5000'))):d} 🪙, choisie par le créateur du duel. Le deuxième joueur doit couvrir la même somme pour rejoindre.",
                f"Pot commun = 2 × mise. Le gagnant empoche {int(round((1 - float(get_config('octogroin_house_tax', '0.10'))) * 100)):d} % du pot ; le reste ({int(round(float(get_config('octogroin_house_tax', '0.10')) * 100)):d} %) est prélevé par la maison. En cas de match nul, chaque joueur récupère sa mise.",
                "Jauge de position de 0 à 100 par cochon : 0 = centre, 100 = bord arrière → sorti de la flaque = défaite instantanée. Après 5 manches sans sortie, la victoire revient au cochon le moins reculé (territorial).",
                "Endurance de départ : 100. Arriver à 0 rend le cochon « essoufflé » : son action suivante échoue automatiquement.",
                "💥 Charge (−20 endu) : pousse l'adversaire (distance ≈ force/4). Deux charges simultanées = clash ; le gagnant est déterminé par force × (1 + poids/200) + vitesse/2.",
                "🧱 Ancrage (−10 endu) : contre une charge frontale, l'attaquant s'écrase et perd −30 endu en plus. Face à tout le reste, aucun effet.",
                "💨 Esquive (−15 endu) : face à une charge, chance de réussite = agilité / 100 (bornée 20–95 %). Succès → l'attaquant glisse vers son propre bord (force/3). Échec → la charge passe normalement.",
                "💤 Repos (+25 endu) : récupère de l'endurance mais très vulnérable à une charge adverse dans le même créneau (poussée ×1.5 = coup critique).",
                "Matchmaking : duels publics visibles dans le lobby ou défis directs par nom d'utilisateur (invisibles au lobby public). Un même cochon ne peut être engagé que dans un seul duel actif à la fois.",
                "Tant qu'aucun adversaire n'a rejoint, le créateur peut annuler son duel pour un remboursement intégral de la mise.",
            ],
        },
    ]

    return {
        'hero_cards': hero_cards,
        'sections': sections,
        'adoption_rows': adoption_rows,
        'feeding_rows': feeding_rows,
        'level_rows': level_rows,
        'race_xp_rows': race_xp_rows,
        'cereal_rows': cereal_rows,
        'training_rows': training_rows,
        'lesson_rows': lesson_rows,
        'bet_rows': bet_rows,
    }
