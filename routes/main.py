from flask import Blueprint, render_template, redirect, url_for, session, flash, request
from sqlalchemy import func
from datetime import datetime
import time

from data import (
    BOURSE_GRID_SIZE,
    BOURSE_MIN_MOVEMENT,
    BOURSE_MOVEMENT_DIVISOR,
    COMPLEX_BET_MIN_SELECTIONS,
    MAX_INJURY_RISK,
    MAX_PIG_SLOTS,
    MIN_INJURY_RISK,
    RETIREMENT_HERITAGE_MIN_WINS,
    SCHOOL_COOLDOWN_MINUTES,
    SNACK_SHARE_DAILY_LIMIT,
    STAT_LABELS,
    VET_RESPONSE_MINUTES,
)
from extensions import db
from models import User, Pig, Race, Participant, Bet, BalanceTransaction, CoursePlan, Trophy
from helpers import (
    ensure_next_race,
    get_cereals_dict,
    get_race_history_entries,
    get_school_lessons_dict,
    get_trainings_dict,
    get_user_active_pigs,
)
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
from services.market_service import get_prix_moyen_groin, is_market_open, get_next_market_time
from services.pig_service import calculate_pig_power, get_weight_profile
from services.race_service import get_pig_dashboard_status, build_course_schedule, get_user_weekly_bet_count, get_course_theme

main_bp = Blueprint('main', __name__)

# ── Cache classement (5 min TTL) ─────────────────────────────────────────
_classement_cache = {'data': None, 'ts': 0}
_CLASSEMENT_TTL = 300  # 5 minutes


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


def _build_rules_page_context():
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
        {'label': 'Fenêtre vétérinaire', 'value': f"{VET_RESPONSE_MINUTES} min", 'note': "Au-delà, le cochon peut mourir."},
        {
            'label': 'Mise par ticket',
            'value': f"{bet_limits['min_bet_race']:.0f} à {bet_limits['max_bet_race']:.0f} 🪙",
            'note': f"Cap payout : {bet_limits['max_payout_race']:.0f} 🪙" if bet_limits['max_payout_race'] > 0 else "Pas de cap payout actif.",
        },
    ]

    adoption_rows = []
    for active_count in range(MAX_PIG_SLOTS):
        adoption_rows.append({
            'label': f"Passer à {active_count + 1} cochon{'s' if active_count + 1 > 1 else ''}",
            'cost': get_adoption_cost_for_active_count(active_count, settings=economy),
        })

    feeding_rows = []
    for active_count in range(1, MAX_PIG_SLOTS + 1):
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
                "Toute interaction positive utile remet la fraîcheur à 100. Un retour après plus de 3 jours prépare même un petit bonus comeback pour la prochaine course.",
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
                f"Le risque de blessure est maintenant borné entre {MIN_INJURY_RISK:.0f}% et {MAX_INJURY_RISK:.0f}% avant modificateurs.",
                "Les 8 premières courses bénéficient d’une vraie protection de début de carrière: le risque réel monte progressivement pour éviter les morts absurdes trop tôt.",
                "Fatigue, faim et mauvais poids aggravent ensuite ce risque à chaque arrivée.",
                f"En cas de blessure, le cochon est bloqué pour les courses, l’entraînement, l’école et le Challenge de la Mort tant qu’il n’est pas soigné. La fenêtre vétérinaire active est de {VET_RESPONSE_MINUTES} minutes.",
                f"Une opération réussie réduit maintenant le risque de blessure du cochon de 2 points et coûte {progression.vet_energy_cost:.0f} énergie / {progression.vet_happiness_cost:.0f} humeur.",
                f"Un champion peut aussi quitter la piste volontairement en retraite d’honneur dès {RETIREMENT_HERITAGE_MIN_WINS} victoires, ou immédiatement s’il est légendaire.",
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
                f"Le deuxième cochon et les suivants coûtent de plus en plus cher. La porcherie est plafonnée à {MAX_PIG_SLOTS} cochons.",
                f"La portée coûte actuellement {economy.breeding_cost:.0f} 🪙 et mélange stats, origine, rareté et lignée des parents.",
                f"Chaque cochon supplémentaire augmente le coût de nourrissage de +{economy.feeding_pressure_per_pig * 100:.0f}% sur tous les achats.",
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
                "Truffes est un revenu d’appoint gratuit sur 7 clics.",
                "Groin Jack consomme des BitGroins comme un vrai mini-casino parallèle.",
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


@main_bp.route('/')
def index():
    next_race = Race.query.filter(Race.status == 'open').order_by(Race.scheduled_at).first()
    if not next_race:
        ensure_next_race()
        next_race = Race.query.filter(Race.status == 'open').order_by(Race.scheduled_at).first()
    recent_races = Race.query.filter_by(status='finished').order_by(Race.finished_at.desc()).limit(5).all()

    user = None
    user_bets = []
    pigs = []
    pigs_data = []
    week_slots = []
    featured_pig = None
    featured_pig_status = None
    headline_status = None
    weekly_bacon_tickets = get_weekly_bacon_tickets_value()
    bet_types = get_configured_bet_types()
    bacon_tickets_remaining = weekly_bacon_tickets
    latest_race = recent_races[0] if recent_races else None
    latest_race_participants = []
    news_items = []
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            # --- Prime de pointage journalière ---
            reward = user.claim_daily_reward()
            if reward > 0:
                db.session.commit()
                flash(f"🎁 Prime de pointage : Vous avez reçu {reward:.0f} 🪙 BitGroins pour votre première connexion de la journée !", "success")

            pigs = get_user_active_pigs(user)
            for pig in pigs:
                pig.update_vitals()
            pigs_data = [{
                'pig': pig,
                'power': round(calculate_pig_power(pig), 1),
                'weight_profile': get_weight_profile(pig),
                'dashboard': get_pig_dashboard_status(pig),
            } for pig in pigs]
            week_slots = build_course_schedule(user, pigs, days=7)
            weekly_bet_count = get_user_weekly_bet_count(user, datetime.now())
            bacon_tickets_remaining = max(0, weekly_bacon_tickets - weekly_bet_count)
            if next_race:
                user_bets = Bet.query.filter_by(user_id=user.id, race_id=next_race.id).all()

    participants = []
    if next_race:
        participants = Participant.query.filter_by(race_id=next_race.id).order_by(Participant.odds).all()
    participants_by_pig_id = {participant.pig_id: participant for participant in participants if participant.pig_id}

    if latest_race:
        latest_race_participants = Participant.query.filter_by(race_id=latest_race.id).order_by(Participant.finish_position).all()

    if pigs_data:
        featured_candidates = [entry for entry in pigs_data if entry['pig'].id in participants_by_pig_id]
        featured_pig = (featured_candidates[0] if featured_candidates else pigs_data[0])
        featured_pig_status = featured_pig['dashboard']
        featured_pig_obj = featured_pig['pig']
        participant = participants_by_pig_id.get(featured_pig_obj.id)
        if participant:
            headline_status = {
                'participates': True,
                'label': f"{featured_pig_obj.emoji} {featured_pig_obj.name} y participe !",
                'subtext': f"Cote actuelle x{participant.odds:.1f}. {featured_pig_status['rest_label']}.",
                'tone': 'success',
            }
        else:
            next_plan = (
                CoursePlan.query
                .filter(CoursePlan.user_id == user.id, CoursePlan.pig_id == featured_pig_obj.id, CoursePlan.scheduled_at >= datetime.now())
                .order_by(CoursePlan.scheduled_at.asc())
                .first()
            )
            if next_plan:
                plan_label = next_plan.scheduled_at.strftime('%d/%m %H:%M')
                headline_status = {
                    'participates': False,
                    'label': f"📅 {featured_pig_obj.name} vise le {plan_label}",
                    'subtext': featured_pig_status['rest_note'],
                    'tone': 'planned',
                }
            else:
                headline_status = {
                    'participates': False,
                    'label': f"💤 {featured_pig_obj.name} se repose",
                    'subtext': featured_pig_status['rest_note'],
                    'tone': 'rest',
                }

    injured_pig = Pig.query.filter_by(is_alive=True, is_injured=True).order_by(Pig.vet_deadline.asc(), Pig.id.asc()).first()
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

    week_race_cards = week_slots[:5] if week_slots else []
    next_race_theme = get_course_theme(next_race.scheduled_at) if next_race else None

    prix_groin = get_prix_moyen_groin()

    return render_template('index.html',
        user=user, pigs=pigs, next_race=next_race,
        participants=participants, recent_races=recent_races,
        user_bets=user_bets, now=datetime.now(),
        bet_types=bet_types,
        prix_groin=prix_groin,
        market_open=is_market_open(),
        next_market=get_next_market_time(),
        featured_pig=featured_pig,
        featured_pig_status=featured_pig_status,
        headline_status=headline_status,
        bacon_tickets_remaining=bacon_tickets_remaining,
        weekly_bacon_tickets=weekly_bacon_tickets,
        week_race_cards=week_race_cards,
        next_race_theme=next_race_theme,
        latest_race=latest_race,
        latest_race_participants=latest_race_participants,
        news_items=news_items[:3],
    )


@main_bp.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    current_user = User.query.get(session['user_id'])
    view_user_id = request.args.get('u', type=int) or current_user.id
    target_user = User.query.get(view_user_id)
    
    if not target_user:
        target_user = current_user
    
    all_users = User.query.order_by(User.username).all()
    
    bets = Bet.query.filter_by(user_id=target_user.id).order_by(Bet.placed_at.desc()).all()
    transactions = BalanceTransaction.query.filter_by(user_id=target_user.id).order_by(BalanceTransaction.created_at.desc(), BalanceTransaction.id.desc()).all()
    
    global_transactions = []
    if current_user.is_admin:
        global_transactions = BalanceTransaction.query.order_by(BalanceTransaction.created_at.desc(), BalanceTransaction.id.desc()).all()

    race_history = get_race_history_entries()

    won_bets = [bet for bet in bets if bet.status == 'won']
    lost_bets = [bet for bet in bets if bet.status == 'lost']
    settled_bets = won_bets + lost_bets
    credited_amount = round(sum(tx.amount for tx in transactions if tx.amount > 0 and tx.reason_code != 'snapshot'), 2)
    debited_amount = round(sum(abs(tx.amount) for tx in transactions if tx.amount < 0 and tx.reason_code != 'snapshot'), 2)

    return render_template(
        'history.html',
        user=current_user,
        target_user=target_user,
        all_users=all_users,
        bets=bets,
        won_bets=won_bets,
        lost_bets=lost_bets,
        settled_bets=settled_bets,
        transactions=transactions,
        global_transactions=global_transactions,
        race_history=race_history,
        bet_types=get_configured_bet_types(),
        credited_amount=credited_amount,
        debited_amount=debited_amount,
    )


def _build_classement_data():
    """Build rankings, chart_data and awards. Cached for 5 min."""
    all_users = User.query.all()
    user_ids = [u.id for u in all_users]

    # ── Batch: stats courses par user (1 query) ────────────────────────
    pig_stats_rows = (
        db.session.query(
            Pig.user_id,
            func.coalesce(func.sum(Pig.races_won), 0),
            func.coalesce(func.sum(Pig.races_entered), 0),
        )
        .filter(Pig.user_id.in_(user_ids))
        .group_by(Pig.user_id)
        .all()
    )
    pig_stats = {uid: (int(w), int(r)) for uid, w, r in pig_stats_rows}

    # ── Batch: tous les cochons (1 query) ──────────────────────────────
    all_pigs_list = Pig.query.filter(Pig.user_id.in_(user_ids)).all()
    pigs_by_user = {}
    for p in all_pigs_list:
        pigs_by_user.setdefault(p.user_id, []).append(p)

    # ── Batch: stats paris par user (1 query) ──────────────────────────
    bet_stats_rows = (
        db.session.query(
            Bet.user_id,
            Bet.status,
            func.count(Bet.id),
            func.coalesce(func.sum(Bet.amount), 0.0),
            func.coalesce(func.sum(Bet.winnings), 0.0),
            func.max(db.case((Bet.status == 'won', Bet.odds_at_bet), else_=0.0)),
        )
        .filter(Bet.user_id.in_(user_ids))
        .group_by(Bet.user_id, Bet.status)
        .all()
    )
    bet_stats = {}
    for uid, status, count, staked, winnings, best_odds in bet_stats_rows:
        entry = bet_stats.setdefault(uid, {
            'total': 0, 'won': 0, 'lost': 0, 'staked': 0.0,
            'winnings': 0.0, 'won_staked': 0.0, 'lost_staked': 0.0,
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

    # ── Batch: depenses nourriture & gains par user (2 queries) ────────
    food_rows = (
        db.session.query(
            BalanceTransaction.user_id,
            func.coalesce(func.sum(func.abs(BalanceTransaction.amount)), 0.0),
        )
        .filter(
            BalanceTransaction.user_id.in_(user_ids),
            BalanceTransaction.reason_code == 'feed_purchase',
        )
        .group_by(BalanceTransaction.user_id)
        .all()
    )
    food_spent = {uid: round(float(v), 2) for uid, v in food_rows}

    earned_rows = (
        db.session.query(
            BalanceTransaction.user_id,
            func.coalesce(func.sum(BalanceTransaction.amount), 0.0),
        )
        .filter(
            BalanceTransaction.user_id.in_(user_ids),
            BalanceTransaction.amount > 0,
            BalanceTransaction.reason_code != 'snapshot',
        )
        .group_by(BalanceTransaction.user_id)
        .all()
    )
    total_earned_map = {uid: round(float(v), 2) for uid, v in earned_rows}

    # ── Batch: trophees memorial par user (1 query) ────────────────────
    all_trophies = Trophy.query.filter(Trophy.user_id.in_(user_ids)).order_by(Trophy.earned_at.asc()).all()
    trophies_by_user = {}
    for t in all_trophies:
        trophies_by_user.setdefault(t.user_id, []).append(t)

    # ── Construction du classement ─────────────────────────────────────
    rankings = []
    for u in all_users:
        total_wins, total_races = pig_stats.get(u.id, (0, 0))
        win_rate = (total_wins / total_races * 100) if total_races > 0 else 0

        user_pigs = pigs_by_user.get(u.id, [])
        dead_pigs = [p for p in user_pigs if not p.is_alive]
        dead_pigs_count = len([p for p in dead_pigs if p.death_cause != 'vendu'])
        deaths_by_cause = {}
        for p in dead_pigs:
            if p.death_cause and p.death_cause != 'vendu':
                deaths_by_cause[p.death_cause] = deaths_by_cause.get(p.death_cause, 0) + 1
        deaths_challenge = deaths_by_cause.get('challenge', 0)
        deaths_blessure = deaths_by_cause.get('blessure', 0)
        deaths_sacrifice = deaths_by_cause.get('sacrifice_volontaire', 0) + deaths_by_cause.get('sacrifice', 0)
        deaths_vieillesse = deaths_by_cause.get('vieillesse', 0)
        legendary_dead = sum(1 for p in dead_pigs if p.death_cause != 'vendu' and (p.races_won or 0) >= 3)

        bs = bet_stats.get(u.id, {
            'total': 0, 'won': 0, 'lost': 0, 'staked': 0.0,
            'winnings': 0.0, 'won_staked': 0.0, 'lost_staked': 0.0,
            'best_odds': 0.0,
        })
        total_bets = bs['total']
        won_bets_count = bs['won']
        lost_bets_count = bs['lost']
        total_staked = round(bs['staked'], 2)
        total_winnings = round(bs['winnings'], 2)
        settled_staked = bs['won_staked'] + bs['lost_staked']
        bet_profit = round(total_winnings - settled_staked, 2)
        settled_count = won_bets_count + lost_bets_count
        bet_win_rate = round((won_bets_count / settled_count) * 100, 1) if settled_count else 0.0
        best_odds_hit = bs['best_odds']

        active_pigs = [p for p in user_pigs if p.is_alive]
        best_pig = max(user_pigs, key=lambda p: (p.races_won or 0, p.level or 0), default=None)
        max_level = max((p.level or 1 for p in user_pigs), default=1)
        total_school = sum(p.school_sessions_completed or 0 for p in user_pigs)
        total_xp = sum(p.xp or 0 for p in user_pigs)
        legendary_count = sum(1 for p in user_pigs if p.rarity == 'legendaire')

        total_spent_on_food = food_spent.get(u.id, 0.0)
        total_earned = total_earned_map.get(u.id, 0.0)

        # --- Trophees ---
        trophies = []
        if u.balance >= 500: trophies.append({'n': 'Cresus', 'e': '💰', 'd': 'Plus de 500 🪙 en caisse'})
        if u.balance >= 1000: trophies.append({'n': 'Oligarque', 'e': '👑', 'd': 'Plus de 1000 🪙 en caisse'})
        if total_wins >= 10: trophies.append({'n': 'Legende', 'e': '🏆', 'd': '10 victoires au total'})
        if total_wins >= 25: trophies.append({'n': 'Dynastie', 'e': '🏛️', 'd': '25 victoires au total'})
        if dead_pigs_count >= 5: trophies.append({'n': 'Boucher', 'e': '🔪', 'd': '5 cochons morts'})
        if dead_pigs_count >= 10: trophies.append({'n': 'Equarrisseur', 'e': '💀', 'd': '10 cochons morts'})
        if total_races >= 50: trophies.append({'n': 'Veteran', 'e': '🎖️', 'd': '50 courses disputees'})
        if total_races >= 100: trophies.append({'n': 'Marathonien', 'e': '🏃', 'd': '100 courses disputees'})
        if deaths_challenge >= 3: trophies.append({'n': 'Kamikaze', 'e': '💣', 'd': '3 cochons morts au Challenge'})
        if deaths_blessure >= 3: trophies.append({'n': 'Negligent', 'e': '🩹', 'd': '3 cochons morts par blessure'})
        if deaths_vieillesse >= 2: trophies.append({'n': 'Eleveur Sage', 'e': '🧓', 'd': '2 cochons morts de vieillesse'})
        if total_school >= 20: trophies.append({'n': 'Pedagogue', 'e': '📚', 'd': '20 sessions ecole'})
        if total_school >= 50: trophies.append({'n': 'Doyen', 'e': '🎓', 'd': '50 sessions ecole'})
        if won_bets_count >= 10: trophies.append({'n': 'Parieur', 'e': '🎟️', 'd': '10 paris gagnes'})
        if best_odds_hit >= 5.0: trophies.append({'n': 'Sniper', 'e': '🎯', 'd': 'Pari gagne a x5+'})
        if best_odds_hit >= 10.0: trophies.append({'n': 'Fou Furieux', 'e': '🔥', 'd': 'Pari gagne a x10+'})
        if bet_profit <= -100: trophies.append({'n': 'Ruine', 'e': '📉', 'd': 'Perdu plus de 100 🪙 en paris'})
        if legendary_count >= 1: trophies.append({'n': 'Collectionneur', 'e': '🟡', 'd': 'Posseder un cochon legendaire'})
        if deaths_sacrifice >= 3: trophies.append({'n': 'Sans Pitie', 'e': '🗡️', 'd': '3 cochons sacrifies'})
        if legendary_dead >= 1: trophies.append({'n': 'Sacrilege', 'e': '⚱️', 'd': 'Avoir perdu un cochon legendaire'})
        if total_bets > 0 and won_bets_count == 0: trophies.append({'n': 'La Poisse', 'e': '🐌', 'd': 'Aucun pari gagne'})
        if win_rate >= 40 and total_races >= 10: trophies.append({'n': 'Stratege', 'e': '🧠', 'd': '40%+ win rate (10+ courses)'})
        for trophy in trophies_by_user.get(u.id, []):
            trophies.append({'n': trophy.label, 'e': trophy.emoji, 'd': trophy.description})

        rankings.append({
            'user': u,
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
            'score': round(u.balance + (total_wins * 50), 2),
        })

    rankings.sort(key=lambda x: x['score'], reverse=True)

    # --- Charts top 5 ---
    top_5 = rankings[:5]
    all_labels = [r['user'].username for r in rankings]
    chart_data = {
        'labels': [r['user'].username for r in top_5],
        'balances': [r['user'].balance for r in top_5],
        'wins': [r['total_wins'] for r in top_5],
        'dead': [r['dead_count'] for r in top_5],
        'all_labels': all_labels,
        'all_dead': [r['dead_count'] for r in rankings],
        'all_challenge': [r['deaths_challenge'] for r in rankings],
        'all_blessure': [r['deaths_blessure'] for r in rankings],
        'all_sacrifice': [r['deaths_sacrifice'] for r in rankings],
        'all_vieillesse': [r['deaths_vieillesse'] for r in rankings],
        'all_bet_profit': [r['bet_profit'] for r in rankings],
        'all_win_rate': [r['win_rate'] for r in rankings],
        'all_races': [r['total_races'] for r in rankings],
    }

    # --- Awards speciaux ---
    def best_by(key, reverse=True):
        valid = [r for r in rankings if r.get(key, 0)]
        if not valid:
            return None
        return (max if reverse else min)(valid, key=lambda r: r[key])

    awards = []

    a = best_by('score')
    if a: awards.append({'emoji': '👑', 'title': 'Roi du Derby', 'desc': 'Meilleur score global', 'user': a['user'].username, 'value': f"{a['score']:.0f} pts", 'color': 'yellow'})

    a = best_by('total_wins')
    if a and a['total_wins'] > 0: awards.append({'emoji': '🏆', 'title': 'Champion Absolu', 'desc': 'Le plus de victoires', 'user': a['user'].username, 'value': f"{a['total_wins']} victoire(s)", 'color': 'green'})

    a = best_by('dead_count')
    if a and a['dead_count'] > 0: awards.append({'emoji': '🔪', 'title': 'Boucher en Chef', 'desc': 'Le plus de cochons morts', 'user': a['user'].username, 'value': f"{a['dead_count']} victime(s)", 'color': 'red'})

    a = best_by('deaths_challenge')
    if a and a['deaths_challenge'] > 0: awards.append({'emoji': '💀', 'title': 'Kamikaze Supreme', 'desc': 'Le plus de morts au Challenge', 'user': a['user'].username, 'value': f"{a['deaths_challenge']} sacrifice(s)", 'color': 'purple'})

    a = best_by('total_staked')
    if a and a['total_staked'] > 0: awards.append({'emoji': '🎰', 'title': 'Le Flambeur', 'desc': 'Le plus mise au total', 'user': a['user'].username, 'value': f"{a['total_staked']:.0f} 🪙 misés", 'color': 'amber'})

    a = best_by('bet_profit')
    if a and a['bet_profit'] > 0: awards.append({'emoji': '🤑', 'title': 'Le Bookmaker', 'desc': 'Le plus gros profit aux paris', 'user': a['user'].username, 'value': f"+{a['bet_profit']:.0f} 🪙", 'color': 'emerald'})

    a = best_by('bet_profit', reverse=False)
    if a and a['bet_profit'] < 0: awards.append({'emoji': '📉', 'title': 'Le Pigeon', 'desc': 'Les pires pertes aux paris', 'user': a['user'].username, 'value': f"{a['bet_profit']:.0f} 🪙", 'color': 'red'})

    a = best_by('total_school')
    if a and a['total_school'] > 0: awards.append({'emoji': '🎓', 'title': "L'Intellectuel", 'desc': 'Le plus de sessions ecole', 'user': a['user'].username, 'value': f"{a['total_school']} sessions", 'color': 'blue'})

    a = best_by('best_odds_hit')
    if a and a['best_odds_hit'] >= 2.0: awards.append({'emoji': '🎯', 'title': 'Le Sniper', 'desc': 'La meilleure cote touchee', 'user': a['user'].username, 'value': f"x{a['best_odds_hit']:.1f}", 'color': 'cyan'})

    a = best_by('total_races')
    if a and a['total_races'] > 0: awards.append({'emoji': '🏃', 'title': 'Le Marathonien', 'desc': 'Le plus de courses disputees', 'user': a['user'].username, 'value': f"{a['total_races']} courses", 'color': 'indigo'})

    a = best_by('deaths_sacrifice')
    if a and a['deaths_sacrifice'] > 0: awards.append({'emoji': '🗡️', 'title': 'Sans Pitie', 'desc': 'Le plus de cochons sacrifies', 'user': a['user'].username, 'value': f"{a['deaths_sacrifice']} sacrifice(s)", 'color': 'rose'})

    a = best_by('deaths_blessure')
    if a and a['deaths_blessure'] > 0: awards.append({'emoji': '🩹', 'title': 'Le Negligent', 'desc': 'Le plus de morts par blessure non soignee', 'user': a['user'].username, 'value': f"{a['deaths_blessure']} victime(s)", 'color': 'orange'})

    a = best_by('total_spent_on_food')
    if a and a['total_spent_on_food'] > 0: awards.append({'emoji': '🌽', 'title': 'Le Nourricier', 'desc': 'Le plus depense en nourriture', 'user': a['user'].username, 'value': f"{a['total_spent_on_food']:.0f} 🪙", 'color': 'lime'})

    a = best_by('legendary_dead')
    if a and a['legendary_dead'] > 0: awards.append({'emoji': '⚱️', 'title': 'Le Sacrilege', 'desc': 'Le plus de legendaires perdus', 'user': a['user'].username, 'value': f"{a['legendary_dead']} legendaire(s)", 'color': 'fuchsia'})

    a = best_by('total_xp')
    if a and a['total_xp'] > 0: awards.append({'emoji': '⭐', 'title': "L'Eleveur Supreme", 'desc': 'Le plus d\'XP accumulee', 'user': a['user'].username, 'value': f"{a['total_xp']} XP", 'color': 'violet'})

    a = best_by('max_level')
    if a and a['max_level'] > 1: awards.append({'emoji': '🔝', 'title': 'Le Maitre', 'desc': 'Cochon au plus haut niveau', 'user': a['user'].username, 'value': f"Niv. {a['max_level']}", 'color': 'teal'})

    a = best_by('total_earned')
    if a and a['total_earned'] > 0: awards.append({'emoji': '💸', 'title': 'La Machine à 🪙', 'desc': 'Le plus de BitGroins gagnes au total', 'user': a['user'].username, 'value': f"{a['total_earned']:.0f} 🪙", 'color': 'emerald'})

    a = best_by('deaths_vieillesse')
    if a and a['deaths_vieillesse'] > 0: awards.append({'emoji': '🧓', 'title': 'Eleveur Patient', 'desc': 'Le plus de cochons morts de vieillesse', 'user': a['user'].username, 'value': f"{a['deaths_vieillesse']} retraite(s)", 'color': 'sky'})

    # Le Looser: worst win rate with at least some races
    losers = [r for r in rankings if r['total_races'] >= 5]
    if losers:
        loser = min(losers, key=lambda r: r['win_rate'])
        if loser['win_rate'] < 30:
            awards.append({'emoji': '🐌', 'title': 'Le Looser Officiel', 'desc': 'Pire taux de victoire (5+ courses)', 'user': loser['user'].username, 'value': f"{loser['win_rate']}%", 'color': 'slate'})

    # Le Survivant: most races with no deaths
    survivors = [r for r in rankings if r['total_races'] >= 10 and r['dead_count'] == 0]
    if survivors:
        survivor = max(survivors, key=lambda r: r['total_races'])
        awards.append({'emoji': '🛡️', 'title': 'Le Survivant', 'desc': 'Le plus de courses sans aucune perte', 'user': survivor['user'].username, 'value': f"{survivor['total_races']} courses, 0 mort", 'color': 'emerald'})

    return rankings, chart_data, awards


@main_bp.route('/classement')
def classement():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])

    now = time.time()
    if _classement_cache['data'] and (now - _classement_cache['ts']) < _CLASSEMENT_TTL:
        rankings, chart_data, awards = _classement_cache['data']
    else:
        rankings, chart_data, awards = _build_classement_data()
        _classement_cache['data'] = (rankings, chart_data, awards)
        _classement_cache['ts'] = now

    return render_template('classement.html', user=user, rankings=rankings, chart_data=chart_data, awards=awards, active_page='classement')


@main_bp.route('/regles')
def regles():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])

    return render_template(
        'regles.html',
        user=user,
        active_page='regles',
        **_build_rules_page_context(),
    )


@main_bp.route('/legendes-pop')
def legendes_pop():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])

    pop_pigs = [
        {"name": "Porky Pig", "emoji": "🎩", "desc": "Le pionnier. A transformé un bégaiement en une carrière légendaire.", "category": "Stars du Marché"},
        {"name": "Miss Piggy", "emoji": "🎀", "desc": "Influenceuse avant Instagram. Mélange unique de glamour et de violence passive-agressive.", "category": "Stars du Marché"},
        {"name": "Peppa Pig", "emoji": "☔", "desc": "CEO d\u2019un empire mondial basé sur des grognements et des flaques de boue.", "category": "Stars du Marché"},
        {"name": "Porcinet", "emoji": "🧣", "desc": "12 kg de stress, mais validé émotionnellement par toute une génération.", "category": "Stars du Marché"},
        {"name": "Napoléon", "emoji": "👑", "desc": "Commence comme cochon, finit comme manager toxique (La Ferme des Animaux).", "category": "Niveau Dangereux"},
        {"name": "Porco Rosso", "emoji": "🛩️", "desc": "Pilote, philosophe, cochon. Trois problèmes complexes en un seul groin.", "category": "Niveau Dangereux"},
        {"name": "Cochons (Pink Floyd)", "emoji": "🎸", "desc": "Métaphore officielle des élites. Entrée validée par guitare électrique.", "category": "Niveau Dangereux"},
        {"name": "Tête de cochon", "emoji": "💀", "desc": "Quand un cochon mort devient plus charismatique que les humains (Sa Majesté des Mouches).", "category": "Niveau Dangereux"},
        {"name": "Cochon Minecraft", "emoji": "🧊", "desc": "Moyen de transport discutable. Existe principalement pour être transformé en côtelette.", "category": "Quotidien Suspect"},
        {"name": "Cochons Verts", "emoji": "🤢", "desc": "Ingénieurs en structures inefficaces (Angry Birds).", "category": "Quotidien Suspect"},
        {"name": "Hog Rider", "emoji": "🔨", "desc": "Un homme qui crie sur un cochon. Personne ne remet ça en question.", "category": "Quotidien Suspect"},
        {"name": "Hamm / Bayonne", "emoji": "🪙", "desc": "Tirelire cynique de Toy Story. Le seul qui comprend réellement l\u2019économie.", "category": "Quotidien Suspect"},
        {"name": "Nif-Nif, Naf-Naf & Nouf-Nouf", "emoji": "🏠", "desc": "Trois approches du BTP. Une seule résiste réellement au souffle du loup.", "category": "Patrimoine"},
        {"name": "Babe", "emoji": "🐑", "desc": "Le seul cochon avec un plan de carrière et une reconversion réussie.", "category": "Patrimoine"},
        {"name": "Wilbur", "emoji": "🕸️", "desc": "Sauvé par une araignée (Charlotte) meilleure en communication de crise que lui.", "category": "Patrimoine"},
        {"name": "Peter Pig", "emoji": "⚓", "desc": "Preuve que même chez Disney, certains cochons n\u2019ont pas percé.", "category": "Patrimoine"},
        {"name": "Petunia Pig", "emoji": "👒", "desc": "Love interest officielle. Un potentiel inexploité par les studios.", "category": "Secondaires"},
        {"name": "Piggy (Merrie Melodies)", "emoji": "🤡", "desc": "Version bêta de Porky Pig. A servi de crash-test pour l\u2019humour.", "category": "Secondaires"},
        {"name": "Arnold Ziffel", "emoji": "📺", "desc": "Cochon traité comme un humain complet. Personne ne pose de questions.", "category": "Secondaires"},
        {"name": "Pumbaa", "emoji": "🐗", "desc": "Techniquement un phacochère. Accepté dans la base pour raisons administratives.", "category": "Secondaires"},
    ]
    return render_template('legendes_pop.html', user=user, pop_pigs=pop_pigs)
