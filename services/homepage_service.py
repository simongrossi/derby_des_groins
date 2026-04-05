from datetime import datetime

from extensions import db
from helpers.race import ensure_next_race, get_user_active_pigs
from models import BalanceTransaction, Bet, CoursePlan, Participant, Pig, Race, User, UserCerealInventory
from services.economy_service import get_configured_bet_types, get_weekly_bacon_tickets_value
from services.finance_service import claim_daily_reward
from services.market_service import get_next_market_time, get_prix_moyen_groin, is_market_open
from services.pig_power_service import calculate_pig_power, get_weight_profile
from services.pig_service import recommend_best_cereal, update_pig_vitals
from services.race_service import (
    build_course_schedule,
    get_course_theme,
    get_pig_dashboard_status,
    get_user_weekly_bet_count,
)


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

        inventory_items = UserCerealInventory.query.filter_by(user_id=user.id).all()
        inventory = {item.cereal_key: item.quantity for item in inventory_items if item.quantity > 0}
    else:
        inventory = {}

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
        recommended_cereal = recommend_best_cereal(featured_pig['pig'], inventory)
    else:
        recommended_cereal = None

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
        'inventory': inventory,
        'recommended_cereal': recommended_cereal,
    }
