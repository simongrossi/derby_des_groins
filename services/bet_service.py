from datetime import datetime

from config.game_rules import BET_RULES
from data import COMPLEX_BET_MIN_SELECTIONS
from exceptions import InsufficientFundsError, ValidationError
from extensions import db
from helpers.config import get_config
from helpers.db import apply_row_lock
from helpers.race import get_user_active_pigs
from models import Bet, Participant, Race, User
from services.economy_service import (
    get_bet_limits,
    get_configured_bet_types,
    get_effective_bet_odds,
    get_weekly_bacon_tickets_value,
)
from services.finance_service import debit_user
from services.race_service import (
    calculate_bet_odds,
    format_bet_label,
    get_course_theme,
    get_user_weekly_bet_count,
    normalize_bet_type,
    parse_selection_ids,
    serialize_selection_ids,
)


def place_bet_for_user(user_or_id, race_id, bet_type_raw, selection_raw, amount):
    user = user_or_id if isinstance(user_or_id, User) else db.session.get(User, user_or_id)
    if not user:
        raise ValidationError("Utilisateur introuvable.")

    bet_types = get_configured_bet_types()
    weekly_bacon_tickets = get_weekly_bacon_tickets_value()
    bet_limits = get_bet_limits()
    weekly_bet_count = get_user_weekly_bet_count(user, datetime.now())
    if weekly_bet_count >= weekly_bacon_tickets:
        raise ValidationError(f"Tu as deja utilise tes {weekly_bacon_tickets} Tickets Bacon de la semaine.")

    bet_type = normalize_bet_type(bet_type_raw or 'win')
    selection_ids = parse_selection_ids((selection_raw or '').strip())
    if not all([race_id, amount]):
        raise ValidationError("Ticket incomplet. Choisis ton pari et ta mise.")

    race = apply_row_lock(Race.query.filter_by(id=race_id)).first()
    if not race or race.status != 'open':
        raise ValidationError("Cette course n'accepte plus de paris.")

    if (race.scheduled_at - datetime.now()).total_seconds() < BET_RULES.closing_window_seconds:
        raise ValidationError(
            f"Les paris ferment {BET_RULES.closing_window_seconds} secondes avant le départ."
        )

    participants = Participant.query.filter_by(race_id=race_id).all()
    participants_by_id = {participant.id: participant for participant in participants}
    expected_count = bet_types[bet_type]['selection_count']
    if len(participants) < expected_count:
        raise ValidationError("Pas assez de partants pour ce type de ticket.")

    if len(selection_ids) != expected_count or len(set(selection_ids)) != expected_count:
        raise ValidationError(f"Ce ticket demande {expected_count} cochon(s) distinct(s) dans l'ordre.")

    selected_participants = [participants_by_id.get(selection_id) for selection_id in selection_ids]
    if any(participant is None for participant in selected_participants):
        raise ValidationError("Sélection invalide pour cette course.")

    if not amount or amount < bet_limits['min_bet_race'] or amount > bet_limits['max_bet_race']:
        raise ValidationError(
            f"La mise doit etre entre {bet_limits['min_bet_race']:.0f} et {bet_limits['max_bet_race']:.0f} BitGroins."
        )

    if expected_count >= COMPLEX_BET_MIN_SELECTIONS:
        user_pig_ids = {pig.id for pig in get_user_active_pigs(user)}
        user_has_pig_in_race = any(participant.pig_id and participant.pig_id in user_pig_ids for participant in participants)
        if not user_has_pig_in_race:
            raise ValidationError("Les paris complexes (3+ cochons) necessitent que ton cochon participe a la course.")

    try:
        max_bets = int(
            get_config('bets_per_race_limit', str(BET_RULES.default_bets_per_race_limit))
        )
    except (ValueError, TypeError):
        max_bets = BET_RULES.default_bets_per_race_limit

    existing_count = Bet.query.filter_by(user_id=user.id, race_id=race_id).count()
    if existing_count >= max_bets:
        if max_bets <= 1:
            raise ValidationError("Tu as déjà un ticket sur cette course.")
        raise ValidationError(f"Tu as déjà atteint la limite de {max_bets} ticket(s) sur cette course.")

    reward_multiplier = float((get_course_theme(race.scheduled_at) or {}).get('reward_multiplier', 1) or 1)
    raw_odds = calculate_bet_odds(
        participants_by_id,
        selection_ids,
        bet_type,
        reward_multiplier=reward_multiplier,
    )
    if raw_odds <= 0:
        raise ValidationError("Impossible de calculer la cote de ce ticket.")

    odds_at_bet = get_effective_bet_odds(raw_odds, amount)
    if odds_at_bet <= 0:
        raise ValidationError("Le plafond de gain actuel rend cette mise impossible pour ce ticket.")

    bet_label = format_bet_label(selected_participants)
    bet = Bet(
        user_id=user.id,
        race_id=race_id,
        pig_name=bet_label,
        bet_type=bet_type,
        selection_order=serialize_selection_ids(selection_ids),
        amount=amount,
        odds_at_bet=odds_at_bet,
        status='pending',
    )

    try:
        debit_user(
            user,
            amount,
            reason_code='bet_stake',
            reason_label='Mise de pari',
            details=f"Ticket {bet_types[bet_type]['label'].lower()} sur la course #{race_id}: {bet_label}.",
            reference_type='race',
            reference_id=race_id,
            commit=False,
        )
    except InsufficientFundsError:
        raise InsufficientFundsError("Pas assez de BitGroins pour valider ce ticket.") from None

    db.session.add(bet)
    db.session.commit()

    return {
        'category': 'success',
        'message': f"{bet_types[bet_type]['icon']} Ticket {bet_types[bet_type]['label'].lower()} validé sur {bet_label}.",
    }
