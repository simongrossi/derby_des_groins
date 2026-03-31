from __future__ import annotations

import random
from typing import Any

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from extensions import db, limiter
from models import User
from services.finance_service import credit_user_balance, debit_user_balance

blackjack_bp = Blueprint('blackjack', __name__)

SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
RANK_VALUES = {
    'A': [1, 11],
    '2': 2,
    '3': 3,
    '4': 4,
    '5': 5,
    '6': 6,
    '7': 7,
    '8': 8,
    '9': 9,
    '10': 10,
    'J': 10,
    'Q': 10,
    'K': 10,
}
JOKERS = [
    {'rank': 'JOKER', 'suit': '🃏', 'value': 0, 'is_joker': True, 'label': 'Joker Rouge'},
    {'rank': 'JOKER', 'suit': '🃏', 'value': 0, 'is_joker': True, 'label': 'Joker Noir'},
]
JOKER_EFFECTS = [
    "Le croupier glisse dans la boue : tu pioches une carte bonus.",
    "Le Joker grogne et sème la panique à la table.",
    "Intervention divine porcine : une carte supplémentaire tombe du sabot.",
    "Le Joker rote bruyamment. Rien ne se passe, mais l'ambiance est bonne.",
]

MIN_BET = 5
MAX_BET = 500
SESSION_KEY = 'blackjack_game'


def build_deck() -> list[dict[str, Any]]:
    deck = []
    for suit in SUITS:
        for rank in RANKS:
            deck.append({
                'rank': rank,
                'suit': suit,
                'value': RANK_VALUES[rank],
                'is_joker': False,
                'label': f'{rank}{suit}',
            })
    deck.extend(JOKERS)
    random.shuffle(deck)
    return deck


def hand_value(hand: list[dict[str, Any]]) -> int:
    total = 0
    aces = 0
    for card in hand:
        if card.get('is_joker'):
            continue
        value = card['value']
        if isinstance(value, list):
            total += 11
            aces += 1
        else:
            total += value
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total


def load_game_state() -> dict[str, Any] | None:
    return session.get(SESSION_KEY)


def save_game_state(state: dict[str, Any]) -> None:
    session[SESSION_KEY] = state
    session.modified = True


def clear_game_state() -> None:
    session.pop(SESSION_KEY, None)
    session.modified = True


def _resolve_user() -> User | None:
    user_id = session.get('user_id')
    return User.query.get(user_id) if user_id else None


def _finish_game(game: dict[str, Any], user: User) -> dict[str, Any]:
    dealer_hand = game['dealer_hand']
    deck = game['deck']

    while hand_value(dealer_hand) < 17 and deck:
        drawn = deck.pop()
        dealer_hand.append(drawn)
        if drawn.get('is_joker') and len(dealer_hand) > 1:
            removable_indexes = [i for i, card in enumerate(dealer_hand) if not card.get('is_joker')]
            if removable_indexes:
                dealer_hand.pop(random.choice(removable_indexes))
                game['joker_msg'] = "Le Joker a fait défausser une carte au croupier."

    player_total = hand_value(game['player_hand'])
    dealer_total = hand_value(dealer_hand)

    if player_total > 21:
        result = 'bust'
    elif dealer_total > 21:
        result = 'dealer_bust'
    elif player_total > dealer_total:
        result = 'win'
    elif player_total < dealer_total:
        result = 'lose'
    else:
        result = 'push'

    game['phase'] = 'finished'
    game['dealer_reveal'] = True
    game['result'] = result
    game['player_total'] = player_total
    game['dealer_total'] = dealer_total
    game['deck'] = deck

    bet = round(float(game['bet']), 2)
    if result in ('win', 'dealer_bust'):
        winnings = round(bet * 2, 2)
        credit_user_balance(
            user.id,
            winnings,
            reason_code='blackjack_win',
            reason_label='Victoire Groin Jack',
            details=f'Victoire au blackjack porcin ({bet:.0f} 🪙 misés).',
            reference_type='user',
            reference_id=user.id,
        )
        game['winnings'] = winnings
        db.session.commit()
    elif result == 'push':
        credit_user_balance(
            user.id,
            bet,
            reason_code='blackjack_push',
            reason_label='Égalité Groin Jack',
            details=f'Égalité au blackjack porcin ({bet:.0f} 🪙 remboursés).',
            reference_type='user',
            reference_id=user.id,
        )
        game['winnings'] = bet
        db.session.commit()
    else:
        game['winnings'] = 0

    return game


@blackjack_bp.route('/blackjack')
def blackjack():
    user = _resolve_user()
    if not user:
        return redirect(url_for('auth.login'))
    return render_template(
        'blackjack.html',
        user=user,
        active_page='blackjack',
        game=load_game_state(),
        min_bet=MIN_BET,
        max_bet=MAX_BET,
    )


@blackjack_bp.route('/blackjack/deal', methods=['POST'])
@limiter.limit("15 per minute")
def blackjack_deal():
    user = _resolve_user()
    if not user:
        return redirect(url_for('auth.login'))

    current_game = load_game_state()
    if current_game and current_game.get('phase') == 'playing':
        flash('Une partie est déjà en cours.', 'warning')
        return redirect(url_for('blackjack.blackjack'))

    bet = request.form.get('bet', type=float, default=0)
    if bet < MIN_BET or bet > MAX_BET:
        flash(f'La mise doit être comprise entre {MIN_BET} et {MAX_BET} 🪙.', 'error')
        return redirect(url_for('blackjack.blackjack'))
    if not user.can_afford(bet):
        flash("Pas assez de BitGroins pour lancer une partie.", 'error')
        return redirect(url_for('blackjack.blackjack'))

    ok = debit_user_balance(
        user.id,
        bet,
        reason_code='blackjack_bet',
        reason_label='Mise Groin Jack',
        details=f'Mise de {bet:.0f} 🪙 au blackjack porcin.',
        reference_type='user',
        reference_id=user.id,
    )
    if not ok:
        flash("Impossible de débiter la mise.", 'error')
        return redirect(url_for('blackjack.blackjack'))
    db.session.commit()

    deck = build_deck()
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]
    joker_msg = None

    if any(card.get('is_joker') for card in player_hand) and deck:
        player_hand.append(deck.pop())
        joker_msg = random.choice(JOKER_EFFECTS)

    game = {
        'phase': 'playing',
        'bet': round(bet, 2),
        'deck': deck,
        'player_hand': player_hand,
        'dealer_hand': dealer_hand,
        'dealer_reveal': False,
        'joker_msg': joker_msg,
        'result': None,
        'winnings': None,
        'player_total': hand_value(player_hand),
        'dealer_total': hand_value(dealer_hand),
    }

    if game['player_total'] == 21 and len([card for card in player_hand if not card.get('is_joker')]) == 2:
        if game['dealer_total'] == 21:
            game['phase'] = 'finished'
            game['dealer_reveal'] = True
            game['result'] = 'push'
            game['winnings'] = bet
            credit_user_balance(
                user.id,
                bet,
                reason_code='blackjack_push',
                reason_label='Égalité Groin Jack',
                details='Blackjack partagé avec le croupier.',
                reference_type='user',
                reference_id=user.id,
            )
        else:
            winnings = round(bet * 2.5, 2)
            game['phase'] = 'finished'
            game['dealer_reveal'] = True
            game['result'] = 'blackjack'
            game['winnings'] = winnings
            credit_user_balance(
                user.id,
                winnings,
                reason_code='blackjack_win',
                reason_label='Blackjack Groin Jack',
                details=f'Blackjack naturel payé 3:2 ({bet:.0f} 🪙 misés).',
                reference_type='user',
                reference_id=user.id,
            )
        db.session.commit()

    save_game_state(game)
    return redirect(url_for('blackjack.blackjack'))


@blackjack_bp.route('/blackjack/hit', methods=['POST'])
@limiter.limit("30 per minute")
def blackjack_hit():
    user = _resolve_user()
    if not user:
        return redirect(url_for('auth.login'))

    game = load_game_state()
    if not game or game.get('phase') != 'playing' or not game.get('deck'):
        return redirect(url_for('blackjack.blackjack'))

    drawn = game['deck'].pop()
    game['player_hand'].append(drawn)
    if drawn.get('is_joker') and game['deck']:
        game['player_hand'].append(game['deck'].pop())
        game['joker_msg'] = random.choice(JOKER_EFFECTS)

    game['player_total'] = hand_value(game['player_hand'])
    if game['player_total'] > 21:
        game['phase'] = 'finished'
        game['dealer_reveal'] = True
        game['result'] = 'bust'
        game['winnings'] = 0
    elif game['player_total'] == 21:
        game = _finish_game(game, user)

    save_game_state(game)
    return redirect(url_for('blackjack.blackjack'))


@blackjack_bp.route('/blackjack/stand', methods=['POST'])
@limiter.limit("30 per minute")
def blackjack_stand():
    user = _resolve_user()
    if not user:
        return redirect(url_for('auth.login'))

    game = load_game_state()
    if not game or game.get('phase') != 'playing':
        return redirect(url_for('blackjack.blackjack'))

    game = _finish_game(game, user)
    save_game_state(game)
    return redirect(url_for('blackjack.blackjack'))


@blackjack_bp.route('/blackjack/double', methods=['POST'])
@limiter.limit("30 per minute")
def blackjack_double():
    user = _resolve_user()
    if not user:
        return redirect(url_for('auth.login'))

    game = load_game_state()
    if not game or game.get('phase') != 'playing' or len(game.get('player_hand', [])) != 2:
        return redirect(url_for('blackjack.blackjack'))

    extra_bet = round(float(game['bet']), 2)
    if not user.can_afford(extra_bet):
        flash("Pas assez de BitGroins pour doubler.", 'error')
        return redirect(url_for('blackjack.blackjack'))

    ok = debit_user_balance(
        user.id,
        extra_bet,
        reason_code='blackjack_double',
        reason_label='Double Groin Jack',
        details=f'Doublement de mise au blackjack (+{extra_bet:.0f} 🪙).',
        reference_type='user',
        reference_id=user.id,
    )
    if not ok:
        flash("Impossible de doubler la mise.", 'error')
        return redirect(url_for('blackjack.blackjack'))
    db.session.commit()

    game['bet'] = round(game['bet'] + extra_bet, 2)
    if game['deck']:
        game['player_hand'].append(game['deck'].pop())
    game['player_total'] = hand_value(game['player_hand'])
    game = _finish_game(game, user)
    save_game_state(game)
    return redirect(url_for('blackjack.blackjack'))


@blackjack_bp.route('/blackjack/new', methods=['POST'])
@limiter.limit("15 per minute")
def blackjack_new():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    clear_game_state()
    return redirect(url_for('blackjack.blackjack'))
