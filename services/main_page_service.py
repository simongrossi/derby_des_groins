from datetime import datetime
from statistics import median

from sqlalchemy import func

from data import (
    BOURSE_GRID_SIZE,
    BOURSE_MIN_MOVEMENT,
    BOURSE_MOVEMENT_DIVISOR,
    COMPLEX_BET_MIN_SELECTIONS,
    SCHOOL_COOLDOWN_MINUTES,
    SNACK_SHARE_DAILY_LIMIT,
    STAT_LABELS,
)
from extensions import db
from models import BalanceTransaction, Bet, CoursePlan, Participant, Pig, Race, Trophy, User
from helpers import (
    ensure_next_race,
    get_cereals_dict,
    get_race_history_entries,
    get_school_lessons_dict,
    get_trainings_dict,
    get_user_active_pigs,
)
from services.race_service import attach_bet_outcome_snapshots
from services.economy_service import (
    get_adoption_cost_for_active_count,
    get_bet_limits,
    get_configured_bet_types,
    get_daily_login_reward_value,
    get_economy_settings,
    get_feeding_multiplier_for_count,
    get_progression_settings,
    get_race_reward_settings,
    get_weekly_bacon_tickets_value,
    get_weekly_race_quota_value,
    get_welcome_bonus_value,
    xp_for_level_value,
)
from services.finance_service import claim_daily_reward
from services.market_service import get_next_market_time, get_prix_moyen_groin, is_market_open
from services.pig_service import calculate_pig_power, get_pig_settings, get_weight_profile, update_pig_vitals
from services.race_service import (
    build_course_schedule,
    get_course_theme,
    get_pig_dashboard_status,
    get_user_weekly_bet_count,
)


def build_empty_classement_page_context():
    return {
        'rankings': [],
        'chart_data': {
            'labels': [],
            'balances': [],
            'wins': [],
            'dead': [],
            'all_labels': [],
            'all_dead': [],
            'all_challenge': [],
            'all_blessure': [],
            'all_sacrifice': [],
            'all_vieillesse': [],
            'all_bet_profit': [],
            'all_win_rate': [],
            'all_races': [],
        },
        'awards': [],
    }


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


def _build_headline_status(user, pigs_data, participants_by_pig_id):
    if not pigs_data:
        return None, None, None

    featured_candidates = [entry for entry in pigs_data if entry['pig'].id in participants_by_pig_id]
    featured_pig = featured_candidates[0] if featured_candidates else pigs_data[0]
    featured_pig_status = featured_pig['dashboard']
    featured_pig_obj = featured_pig['pig']
    participant = participants_by_pig_id.get(featured_pig_obj.id)
    if participant:
        return (
            featured_pig,
            featured_pig_status,
            {
                'participates': True,
                'label': f"{featured_pig_obj.emoji} {featured_pig_obj.name} y participe !",
                'subtext': f"Cote actuelle x{participant.odds:.1f}. {featured_pig_status['rest_label']}.",
                'tone': 'success',
            },
        )

    next_plan = (
        CoursePlan.query
        .filter(
            CoursePlan.user_id == user.id,
            CoursePlan.pig_id == featured_pig_obj.id,
            CoursePlan.scheduled_at >= datetime.now(),
        )
        .order_by(CoursePlan.scheduled_at.asc())
        .first()
    )
    if next_plan:
        plan_label = next_plan.scheduled_at.strftime('%d/%m %H:%M')
        return (
            featured_pig,
            featured_pig_status,
            {
                'participates': False,
                'label': f"📅 {featured_pig_obj.name} vise le {plan_label}",
                'subtext': featured_pig_status['rest_note'],
                'tone': 'planned',
            },
        )
    return (
        featured_pig,
        featured_pig_status,
        {
            'participates': False,
            'label': f"💤 {featured_pig_obj.name} se repose",
            'subtext': featured_pig_status['rest_note'],
            'tone': 'rest',
        },
    )


def _build_home_news_items(latest_race, latest_race_participants):
    news_items = []

    injured_pig = (
        Pig.query.filter_by(is_alive=True, is_injured=True)
        .order_by(Pig.vet_deadline.asc(), Pig.id.asc())
        .first()
    )
    if injured_pig:
        owner_name = injured_pig.owner.username if injured_pig.owner else "Un eleveur"
        news_items.append({
            'emoji': '🏥',
            'title': f"{injured_pig.name} s'est blesse",
            'text': f"{owner_name} doit l'envoyer au veto avant la deadline.",
        })

    latest_big_win = (
        BalanceTransaction.query
        .filter(BalanceTransaction.reason_code.in_(['bet_payout', 'challenge_payout']))
        .order_by(BalanceTransaction.created_at.desc(), BalanceTransaction.id.desc())
        .first()
    )
    if latest_big_win and latest_big_win.user:
        news_items.append({
            'emoji': '🎟️',
            'title': f"{latest_big_win.user.username} a touche gros",
            'text': f"{latest_big_win.reason_label}: {latest_big_win.amount:.0f} 🪙.",
        })

    if latest_race and latest_race_participants:
        winner = latest_race_participants[0]
        winner_owner = winner.owner_name or 'Ordinateur'
        news_items.append({
            'emoji': '🏆',
            'title': f"{winner.name} a gagne la derniere course",
            'text': f"Victoire signee {winner_owner} sur la course #{latest_race.id}.",
        })

    return news_items[:3]


def build_homepage_context(user_id=None):
    next_race = Race.query.filter(Race.status == 'open').order_by(Race.scheduled_at).first()
    if not next_race:
        ensure_next_race()
        next_race = Race.query.filter(Race.status == 'open').order_by(Race.scheduled_at).first()
    recent_races = (
        Race.query.filter_by(status='finished')
        .order_by(Race.finished_at.desc())
        .limit(5)
        .all()
    )

    user = db.session.get(User, user_id) if user_id else None
    user_bets = []
    pigs = []
    pigs_data = []
    week_slots = []
    headline_status = None
    featured_pig = None
    featured_pig_status = None
    weekly_bacon_tickets = get_weekly_bacon_tickets_value()
    bet_types = get_configured_bet_types()
    bacon_tickets_remaining = weekly_bacon_tickets
    latest_race = recent_races[0] if recent_races else None
    latest_race_participants = []
    daily_reward = 0.0

    if user:
        daily_reward = claim_daily_reward(user)
        pigs = get_user_active_pigs(user)
        for pig in pigs:
            update_pig_vitals(pig)
        pigs_data = [
            {
                'pig': pig,
                'power': round(calculate_pig_power(pig), 1),
                'weight_profile': get_weight_profile(pig),
                'dashboard': get_pig_dashboard_status(pig),
            }
            for pig in pigs
        ]
        week_slots = build_course_schedule(user, pigs, days=7)
        weekly_bet_count = get_user_weekly_bet_count(user, datetime.now())
        bacon_tickets_remaining = max(0, weekly_bacon_tickets - weekly_bet_count)
        if next_race:
            user_bets = Bet.query.filter_by(user_id=user.id, race_id=next_race.id).all()

    participants = []
    if next_race:
        participants = Participant.query.filter_by(race_id=next_race.id).order_by(Participant.odds).all()
    participants_by_pig_id = {
        participant.pig_id: participant
        for participant in participants
        if participant.pig_id
    }

    if latest_race:
        latest_race_participants = (
            Participant.query.filter_by(race_id=latest_race.id)
            .order_by(Participant.finish_position)
            .all()
        )

    if user and pigs_data:
        featured_pig, featured_pig_status, headline_status = _build_headline_status(
            user,
            pigs_data,
            participants_by_pig_id,
        )

    return {
        'user': user,
        'pigs': pigs,
        'next_race': next_race,
        'participants': participants,
        'recent_races': recent_races,
        'user_bets': user_bets,
        'now': datetime.now(),
        'bet_types': bet_types,
        'prix_groin': get_prix_moyen_groin(),
        'market_open': is_market_open(),
        'next_market': get_next_market_time(),
        'featured_pig': featured_pig,
        'featured_pig_status': featured_pig_status,
        'headline_status': headline_status,
        'bacon_tickets_remaining': bacon_tickets_remaining,
        'weekly_bacon_tickets': weekly_bacon_tickets,
        'week_race_cards': week_slots[:5] if week_slots else [],
        'next_race_theme': get_course_theme(next_race.scheduled_at) if next_race else None,
        'latest_race': latest_race,
        'latest_race_participants': latest_race_participants,
        'news_items': _build_home_news_items(latest_race, latest_race_participants),
        'daily_reward': daily_reward,
    }


def build_rules_page_context():
    economy = get_economy_settings()
    progression = get_progression_settings()
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
        {'label': 'Fenêtre vétérinaire', 'value': f"{get_pig_settings().vet_response_minutes} min", 'note': "Au-delà, le cochon peut mourir."},
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
            'goal': f"Top {meta['top_n']} {'dans l’ordre' if meta['order_matters'] else 'dans n’importe quel ordre'}",
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
                f"À l’inscription, tu reçois {get_welcome_bonus_value(economy):.0f} BitGroins et un premier cochon gratuit.",
                f"La première connexion de chaque journée crédite {get_daily_login_reward_value(economy):.0f} BitGroins.",
                "Le menu Mon Cochon affiche toujours les jauges, les courses restantes et les blocages éventuels avant de lancer une action.",
                "Si ta caisse tombe vraiment trop bas, le jeu peut déclencher une prime d’urgence pour te débloquer.",
            ],
        },
        {
            'id': 'progression',
            'emoji': '📈',
            'title': 'Stats, niveau et progression',
            'summary': "Les stats permanentes montent par actions ciblées. Le niveau dépend de l’XP cumulée, pas du nombre de clics.",
            'bullets': [
                "Chaque action ne travaille pas les mêmes stats: nourrir, entraîner, école et Typing Derby ont des rôles différents.",
                f"Le passage de niveau suit la formule actuelle `XP totale = {progression.level_xp_base:.0f} × niveau^{progression.level_xp_exponent:.1f}`.",
                f"Chaque level-up donne actuellement +{_fmt_number(progression.level_happiness_bonus)} d’humeur.",
                f"L’école et le Typing Derby partagent un cooldown de {SCHOOL_COOLDOWN_MINUTES} minutes.",
                f"Le Typing Derby donne {int(round(progression.typing_xp_reward))} XP de base, puis ajoute surtout de la vitesse et de l’agilité selon ta performance.",
                "🏋️ Entraînement : max 10 sessions par cochon par jour (toutes disciplines). Alerte visuelle dès qu’il reste moins de 3 sessions.",
                "🎓 École : rendement décroissant par jour. Sessions 1–2 = 100% XP/stats, session 3 = 50%, sessions 4+ = 10%. Le flash message te prévient du multiplicateur actif.",
            ],
        },
        {
            'id': 'etat',
            'emoji': '🫀',
            'title': 'Énergie, satiété, humeur, fraîcheur et poids',
            'summary': "Ce sont les jauges de forme du moment. Elles bougent vite et déterminent si un cochon est vraiment prêt à courir.",
            'bullets': [
                f"La satiété baisse d’environ {progression.hunger_decay_per_hour:.1f} point(s) par heure.",
                f"Si la satiété reste au-dessus de {progression.energy_regen_hunger_threshold:.0f}, l’énergie remonte de {progression.energy_regen_per_hour:.1f}/h. En dessous, l’énergie redescend de {progression.energy_drain_per_hour:.1f}/h.",
                f"Quand la satiété est trop basse, l’humeur fond plus vite: -{progression.mid_hunger_happiness_drain_per_hour:.1f}/h sous le seuil de confort, puis -{progression.low_hunger_happiness_drain_per_hour:.1f}/h en zone critique. Au repos, elle peut remonter doucement jusqu’à {progression.passive_happiness_regen_cap:.0f}.",
                f"La fraîcheur reste à 100 pendant {progression.freshness_grace_hours:.0f} h sans interaction positive, puis perd {progression.freshness_decay_per_workday:.0f} points par jour ouvré. Le week-end est mis en trêve.",
                "Toute interaction positive utile remet la fraîcheur à 100. Un retour après plus de 12h sans interaction prépare un bonus comeback pour la prochaine course.",
                "🌟 Comeback Bonus actif : si le cochon n'a pas été touché depuis +12h et qu'il gagne sa prochaine course, il reçoit ×2 XP, ×2 gains de stats et +10 bonheur. Le bonus se consomme en une seule victoire.",
                "Le poids idéal dépend des stats et du niveau. Un gros écart par rapport à cette zone fait baisser la performance et monter le risque de blessure.",
                f"Un cochon ne peut plus courir si son énergie ou sa satiété tombe à 20 ou moins.",
                f"Les snacks de bureau servent juste à remonter un peu la satiété: {SNACK_SHARE_DAILY_LIMIT} partage(s) maximum par jour.",
            ],
        },
        {
            'id': 'courses',
            'emoji': '🏁',
            'title': 'Courses, quotas et récompenses',
            'summary': "Les courses rapportent XP et BitGroins, mais elles usent le cochon et le calendrier impose des arbitrages.",
            'bullets': [
                f"Chaque cochon vivant peut être planifié sur {economy.weekly_race_quota} course(s) par semaine.",
                f"Chaque course coûte actuellement {progression.race_energy_cost:.0f} énergie, {progression.race_hunger_cost:.0f} satiété et {abs(progression.race_weight_delta):.1f} kg environ.",
                f"Si un cochon recourt en moins de 24 h, sa perf prend un multiplicateur de {progression.recent_race_penalty_under_24h:.2f}. Entre 24 h et 48 h, le multiplicateur passe à {progression.recent_race_penalty_under_48h:.2f}.",
                f"La présence rapporte {rewards['appearance_reward']:.0f} 🪙, puis le podium ajoute {rewards['position_rewards'].get(1, 0):.0f}/{rewards['position_rewards'].get(2, 0):.0f}/{rewards['position_rewards'].get(3, 0):.0f} 🪙.",
                "Le niveau n’entre pas directement comme une stat magique en course: il sert surtout via l’XP cumulée, la forme, le poids et les stats construites.",
                "Mon Cochon affiche aussi les courses restantes du cochon. Quand ce plafond est atteint, il prend automatiquement sa retraite de course.",
            ],
        },
        {
            'id': 'risques',
            'emoji': '🩹',
            'title': 'Blessures, vétérinaire, mort et retraite',
            'summary': "La mort rapide ne vient pas de l’âge seul: elle est surtout liée aux blessures non soignées à temps.",
            'bullets': [
                f"Le risque de blessure est maintenant borné entre {get_pig_settings().injury_min_risk:.0f}% et {get_pig_settings().injury_max_risk:.0f}% avant modificateurs.",
                "Les 8 premières courses bénéficient d’une vraie protection de début de carrière: le risque réel monte progressivement pour éviter les morts absurdes trop tôt.",
                "Fatigue, faim et mauvais poids aggravent ensuite ce risque à chaque arrivée.",
                f"En cas de blessure, le cochon est bloqué pour les courses, l’entraînement, l’école et le Challenge de la Mort tant qu’il n’est pas soigné. La fenêtre vétérinaire active est de {get_pig_settings().vet_response_minutes} minutes.",
                f"Une opération réussie réduit maintenant le risque de blessure du cochon de 2 points et coûte {progression.vet_energy_cost:.0f} énergie / {progression.vet_happiness_cost:.0f} humeur.",
                f"Un champion peut aussi quitter la piste volontairement en retraite d’honneur dès {get_pig_settings().retirement_min_wins} victoires, ou immédiatement s’il est légendaire.",
            ],
        },
        {
            'id': 'paris',
            'emoji': '🎟️',
            'title': 'Paris et Tickets Bacon',
            'summary': "Les paris sont limités en nombre, ferment juste avant le départ et peuvent être plafonnés pour protéger l’économie.",
            'bullets': [
                f"Chaque joueur dispose de {economy.weekly_bacon_tickets} Ticket(s) Bacon par semaine et ne peut poser qu’un seul ticket par course.",
                f"Les mises doivent rester entre {bet_limits['min_bet_race']:.0f} et {bet_limits['max_bet_race']:.0f} BitGroins.",
                "Les paris ferment 30 secondes avant le départ.",
                f"Les tickets complexes à {COMPLEX_BET_MIN_SELECTIONS}+ sélections exigent que ton propre cochon participe à la course.",
                f"Le cap payout actif est de {bet_limits['max_payout_race']:.0f} 🪙." if bet_limits['max_payout_race'] > 0 else "Aucun cap payout n’est actif en ce moment: les gains suivent simplement la cote effective calculée à la prise de ticket.",
                "Historique conserve les tickets joués, leurs cotes prises au moment du pari et les mouvements de BitGroins associés.",
            ],
        },
        {
            'id': 'economie',
            'emoji': '🪙',
            'title': 'Économie, élevage et circulation des BitGroins',
            'summary': "L’économie ne repose pas que sur les paris: connexion, courses, coût des cochons et pression de nourrissage comptent autant.",
            'bullets': [
                f"Le deuxième cochon et les suivants coûtent de plus en plus cher. La porcherie est plafonnée à {get_pig_settings().max_slots} cochons.",
                f"La portée coûte actuellement {economy.breeding_cost:.0f} 🪙 et mélange stats, origine, rareté et lignée des parents.",
                f"Chaque cochon supplémentaire augmente le coût de nourrissage de +{economy.feeding_pressure_per_pig * 100:.0f}% sur tous les achats.",
                "💸 Taxe progressive anti-baleine : solde > 2 000 🪙 → 20% de taxe sur chaque crédit entrant ; > 5 000 🪙 → 50%. Les revenus de base (prime quotidienne, secours d’urgence) sont exempts.",
                "🤝 Caisse de Solidarité : les BitGroins taxés alimentent une cagnotte. Si tu tombes sous 50 🪙, tu reçois automatiquement 30 🪙 depuis cette caisse.",
                "Le journal de compte dans Historique est la source de vérité pour comprendre d’où viennent et où partent les BitGroins.",
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
                "Le dernier grain acheté passe en vitrine et devient bloqué tant qu’un autre grain n’a pas été acheté à sa place.",
                "Sur la page Bourse, le sélecteur de cochon sert seulement à choisir qui reçoit le grain; les prix, eux, sont communs à tout le monde.",
            ],
        },
        {
            'id': 'marche',
            'emoji': '🏪',
            'title': 'Marché, galerie et objets',
            'summary': "Le Marché gère les cochons, la Galerie les équipements, et chaque circuit a ses propres verrous.",
            'bullets': [
                "Le marché aux cochons se débloque après 3 courses disputées ou 24 heures d’ancienneté de compte.",
                "Les surenchères remboursent automatiquement l’ancien enchérisseur.",
                "Si un cochon mis en vente ne trouve pas preneur, il retourne chez son propriétaire au lieu de disparaître.",
                "Les cochons du marché utilisent des raretés avec leurs propres plages de stats, de prix et de durée de carrière.",
                "La Galerie Lard-chande et Le Bon Groin ajoutent la couche d’objets, d’équipements et de revente entre joueurs.",
            ],
        },
        {
            'id': 'mini-jeux',
            'emoji': '🎮',
            'title': 'Mini-jeux et à-côtés',
            'summary': "Les mini-jeux servent à détendre le rythme bureau tout en injectant un peu de monnaie ou de progression.",
            'bullets': [
                "🐷 Cochon Pendu : 3 parties gratuites par jour, puis 5 🪙 par partie supplémentaire. Le quota restant est affiché sous le bouton Rejouer.",
                "Truffes est un revenu d’appoint gratuit sur 7 clics (limite quotidienne configurable, puis rejouer coûte quelques 🪙).",
                "🎰 Groin Jack : mini-casino en BitGroins. Plafond de 500 🪙 de gains nets par jour — au-delà, les crédits casino sont suspendus jusqu’au lendemain.",
                "Agenda / Whack-a-Réu se joue 1 fois par jour et récompense les réflexes.",
                "Le replay Live sert à comprendre les arrivées, les accrocs et la narration d’une course terminée.",
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


def build_classement_page_context():
    all_users = User.query.all()
    if not all_users:
        return build_empty_classement_page_context()

    pig_stats_rows = (
        db.session.query(
            Pig.user_id,
            func.coalesce(func.sum(Pig.races_won), 0),
            func.coalesce(func.sum(Pig.races_entered), 0),
        )
        .group_by(Pig.user_id)
        .all()
    )
    pig_stats = {uid: (int(w), int(r)) for uid, w, r in pig_stats_rows}

    all_pigs_list = Pig.query.all()
    pigs_by_user = {}
    for pig in all_pigs_list:
        pigs_by_user.setdefault(pig.user_id, []).append(pig)

    bet_stats_rows = (
        db.session.query(
            Bet.user_id,
            Bet.status,
            func.count(Bet.id),
            func.coalesce(func.sum(Bet.amount), 0.0),
            func.coalesce(func.sum(Bet.winnings), 0.0),
            func.max(db.case((Bet.status == 'won', Bet.odds_at_bet), else_=0.0)),
        )
        .group_by(Bet.user_id, Bet.status)
        .all()
    )
    bet_stats = {}
    for uid, status, count, staked, winnings, best_odds in bet_stats_rows:
        entry = bet_stats.setdefault(uid, {
            'total': 0,
            'won': 0,
            'lost': 0,
            'staked': 0.0,
            'winnings': 0.0,
            'won_staked': 0.0,
            'lost_staked': 0.0,
            'best_odds': 0.0,
        })
        entry['total'] += count
        entry['staked'] += float(staked)
        if status == 'won':
            entry['won'] = count
            entry['winnings'] = float(winnings)
            entry['won_staked'] = float(staked)
            entry['best_odds'] = max(entry['best_odds'], float(best_odds or 0))
        elif status == 'lost':
            entry['lost'] = count
            entry['lost_staked'] = float(staked)

    food_rows = (
        db.session.query(
            BalanceTransaction.user_id,
            func.coalesce(func.sum(func.abs(BalanceTransaction.amount)), 0.0),
        )
        .filter(BalanceTransaction.reason_code == 'feed_purchase')
        .group_by(BalanceTransaction.user_id)
        .all()
    )
    food_spent = {uid: round(float(value), 2) for uid, value in food_rows}

    earned_rows = (
        db.session.query(
            BalanceTransaction.user_id,
            func.coalesce(func.sum(BalanceTransaction.amount), 0.0),
        )
        .filter(
            BalanceTransaction.amount > 0,
            BalanceTransaction.reason_code != 'snapshot',
        )
        .group_by(BalanceTransaction.user_id)
        .all()
    )
    total_earned_map = {uid: round(float(value), 2) for uid, value in earned_rows}

    all_trophies = Trophy.query.order_by(Trophy.earned_at.asc()).all()
    trophies_by_user = {}
    for trophy in all_trophies:
        trophies_by_user.setdefault(trophy.user_id, []).append(trophy)

    rankings = []
    for user in all_users:
        total_wins, total_races = pig_stats.get(user.id, (0, 0))
        win_rate = (total_wins / total_races * 100) if total_races > 0 else 0

        user_pigs = pigs_by_user.get(user.id, [])
        dead_pigs = [pig for pig in user_pigs if not pig.is_alive]
        dead_pigs_count = len([pig for pig in dead_pigs if pig.death_cause != 'vendu'])
        deaths_by_cause = {}
        for pig in dead_pigs:
            if pig.death_cause and pig.death_cause != 'vendu':
                deaths_by_cause[pig.death_cause] = deaths_by_cause.get(pig.death_cause, 0) + 1
        deaths_challenge = deaths_by_cause.get('challenge', 0)
        deaths_blessure = deaths_by_cause.get('blessure', 0)
        deaths_sacrifice = deaths_by_cause.get('sacrifice_volontaire', 0) + deaths_by_cause.get('sacrifice', 0)
        deaths_vieillesse = deaths_by_cause.get('vieillesse', 0)
        legendary_dead = sum(
            1 for pig in dead_pigs if pig.death_cause != 'vendu' and (pig.races_won or 0) >= 3
        )

        bet_entry = bet_stats.get(user.id, {
            'total': 0,
            'won': 0,
            'lost': 0,
            'staked': 0.0,
            'winnings': 0.0,
            'won_staked': 0.0,
            'lost_staked': 0.0,
            'best_odds': 0.0,
        })
        total_bets = bet_entry['total']
        won_bets_count = bet_entry['won']
        lost_bets_count = bet_entry['lost']
        total_staked = round(bet_entry['staked'], 2)
        total_winnings = round(bet_entry['winnings'], 2)
        settled_staked = bet_entry['won_staked'] + bet_entry['lost_staked']
        bet_profit = round(total_winnings - settled_staked, 2)
        settled_count = won_bets_count + lost_bets_count
        bet_win_rate = round((won_bets_count / settled_count) * 100, 1) if settled_count else 0.0
        best_odds_hit = bet_entry['best_odds']

        active_pigs = [pig for pig in user_pigs if pig.is_alive]
        best_pig = max(
            user_pigs,
            key=lambda pig: (pig.races_won or 0, pig.level or 0),
            default=None,
        )
        max_level = max((pig.level or 1 for pig in user_pigs), default=1)
        total_school = sum(pig.school_sessions_completed or 0 for pig in user_pigs)
        total_xp = sum(pig.xp or 0 for pig in user_pigs)
        legendary_count = sum(1 for pig in user_pigs if pig.rarity == 'legendaire')

        total_spent_on_food = food_spent.get(user.id, 0.0)
        total_earned = total_earned_map.get(user.id, 0.0)

        trophies = []
        if user.balance >= 500:
            trophies.append({'n': 'Cresus', 'e': '💰', 'd': 'Plus de 500 🪙 en caisse'})
        if user.balance >= 1000:
            trophies.append({'n': 'Oligarque', 'e': '👑', 'd': 'Plus de 1000 🪙 en caisse'})
        if total_wins >= 10:
            trophies.append({'n': 'Legende', 'e': '🏆', 'd': '10 victoires au total'})
        if total_wins >= 25:
            trophies.append({'n': 'Dynastie', 'e': '🏛️', 'd': '25 victoires au total'})
        if dead_pigs_count >= 5:
            trophies.append({'n': 'Boucher', 'e': '🔪', 'd': '5 cochons morts'})
        if dead_pigs_count >= 10:
            trophies.append({'n': 'Equarrisseur', 'e': '💀', 'd': '10 cochons morts'})
        if total_races >= 50:
            trophies.append({'n': 'Veteran', 'e': '🎖️', 'd': '50 courses disputees'})
        if total_races >= 100:
            trophies.append({'n': 'Marathonien', 'e': '🏃', 'd': '100 courses disputees'})
        if deaths_challenge >= 3:
            trophies.append({'n': 'Kamikaze', 'e': '💣', 'd': '3 cochons morts au Challenge'})
        if deaths_blessure >= 3:
            trophies.append({'n': 'Negligent', 'e': '🩹', 'd': '3 cochons morts par blessure'})
        if deaths_vieillesse >= 2:
            trophies.append({'n': 'Eleveur Sage', 'e': '🧓', 'd': '2 cochons morts de vieillesse'})
        if total_school >= 20:
            trophies.append({'n': 'Pedagogue', 'e': '📚', 'd': '20 sessions ecole'})
        if total_school >= 50:
            trophies.append({'n': 'Doyen', 'e': '🎓', 'd': '50 sessions ecole'})
        if won_bets_count >= 10:
            trophies.append({'n': 'Parieur', 'e': '🎟️', 'd': '10 paris gagnes'})
        if best_odds_hit >= 5.0:
            trophies.append({'n': 'Sniper', 'e': '🎯', 'd': 'Pari gagne a x5+'})
        if best_odds_hit >= 10.0:
            trophies.append({'n': 'Fou Furieux', 'e': '🔥', 'd': 'Pari gagne a x10+'})
        if bet_profit <= -100:
            trophies.append({'n': 'Ruine', 'e': '📉', 'd': 'Perdu plus de 100 🪙 en paris'})
        if legendary_count >= 1:
            trophies.append({'n': 'Collectionneur', 'e': '🟡', 'd': 'Posseder un cochon legendaire'})
        if deaths_sacrifice >= 3:
            trophies.append({'n': 'Sans Pitie', 'e': '🗡️', 'd': '3 cochons sacrifies'})
        if legendary_dead >= 1:
            trophies.append({'n': 'Sacrilege', 'e': '⚱️', 'd': 'Avoir perdu un cochon legendaire'})
        if total_bets > 0 and won_bets_count == 0:
            trophies.append({'n': 'La Poisse', 'e': '🐌', 'd': 'Aucun pari gagne'})
        if win_rate >= 40 and total_races >= 10:
            trophies.append({'n': 'Stratege', 'e': '🧠', 'd': '40%+ win rate (10+ courses)'})
        for trophy in trophies_by_user.get(user.id, []):
            trophies.append({'n': trophy.label, 'e': trophy.emoji, 'd': trophy.description})

        rankings.append({
            'user': user,
            'total_wins': total_wins,
            'total_races': total_races,
            'win_rate': round(win_rate, 1),
            'dead_count': dead_pigs_count,
            'deaths_challenge': deaths_challenge,
            'deaths_blessure': deaths_blessure,
            'deaths_sacrifice': deaths_sacrifice,
            'deaths_vieillesse': deaths_vieillesse,
            'legendary_dead': legendary_dead,
            'total_bets': total_bets,
            'won_bets': won_bets_count,
            'lost_bets': lost_bets_count,
            'total_staked': total_staked,
            'total_winnings': total_winnings,
            'bet_profit': bet_profit,
            'bet_win_rate': bet_win_rate,
            'best_odds_hit': round(best_odds_hit, 1),
            'best_pig': best_pig,
            'max_level': max_level,
            'total_school': total_school,
            'total_xp': total_xp,
            'legendary_count': legendary_count,
            'active_pigs_count': len(active_pigs),
            'total_spent_on_food': total_spent_on_food,
            'total_earned': total_earned,
            'trophies': trophies,
            'score': round(user.balance + (total_wins * 50), 2),
        })

    rankings.sort(key=lambda item: item['score'], reverse=True)

    top_5 = rankings[:5]
    all_labels = [entry['user'].username for entry in rankings]
    chart_data = {
        'labels': [entry['user'].username for entry in top_5],
        'balances': [entry['user'].balance for entry in top_5],
        'wins': [entry['total_wins'] for entry in top_5],
        'dead': [entry['dead_count'] for entry in top_5],
        'all_labels': all_labels,
        'all_dead': [entry['dead_count'] for entry in rankings],
        'all_challenge': [entry['deaths_challenge'] for entry in rankings],
        'all_blessure': [entry['deaths_blessure'] for entry in rankings],
        'all_sacrifice': [entry['deaths_sacrifice'] for entry in rankings],
        'all_vieillesse': [entry['deaths_vieillesse'] for entry in rankings],
        'all_bet_profit': [entry['bet_profit'] for entry in rankings],
        'all_win_rate': [entry['win_rate'] for entry in rankings],
        'all_races': [entry['total_races'] for entry in rankings],
    }

    def best_by(key, reverse=True):
        valid = [entry for entry in rankings if entry.get(key, 0)]
        if not valid:
            return None
        return (max if reverse else min)(valid, key=lambda entry: entry[key])

    awards = []

    top_score = best_by('score')
    if top_score:
        awards.append({'emoji': '👑', 'title': 'Roi du Derby', 'desc': 'Meilleur score global', 'user': top_score['user'].username, 'value': f"{top_score['score']:.0f} pts", 'color': 'yellow'})

    top_wins = best_by('total_wins')
    if top_wins and top_wins['total_wins'] > 0:
        awards.append({'emoji': '🏆', 'title': 'Champion Absolu', 'desc': 'Le plus de victoires', 'user': top_wins['user'].username, 'value': f"{top_wins['total_wins']} victoire(s)", 'color': 'green'})

    most_deaths = best_by('dead_count')
    if most_deaths and most_deaths['dead_count'] > 0:
        awards.append({'emoji': '🔪', 'title': 'Boucher en Chef', 'desc': 'Le plus de cochons morts', 'user': most_deaths['user'].username, 'value': f"{most_deaths['dead_count']} victime(s)", 'color': 'red'})

    challenge_losses = best_by('deaths_challenge')
    if challenge_losses and challenge_losses['deaths_challenge'] > 0:
        awards.append({'emoji': '💀', 'title': 'Kamikaze Supreme', 'desc': 'Le plus de morts au Challenge', 'user': challenge_losses['user'].username, 'value': f"{challenge_losses['deaths_challenge']} sacrifice(s)", 'color': 'purple'})

    top_staked = best_by('total_staked')
    if top_staked and top_staked['total_staked'] > 0:
        awards.append({'emoji': '🎰', 'title': 'Le Flambeur', 'desc': 'Le plus mise au total', 'user': top_staked['user'].username, 'value': f"{top_staked['total_staked']:.0f} 🪙 misés", 'color': 'amber'})

    top_profit = best_by('bet_profit')
    if top_profit and top_profit['bet_profit'] > 0:
        awards.append({'emoji': '🤑', 'title': 'Le Bookmaker', 'desc': 'Le plus gros profit aux paris', 'user': top_profit['user'].username, 'value': f"+{top_profit['bet_profit']:.0f} 🪙", 'color': 'emerald'})

    worst_profit = best_by('bet_profit', reverse=False)
    if worst_profit and worst_profit['bet_profit'] < 0:
        awards.append({'emoji': '📉', 'title': 'Le Pigeon', 'desc': 'Les pires pertes aux paris', 'user': worst_profit['user'].username, 'value': f"{worst_profit['bet_profit']:.0f} 🪙", 'color': 'red'})

    top_school = best_by('total_school')
    if top_school and top_school['total_school'] > 0:
        awards.append({'emoji': '🎓', 'title': "L'Intellectuel", 'desc': 'Le plus de sessions ecole', 'user': top_school['user'].username, 'value': f"{top_school['total_school']} sessions", 'color': 'blue'})

    top_odds = best_by('best_odds_hit')
    if top_odds and top_odds['best_odds_hit'] >= 2.0:
        awards.append({'emoji': '🎯', 'title': 'Le Sniper', 'desc': 'La meilleure cote touchee', 'user': top_odds['user'].username, 'value': f"x{top_odds['best_odds_hit']:.1f}", 'color': 'cyan'})

    top_races = best_by('total_races')
    if top_races and top_races['total_races'] > 0:
        awards.append({'emoji': '🏃', 'title': 'Le Marathonien', 'desc': 'Le plus de courses disputees', 'user': top_races['user'].username, 'value': f"{top_races['total_races']} courses", 'color': 'indigo'})

    top_sacrifice = best_by('deaths_sacrifice')
    if top_sacrifice and top_sacrifice['deaths_sacrifice'] > 0:
        awards.append({'emoji': '🗡️', 'title': 'Sans Pitie', 'desc': 'Le plus de cochons sacrifies', 'user': top_sacrifice['user'].username, 'value': f"{top_sacrifice['deaths_sacrifice']} sacrifice(s)", 'color': 'rose'})

    top_injury_deaths = best_by('deaths_blessure')
    if top_injury_deaths and top_injury_deaths['deaths_blessure'] > 0:
        awards.append({'emoji': '🩹', 'title': 'Le Negligent', 'desc': 'Le plus de morts par blessure non soignee', 'user': top_injury_deaths['user'].username, 'value': f"{top_injury_deaths['deaths_blessure']} victime(s)", 'color': 'orange'})

    top_food_spend = best_by('total_spent_on_food')
    if top_food_spend and top_food_spend['total_spent_on_food'] > 0:
        awards.append({'emoji': '🌽', 'title': 'Le Nourricier', 'desc': 'Le plus depense en nourriture', 'user': top_food_spend['user'].username, 'value': f"{top_food_spend['total_spent_on_food']:.0f} 🪙", 'color': 'lime'})

    top_legendary_losses = best_by('legendary_dead')
    if top_legendary_losses and top_legendary_losses['legendary_dead'] > 0:
        awards.append({'emoji': '⚱️', 'title': 'Le Sacrilege', 'desc': 'Le plus de legendaires perdus', 'user': top_legendary_losses['user'].username, 'value': f"{top_legendary_losses['legendary_dead']} legendaire(s)", 'color': 'fuchsia'})

    top_xp = best_by('total_xp')
    if top_xp and top_xp['total_xp'] > 0:
        awards.append({'emoji': '⭐', 'title': "L'Eleveur Supreme", 'desc': "Le plus d'XP accumulee", 'user': top_xp['user'].username, 'value': f"{top_xp['total_xp']} XP", 'color': 'violet'})

    top_level = best_by('max_level')
    if top_level and top_level['max_level'] > 1:
        awards.append({'emoji': '🔝', 'title': 'Le Maitre', 'desc': 'Cochon au plus haut niveau', 'user': top_level['user'].username, 'value': f"Niv. {top_level['max_level']}", 'color': 'teal'})

    top_earner = best_by('total_earned')
    if top_earner and top_earner['total_earned'] > 0:
        awards.append({'emoji': '💸', 'title': 'La Machine à 🪙', 'desc': 'Le plus de BitGroins gagnes au total', 'user': top_earner['user'].username, 'value': f"{top_earner['total_earned']:.0f} 🪙", 'color': 'emerald'})

    top_retirements = best_by('deaths_vieillesse')
    if top_retirements and top_retirements['deaths_vieillesse'] > 0:
        awards.append({'emoji': '🧓', 'title': 'Eleveur Patient', 'desc': 'Le plus de cochons morts de vieillesse', 'user': top_retirements['user'].username, 'value': f"{top_retirements['deaths_vieillesse']} retraite(s)", 'color': 'sky'})

    losers = [entry for entry in rankings if entry['total_races'] >= 5]
    if losers:
        loser = min(losers, key=lambda entry: entry['win_rate'])
        if loser['win_rate'] < 30:
            awards.append({'emoji': '🐌', 'title': 'Le Looser Officiel', 'desc': 'Pire taux de victoire (5+ courses)', 'user': loser['user'].username, 'value': f"{loser['win_rate']}%", 'color': 'slate'})

    survivors = [entry for entry in rankings if entry['total_races'] >= 10 and entry['dead_count'] == 0]
    if survivors:
        survivor = max(survivors, key=lambda entry: entry['total_races'])
        awards.append({'emoji': '🛡️', 'title': 'Le Survivant', 'desc': 'Le plus de courses sans aucune perte', 'user': survivor['user'].username, 'value': f"{survivor['total_races']} courses, 0 mort", 'color': 'emerald'})

    return {
        'rankings': rankings,
        'chart_data': chart_data,
        'awards': awards,
    }


def _get_bet_net_delta(bet):
    if bet.status == 'won':
        return round(float((bet.winnings or 0.0) - (bet.amount or 0.0)), 2)
    if bet.status == 'lost':
        return round(float(-(bet.amount or 0.0)), 2)
    if bet.status == 'refunded':
        return 0.0
    return None


def _build_bitgroins_curve_context(transactions):
    ordered_transactions = sorted(
        transactions or [],
        key=lambda tx: (
            tx.created_at or datetime.min,
            tx.id or 0,
        ),
    )
    series_by_user = {}
    total_points = 0

    for tx in ordered_transactions:
        if not tx.user:
            continue
        created_at = tx.created_at or datetime.min
        timestamp_ms = int(created_at.timestamp() * 1000)
        username = tx.user.username
        user_series = series_by_user.setdefault(tx.user_id, {
            'user_id': tx.user_id,
            'label': username,
            'points': [],
            'tx_count': 0,
            'peak_balance': None,
            'lowest_balance': None,
            'largest_jump': 0.0,
            'largest_drop': 0.0,
            'current_balance': 0.0,
            'last_at': None,
        })

        balance_after = round(float(tx.balance_after or 0.0), 2)
        amount = round(float(tx.amount or 0.0), 2)
        user_series['points'].append({
            'x': timestamp_ms,
            'y': balance_after,
            'amount': amount,
            'reason': tx.reason_label,
            'date': created_at.strftime('%d/%m/%Y %H:%M'),
        })
        user_series['tx_count'] += 1
        user_series['current_balance'] = balance_after
        user_series['last_at'] = created_at.strftime('%d/%m %H:%M')
        user_series['peak_balance'] = balance_after if user_series['peak_balance'] is None else max(user_series['peak_balance'], balance_after)
        user_series['lowest_balance'] = balance_after if user_series['lowest_balance'] is None else min(user_series['lowest_balance'], balance_after)
        if tx.reason_code != 'snapshot':
            user_series['largest_jump'] = max(user_series['largest_jump'], amount)
            user_series['largest_drop'] = min(user_series['largest_drop'], amount)
        total_points += 1

    rows = sorted(
        (
            {
                'user_id': series['user_id'],
                'label': series['label'],
                'tx_count': series['tx_count'],
                'current_balance': round(series['current_balance'], 2),
                'peak_balance': round(series['peak_balance'] or 0.0, 2),
                'lowest_balance': round(series['lowest_balance'] or 0.0, 2),
                'largest_jump': round(series['largest_jump'], 2),
                'largest_drop': round(series['largest_drop'], 2),
                'last_at': series['last_at'],
            }
            for series in series_by_user.values()
            if series['points']
        ),
        key=lambda row: (-row['current_balance'], row['label'].lower()),
    )

    datasets = [
        {
            'label': series['label'],
            'user_id': series['user_id'],
            'data': series['points'],
        }
        for series in sorted(
            series_by_user.values(),
            key=lambda item: (-(item['current_balance'] or 0.0), item['label'].lower()),
        )
        if series['points']
    ]

    biggest_jump_row = max(rows, key=lambda row: row['largest_jump'], default=None)
    lowest_drop_row = min(rows, key=lambda row: row['largest_drop'], default=None)

    return {
        'datasets': datasets,
        'rows': rows,
        'total_points': total_points,
        'user_count': len(rows),
        'biggest_jump': biggest_jump_row,
        'biggest_drop': lowest_drop_row,
    }


def _build_bet_curve_context(bets):
    ordered_bets = sorted(
        bets or [],
        key=lambda bet: (
            bet.placed_at or datetime.min,
            bet.id or 0,
        ),
    )
    settled_deltas = [
        abs(delta)
        for bet in ordered_bets
        for delta in [_get_bet_net_delta(bet)]
        if delta is not None and abs(delta) > 0
    ]
    suspicious_threshold = 0.0
    if settled_deltas:
        suspicious_threshold = max(150.0, round(float(median(settled_deltas)) * 4, 2))

    series_by_user = {}
    total_points = 0
    for bet in ordered_bets:
        if not bet.user:
            continue
        delta = _get_bet_net_delta(bet)
        if delta is None:
            continue
        created_at = bet.placed_at or datetime.min
        timestamp_ms = int(created_at.timestamp() * 1000)
        username = bet.user.username
        user_series = series_by_user.setdefault(bet.user_id, {
            'user_id': bet.user_id,
            'label': username,
            'points': [],
            'bet_count': 0,
            'settled_count': 0,
            'cumulative_profit': 0.0,
            'peak_profit': 0.0,
            'lowest_profit': 0.0,
            'largest_jump': 0.0,
            'largest_drop': 0.0,
            'last_at': None,
        })
        user_series['bet_count'] += 1
        if bet.status in ('won', 'lost', 'refunded'):
            user_series['settled_count'] += 1
        user_series['cumulative_profit'] = round(user_series['cumulative_profit'] + delta, 2)
        user_series['peak_profit'] = max(user_series['peak_profit'], user_series['cumulative_profit'])
        user_series['lowest_profit'] = min(user_series['lowest_profit'], user_series['cumulative_profit'])
        user_series['largest_jump'] = max(user_series['largest_jump'], delta)
        user_series['largest_drop'] = min(user_series['largest_drop'], delta)
        user_series['last_at'] = created_at.strftime('%d/%m %H:%M')
        user_series['points'].append({
            'x': timestamp_ms,
            'y': user_series['cumulative_profit'],
            'delta': delta,
            'date': created_at.strftime('%d/%m/%Y %H:%M'),
            'bet_label': getattr(getattr(bet, 'outcome_snapshot', None), 'bet_label', bet.bet_type),
            'selection': bet.pig_name,
            'status': bet.status,
        })
        total_points += 1

    rows = []
    for series in series_by_user.values():
        if not series['points']:
            continue
        max_abs_swing = max(abs(series['largest_jump']), abs(series['largest_drop']))
        is_suspicious = bool(suspicious_threshold and max_abs_swing >= suspicious_threshold)
        rows.append({
            'user_id': series['user_id'],
            'label': series['label'],
            'bet_count': series['bet_count'],
            'settled_count': series['settled_count'],
            'cumulative_profit': round(series['cumulative_profit'], 2),
            'peak_profit': round(series['peak_profit'], 2),
            'lowest_profit': round(series['lowest_profit'], 2),
            'largest_jump': round(series['largest_jump'], 2),
            'largest_drop': round(series['largest_drop'], 2),
            'max_abs_swing': round(max_abs_swing, 2),
            'last_at': series['last_at'],
            'is_suspicious': is_suspicious,
        })

    rows.sort(key=lambda row: (-row['cumulative_profit'], row['label'].lower()))
    datasets = [
        {
            'label': series['label'],
            'user_id': series['user_id'],
            'data': series['points'],
            'is_suspicious': next((row['is_suspicious'] for row in rows if row['user_id'] == series['user_id']), False),
        }
        for series in sorted(
            series_by_user.values(),
            key=lambda item: (-(item['cumulative_profit'] or 0.0), item['label'].lower()),
        )
        if series['points']
    ]
    biggest_jump_row = max(rows, key=lambda row: row['largest_jump'], default=None)
    biggest_drop_row = min(rows, key=lambda row: row['largest_drop'], default=None)

    return {
        'datasets': datasets,
        'rows': rows,
        'total_points': total_points,
        'user_count': len(rows),
        'biggest_jump': biggest_jump_row,
        'biggest_drop': biggest_drop_row,
        'suspicious_threshold': suspicious_threshold,
        'suspicious_count': sum(1 for row in rows if row['is_suspicious']),
    }


def _normalize_selected_user_ids(raw_values):
    selected_ids = []
    for raw_value in raw_values or []:
        if raw_value == 'all':
            return []
        try:
            selected_ids.append(int(raw_value))
        except (TypeError, ValueError):
            continue
    return sorted(set(selected_ids))


def build_history_page_context(current_user_id, view_user_id=None, bet_filter_values=None, tx_filter_values=None):
    current_user = User.query.get(current_user_id)
    target_user = User.query.get(view_user_id or current_user.id) if current_user else None
    if not target_user:
        target_user = current_user

    all_users = User.query.order_by(User.username).all()

    bet_filter_raw = 'all'
    bet_filter_user = None
    bet_filter_users = []
    bet_query = Bet.query.order_by(Bet.placed_at.desc(), Bet.id.desc())

    bet_selected_user_ids = _normalize_selected_user_ids(bet_filter_values)
    if bet_selected_user_ids:
        bet_filter_users = User.query.filter(User.id.in_(bet_selected_user_ids)).order_by(User.username).all()
        bet_selected_user_ids = [user.id for user in bet_filter_users]
        if bet_selected_user_ids:
            bet_query = bet_query.filter(Bet.user_id.in_(bet_selected_user_ids))
            bet_filter_raw = 'multi'
            bet_filter_user = bet_filter_users[0] if len(bet_filter_users) == 1 else None

    bets = bet_query.all()
    attach_bet_outcome_snapshots(bets)
    bet_curve = _build_bet_curve_context(bets)

    tx_filter_raw = 'all'
    tx_filter_user = None
    tx_filter_users = []
    tx_query = BalanceTransaction.query.order_by(BalanceTransaction.created_at.desc(), BalanceTransaction.id.desc())

    tx_selected_user_ids = _normalize_selected_user_ids(tx_filter_values)
    if tx_selected_user_ids:
        tx_filter_users = User.query.filter(User.id.in_(tx_selected_user_ids)).order_by(User.username).all()
        tx_selected_user_ids = [user.id for user in tx_filter_users]
        if tx_selected_user_ids:
            tx_query = tx_query.filter(BalanceTransaction.user_id.in_(tx_selected_user_ids))
            tx_filter_raw = 'multi'
            tx_filter_user = tx_filter_users[0] if len(tx_filter_users) == 1 else None

    transactions = tx_query.all()
    bitgroins_curve = _build_bitgroins_curve_context(transactions)
    race_history = get_race_history_entries()

    won_bets = [bet for bet in bets if bet.status == 'won']
    lost_bets = [bet for bet in bets if bet.status == 'lost']
    settled_bets = won_bets + lost_bets
    credited_amount = round(
        sum(tx.amount for tx in transactions if tx.amount > 0 and tx.reason_code != 'snapshot'),
        2,
    )
    debited_amount = round(
        sum(abs(tx.amount) for tx in transactions if tx.amount < 0 and tx.reason_code != 'snapshot'),
        2,
    )

    return {
        'user': current_user,
        'target_user': target_user,
        'all_users': all_users,
        'bets': bets,
        'won_bets': won_bets,
        'lost_bets': lost_bets,
        'settled_bets': settled_bets,
        'bet_filter_raw': bet_filter_raw,
        'bet_filter_user': bet_filter_user,
        'bet_filter_users': bet_filter_users,
        'bet_selected_user_ids': bet_selected_user_ids,
        'bet_curve': bet_curve,
        'transactions': transactions,
        'bitgroins_curve': bitgroins_curve,
        'tx_filter_raw': tx_filter_raw,
        'tx_filter_user': tx_filter_user,
        'tx_filter_users': tx_filter_users,
        'tx_selected_user_ids': tx_selected_user_ids,
        'race_history': race_history,
        'bet_types': get_configured_bet_types(),
        'credited_amount': credited_amount,
        'debited_amount': debited_amount,
    }
