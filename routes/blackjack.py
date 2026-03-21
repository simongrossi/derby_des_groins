from flask import Blueprint, render_template, redirect, url_for, session, flash, request, jsonify
import random
import json

from extensions import db
from models import User
from helpers import debit_user_balance, credit_user_balance

blackjack_bp = Blueprint('blackjack', __name__)

# ── Modélisation du jeu de 54 cartes ────────────────────────────────────────

SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
JOKERS = [{'rank': 'JOKER', 'suit': '🃏', 'value': 0, 'is_joker': True, 'label': 'Joker Rouge'},
          {'rank': 'JOKER', 'suit': '🃟', 'value': 0, 'is_joker': True, 'label': 'Joker Noir'}]

RANK_VALUES = {
    'A': [1, 11], '2': 2, '3': 3, '4': 4, '5': 5,
    '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
    'J': 10, 'Q': 10, 'K': 10,
}

# Effets spéciaux des Jokers dans le Derby des Groins
JOKER_EFFECTS = [
    "Le cochon du croupier glisse sur une flaque de boue et perd une carte !",
    "Intervention divine porcine : vous piochez une carte bonus !",
    "Le Joker grogne et annule la dernière carte du croupier !",
    "Miraculeux ! Votre cochon a trafiqué le sabot — vous tirez une carte de votre choix... ou pas.",
    "Le Joker rote bruyamment. Rien ne se passe. C'était juste un joker nul.",
]

def build_deck():
    """Construit un sabot de 54 cartes (52 + 2 jokers)."""
    deck = []
    for suit in SUITS:
        for rank in RANKS:
            val = RANK_VALUES[rank]
            deck.append({
                'rank': rank,
                'suit': suit,
                'value': val,
                'is_joker': False,
                'label': f"{rank}{suit}",
            })
    deck.extend(JOKERS)
    random.shuffle(deck)
    return deck

def hand_value(hand):
    """Calcule la valeur optimale d'une main (gère les As et ignore les Jokers)."""
    total = 0
    aces = 0
    for card in hand:
        if card.get('is_joker'):
            continue  # Les jokers n'ont pas de valeur fixe en Blackjack
        val = card['value']
        if isinstance(val, list):  # As
            aces += 1
            total += 11
        else:
            total += val
    # Rabattre les As si on dépasse 21
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total

def card_display(card):
    """Retourne un dict enrichi pour l'affichage."""
    if card.get('is_joker'):
        return {**card, 'color': 'joker', 'display': card['suit']}
    color = 'red' if card['suit'] in ['♥', '♦'] else 'black'
    return {**card, 'color': color, 'display': f"{card['rank']}{card['suit']}"}

def get_game_state():
    """Récupère l'état de jeu depuis la session."""
    raw = session.get('blackjack_game')
    if not raw:
        return None
    return raw

def save_game_state(state):
    session['blackjack_game'] = state
    session.modified = True

def clear_game_state():
    session.pop('blackjack_game', None)

MIN_BET = 5
MAX_BET = 500

# ── Routes ───────────────────────────────────────────────────────────────────

@blackjack_bp.route('/blackjack')
def blackjack():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    game = get_game_state()
    return render_template(
        'blackjack.html',
        user=user,
        active_page='blackjack',
        game=game,
        min_bet=MIN_BET,
        max_bet=MAX_BET,
    )


@blackjack_bp.route('/blackjack/deal', methods=['POST'])
def blackjack_deal():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])

    # Nettoyer la partie précédente si elle est terminée
    old_game = get_game_state()
    if old_game and old_game.get('phase') not in ('finished',):
        flash("Une partie est déjà en cours, cochon !", "warning")
        return redirect(url_for('blackjack.blackjack'))

    bet = request.form.get('bet', 0, type=float)
    if bet < MIN_BET or bet > MAX_BET:
        flash(f"La mise doit être entre {MIN_BET} et {MAX_BET} 🪙 BitGroins.", "error")
        return redirect(url_for('blackjack.blackjack'))
    if not user.can_afford(bet):
        flash("T'as pas assez de BitGroins pour jouer ! Va élever des cochons.", "error")
        return redirect(url_for('blackjack.blackjack'))

    # Débiter la mise
    ok = debit_user_balance(
        user.id, bet,
        reason_code='blackjack_bet',
        reason_label='🃏 Mise Blackjack',
        details=f"Mise de {bet:.0f} 🪙 placée à la table du Groin Jack.",
        reference_type='user', reference_id=user.id,
    )
    if not ok:
        flash("Échec du débit... ton cochon a mangé les BitGroins ?", "error")
        return redirect(url_for('blackjack.blackjack'))
    db.session.commit()

    # Construire le sabot et distribuer
    deck = build_deck()
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]

    # Vérifier jokers immédiats
    joker_msg = None
    for card in player_hand:
        if card.get('is_joker'):
            joker_msg = random.choice(JOKER_EFFECTS)
            # Le Joker dans la main du joueur : on lui offre une carte bonus
            player_hand.append(deck.pop())
            break

    # Vérifier Blackjack naturel (sans joker)
    player_val = hand_value(player_hand)
    dealer_val = hand_value(dealer_hand)
    phase = 'playing'
    result = None
    dealer_reveal = False

    if player_val == 21 and len(player_hand) == 2:
        # Blackjack ! Vérifier si le dealer aussi
        if dealer_val == 21:
            phase = 'finished'
            result = 'push'
            dealer_reveal = True
        else:
            phase = 'finished'
            result = 'blackjack'
            dealer_reveal = True
            winnings = round(bet * 2.5, 2)  # 3:2
            credit_user_balance(
                user.id, winnings,
                reason_code='blackjack_win',
                reason_label='🃏 Blackjack ! Gagné',
                details=f"BLACKJACK naturel ! Gain de {winnings:.0f} 🪙 (mise {bet:.0f} × 2.5).",
                reference_type='user', reference_id=user.id,
            )
            db.session.commit()

    game_state = {
        'phase': phase,
        'bet': bet,
        'deck': deck,
        'player_hand': player_hand,
        'dealer_hand': dealer_hand,
        'result': result,
        'dealer_reveal': dealer_reveal,
        'joker_msg': joker_msg,
        'winnings': winnings if result == 'blackjack' else None,
    }
    save_game_state(game_state)
    return redirect(url_for('blackjack.blackjack'))


@blackjack_bp.route('/blackjack/hit', methods=['POST'])
def blackjack_hit():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    game = get_game_state()
    if not game or game.get('phase') != 'playing':
        return redirect(url_for('blackjack.blackjack'))

    deck = game['deck']
    new_card = deck.pop()
    game['player_hand'].append(new_card)
    game['deck'] = deck

    joker_msg = None
    if new_card.get('is_joker'):
        joker_msg = random.choice(JOKER_EFFECTS)
        game['joker_msg'] = joker_msg
        # Joker pioché en cours de jeu : annule la dernière carte du dealer (effet cosmétique)
        # et on ajoute une vraie carte à la main du joueur
        extra = deck.pop()
        game['player_hand'].append(extra)
        game['deck'] = deck

    player_val = hand_value(game['player_hand'])

    if player_val > 21:
        game['phase'] = 'finished'
        game['result'] = 'bust'
        game['dealer_reveal'] = True
    elif player_val == 21:
        # Auto-stand à 21
        game = _dealer_play(game, user)

    save_game_state(game)
    return redirect(url_for('blackjack.blackjack'))


@blackjack_bp.route('/blackjack/stand', methods=['POST'])
def blackjack_stand():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    game = get_game_state()
    if not game or game.get('phase') != 'playing':
        return redirect(url_for('blackjack.blackjack'))

    game = _dealer_play(game, user)
    save_game_state(game)
    return redirect(url_for('blackjack.blackjack'))


@blackjack_bp.route('/blackjack/double', methods=['POST'])
def blackjack_double():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    game = get_game_state()
    if not game or game.get('phase') != 'playing' or len(game['player_hand']) != 2:
        return redirect(url_for('blackjack.blackjack'))

    extra_bet = game['bet']
    if not user.can_afford(extra_bet):
        flash("Pas assez de BitGroins pour doubler ! T'as qu'à prier saint Cochon.", "error")
        return redirect(url_for('blackjack.blackjack'))

    ok = debit_user_balance(
        user.id, extra_bet,
        reason_code='blackjack_double',
        reason_label='🃏 Double Blackjack',
        details=f"Doublement de mise : +{extra_bet:.0f} 🪙.",
        reference_type='user', reference_id=user.id,
    )
    if not ok:
        flash("Échec du doublement...", "error")
        return redirect(url_for('blackjack.blackjack'))
    db.session.commit()

    game['bet'] = round(game['bet'] * 2, 2)
    # Tirer une seule carte puis jouer le dealer
    new_card = game['deck'].pop()
    game['player_hand'].append(new_card)
    game = _dealer_play(game, user)
    save_game_state(game)
    return redirect(url_for('blackjack.blackjack'))


@blackjack_bp.route('/blackjack/new', methods=['POST'])
def blackjack_new():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    clear_game_state()
    return redirect(url_for('blackjack.blackjack'))


# ── Logique dealer ───────────────────────────────────────────────────────────

def _dealer_play(game, user):
    """Le dealer joue selon les règles (tire jusqu'à 17+)."""
    deck = game['deck']
    dealer_hand = game['dealer_hand']

    dealer_val = hand_value(dealer_hand)
    while dealer_val < 17:
        new_card = deck.pop()
        dealer_hand.append(new_card)
        if new_card.get('is_joker'):
            # Joker du dealer : il rate et doit retirer une carte au hasard
            if len(dealer_hand) > 1:
                dealer_hand.pop(random.randrange(len(dealer_hand) - 1))
            game['joker_msg'] = "Le Joker s'incruste chez le croupier ! Il perd une carte dans la confusion porcine."
        dealer_val = hand_value(dealer_hand)

    game['deck'] = deck
    game['dealer_hand'] = dealer_hand
    game['dealer_reveal'] = True

    player_val = hand_value(game['player_hand'])

    # Déterminer le résultat
    if player_val > 21:
        result = 'bust'
    elif dealer_val > 21:
        result = 'dealer_bust'
    elif player_val > dealer_val:
        result = 'win'
    elif player_val < dealer_val:
        result = 'lose'
    else:
        result = 'push'

    game['phase'] = 'finished'
    game['result'] = result

    bet = game['bet']
    winnings = None

    if result in ('win', 'dealer_bust'):
        winnings = round(bet * 2, 2)
        credit_user_balance(
            user.id, winnings,
            reason_code='blackjack_win',
            reason_label='🃏 Victoire Blackjack',
            details=f"Victoire au Groin Jack ! Gain de {winnings:.0f} 🪙 (mise {bet:.0f}).",
            reference_type='user', reference_id=user.id,
        )
        db.session.commit()
    elif result == 'push':
        # Remboursement de la mise
        credit_user_balance(
            user.id, bet,
            reason_code='blackjack_push',
            reason_label='🃏 Égalité Blackjack',
            details=f"Égalité au Groin Jack. Remboursement de {bet:.0f} 🪙.",
            reference_type='user', reference_id=user.id,
        )
        db.session.commit()

    game['winnings'] = winnings
    return game
