"""
🐷 GROIN POKER — Le Texas Hold'em le plus cochon de la porcherie
Route Blueprint : toutes les actions du jeu de poker multijoueur
"""
from __future__ import annotations

import random
import json
from datetime import datetime
from typing import Any

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from extensions import db, limiter
from models import User, PokerTable, PokerPlayer, PokerHandHistory
from services.finance_service import credit_user_balance, debit_user_balance

poker_bp = Blueprint('poker', __name__)

# ──────────────────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────────────────
SUITS = ['🐷', '🐽', '🥓', '🍖']   # symboles porcins en guise de couleurs
SUIT_NAMES = {'🐷': 'Groin', '🐽': 'Truffe', '🥓': 'Lard', '🍖': 'Saucisse'}
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, 2)}  # 2→2 … A→14

BUY_IN_OPTIONS = [10, 20, 50, 100]
MIN_PLAYERS = 3
MAX_PLAYERS = 8
SMALL_BLIND_RATIO = 0.10   # small blind = 10% du buy-in

# Messages porcins humoristiques
GROIN_MSGS = [
    "🐷 Le cochon à gauche grogne d'impatience.",
    "🥓 L'odeur du lard chaud flotte sur la table.",
    "🐽 Une truffe pointe sur vos cartes cachées.",
    "🍖 La saucisse misée tremble dans le pot.",
    "🐗 Le sanglier dealer beugle 'ALL-IN ou BACON ?'",
    "🌽 Quelqu'un a renversé le seau de maïs sur la table.",
    "💨 Un pet de cochon retentit. Bluff ou flatulence ?",
    "🎪 Le fermier observe depuis la barrière avec envie.",
]

BLUFF_TAUNTS = [
    "Tu bluffes comme un cochon déguisé en agneau.",
    "Même un cochon aveugle trouverait cette mise suspecte.",
    "C'est ça ton meilleur jeu ? Ma truffe fait mieux.",
    "Le pot sent la boue ET le mensonge.",
    "CALL ! Si tu mens, tu finis en saucisse.",
]

# ──────────────────────────────────────────────────────────
# Utilitaires cartes
# ──────────────────────────────────────────────────────────

def build_deck() -> list[dict]:
    deck = []
    for suit in SUITS:
        for rank in RANKS:
            deck.append({
                'rank': rank,
                'suit': suit,
                'value': RANK_VALUES[rank],
                'label': f'{rank}{suit}',
                'suit_name': SUIT_NAMES[suit],
            })
    random.shuffle(deck)
    return deck


def hand_rank(cards: list[dict]) -> tuple:
    """Évalue 5 cartes et retourne un tuple comparable (plus grand = meilleure main)."""
    if len(cards) < 5:
        return (0,)
    cards = sorted(cards, key=lambda c: c['value'], reverse=True)
    vals = [c['value'] for c in cards]
    suits = [c['suit'] for c in cards]

    is_flush = len(set(suits)) == 1
    is_straight = (max(vals) - min(vals) == 4 and len(set(vals)) == 5)
    # roue A-2-3-4-5
    if set(vals) == {14, 2, 3, 4, 5}:
        is_straight = True
        vals = [5, 4, 3, 2, 1]

    from collections import Counter
    counts = Counter(vals)
    freq = sorted(counts.values(), reverse=True)
    groups = sorted(counts.keys(), key=lambda v: (counts[v], v), reverse=True)

    if is_straight and is_flush:
        return (8, max(vals))
    if freq == [4, 1]:
        return (7, groups[0], groups[1])
    if freq == [3, 2]:
        return (6, groups[0], groups[1])
    if is_flush:
        return (5,) + tuple(vals)
    if is_straight:
        return (4, max(vals))
    if freq[0] == 3:
        return (3, groups[0]) + tuple(groups[1:])
    if freq[:2] == [2, 2]:
        pair1, pair2 = sorted([groups[0], groups[1]], reverse=True)
        return (2, pair1, pair2, groups[2])
    if freq[0] == 2:
        return (1, groups[0]) + tuple(groups[1:])
    return (0,) + tuple(vals)


def best_5_from_7(cards: list[dict]) -> tuple:
    """Choisit la meilleure main de 5 parmi 7 cartes."""
    from itertools import combinations
    best = (0,)
    for combo in combinations(cards, 5):
        r = hand_rank(list(combo))
        if r > best:
            best = r
    return best


HAND_NAMES = {
    8: "Quinte Flush Royale Porcine 👑🐷",
    7: "Carré de Cochons 🐷🐷🐷🐷",
    6: "Full Groin 🐷🍖",
    5: "Couleur Lard 🥓",
    4: "Quinte Truffe 🐽",
    3: "Brelan de Groineurs 🐷🐷🐷",
    2: "Double Paire Bacon 🥓🥓",
    1: "Paire de Gorets 🐷🐷",
    0: "Carte Haute (pauvre cochon)",
}

def hand_name(rank_tuple: tuple) -> str:
    return HAND_NAMES.get(rank_tuple[0], "???")


# ──────────────────────────────────────────────────────────
# Helpers session / table
# ──────────────────────────────────────────────────────────

def _resolve_user() -> User | None:
    uid = session.get('user_id')
    return User.query.get(uid) if uid else None


def _get_active_table() -> PokerTable | None:
    return PokerTable.query.filter(
        PokerTable.status.in_(['lobby', 'voting', 'playing'])
    ).order_by(PokerTable.created_at.desc()).first()


# ──────────────────────────────────────────────────────────
# Routes principales
# ──────────────────────────────────────────────────────────

@poker_bp.route('/poker')
def poker_lobby():
    user = _resolve_user()
    if not user:
        return redirect(url_for('auth.login'))

    table = _get_active_table()
    my_seat = None
    players = []
    if table:
        players = PokerPlayer.query.filter_by(table_id=table.id).order_by(PokerPlayer.seat).all()
        my_seat = next((p for p in players if p.user_id == user.id), None)

    return render_template(
        'poker.html',
        user=user,
        active_page='poker',
        table=table,
        players=players,
        my_seat=my_seat,
        buy_in_options=BUY_IN_OPTIONS,
        min_players=MIN_PLAYERS,
        groin_msg=random.choice(GROIN_MSGS),
    )


@poker_bp.route('/poker/join', methods=['POST'])
@limiter.limit("10 per minute")
def poker_join():
    """Le joueur s'inscrit pour la prochaine partie."""
    user = _resolve_user()
    if not user:
        return jsonify({'ok': False, 'error': 'Non connecté'}), 401

    table = _get_active_table()

    # Créer une table si aucune n'est ouverte
    if not table:
        table = PokerTable(
            status='lobby',
            buy_in=0,
            pot=0.0,
            deck_json='[]',
            community_json='[]',
            state_json='{}',
        )
        db.session.add(table)
        db.session.flush()

    if table.status == 'playing':
        # Rejoindre en cours de partie
        existing = PokerPlayer.query.filter_by(table_id=table.id, user_id=user.id).first()
        if existing:
            return jsonify({'ok': False, 'error': 'Déjà à table'})
        # Place libre ?
        seat_count = PokerPlayer.query.filter_by(table_id=table.id).count()
        if seat_count >= MAX_PLAYERS:
            return jsonify({'ok': False, 'error': 'Table complète (max 8 cochons)'})
        buy_in = table.buy_in
        if not user.can_afford(buy_in):
            return jsonify({'ok': False, 'error': f'Fonds insuffisants. Il faut {buy_in} BitGroins.'})
        ok = debit_user_balance(user.id, buy_in,
            reason_code='poker_buy_in',
            reason_label='Mise de départ Groin Poker',
            details=f'Achat de jetons ({buy_in} BG) — table #{table.id}',
            reference_type='poker_table', reference_id=table.id)
        if not ok:
            return jsonify({'ok': False, 'error': 'Impossible de débiter le buy-in.'})
        # Attribuer un siège
        used_seats = {p.seat for p in PokerPlayer.query.filter_by(table_id=table.id).all()}
        seat = next(s for s in range(1, MAX_PLAYERS + 1) if s not in used_seats)
        player = PokerPlayer(
            table_id=table.id,
            user_id=user.id,
            seat=seat,
            chips=buy_in,
            status='waiting',  # attendra le prochain tour
            hole_json='[]',
            is_spectator=False,
        )
        db.session.add(player)
        db.session.commit()
        return jsonify({'ok': True, 'status': 'late_join', 'message': '🐷 Tu rejoins la table en cours de partie !'})

    if table.status in ('lobby', 'voting'):
        existing = PokerPlayer.query.filter_by(table_id=table.id, user_id=user.id).first()
        if existing:
            return jsonify({'ok': False, 'error': 'Déjà inscrit pour cette partie !'})
        seat_count = PokerPlayer.query.filter_by(table_id=table.id).count()
        if seat_count >= MAX_PLAYERS:
            return jsonify({'ok': False, 'error': 'Table complète (max 8 cochons)'})

        player = PokerPlayer(
            table_id=table.id,
            user_id=user.id,
            seat=seat_count + 1,
            chips=0,  # sera fixé au vote
            status='waiting',
            hole_json='[]',
            is_spectator=False,
            vote=None,
        )
        db.session.add(player)
        db.session.commit()

        count = PokerPlayer.query.filter_by(table_id=table.id).count()
        return jsonify({
            'ok': True,
            'status': 'lobby',
            'player_count': count,
            'message': f'🐷 Inscrit ! {count} cochon(s) à table.',
        })

    return jsonify({'ok': False, 'error': 'Aucune table disponible.'})


@poker_bp.route('/poker/vote', methods=['POST'])
@limiter.limit("20 per minute")
def poker_vote():
    """Vote pour le montant du buy-in."""
    user = _resolve_user()
    if not user:
        return jsonify({'ok': False, 'error': 'Non connecté'}), 401

    table = _get_active_table()
    if not table or table.status not in ('lobby', 'voting'):
        return jsonify({'ok': False, 'error': 'Pas de vote en cours.'})

    player = PokerPlayer.query.filter_by(table_id=table.id, user_id=user.id).first()
    if not player:
        return jsonify({'ok': False, 'error': 'Tu n\'es pas inscrit à cette table.'})

    amount = request.get_json(silent=True, force=True) or {}
    buy_in = int(amount.get('buy_in', 0))
    if buy_in not in BUY_IN_OPTIONS:
        return jsonify({'ok': False, 'error': 'Montant invalide. Cochon tricheur !'})

    player.vote = buy_in
    table.status = 'voting'
    db.session.commit()

    # Vérifier unanimité
    players = PokerPlayer.query.filter_by(table_id=table.id).all()
    votes = [p.vote for p in players if p.vote is not None]
    total = len(players)

    if len(votes) == total and total >= MIN_PLAYERS:
        if len(set(votes)) == 1:
            # Unanimité !
            agreed_buy_in = votes[0]
            # Vérifier que tout le monde peut payer
            can_all_pay = all(
                User.query.get(p.user_id).can_afford(agreed_buy_in)
                for p in players
            )
            if not can_all_pay:
                # Remettre en vote
                for p in players:
                    p.vote = None
                db.session.commit()
                return jsonify({
                    'ok': False,
                    'error': '💸 Certains cochons sont à sec ! Vote annulé, rechoisissez un montant.'
                })
            return jsonify({
                'ok': True,
                'unanimous': True,
                'buy_in': agreed_buy_in,
                'message': f'🎉 Unanimité ! Buy-in fixé à {agreed_buy_in} BitGroins. Lancement imminent…',
            })
        else:
            # Pas d'unanimité
            for p in players:
                p.vote = None
            db.session.commit()
            return jsonify({
                'ok': True,
                'unanimous': False,
                'votes': {str(v): votes.count(v) for v in set(votes)},
                'message': '🐷 Pas d\'unanimité ! Les cochons doivent revoter.',
            })

    return jsonify({
        'ok': True,
        'unanimous': False,
        'voted': len(votes),
        'total': total,
        'message': f'Vote enregistré ({len(votes)}/{total} cochons ont voté).',
    })


@poker_bp.route('/poker/start', methods=['POST'])
@limiter.limit("5 per minute")
def poker_start():
    """Lance la partie (après vote unanime)."""
    user = _resolve_user()
    if not user:
        return jsonify({'ok': False, 'error': 'Non connecté'}), 401

    table = _get_active_table()
    if not table or table.status not in ('lobby', 'voting'):
        return jsonify({'ok': False, 'error': 'Pas de table en attente.'})

    players = PokerPlayer.query.filter_by(table_id=table.id).all()
    if len(players) < MIN_PLAYERS:
        return jsonify({'ok': False, 'error': f'Minimum {MIN_PLAYERS} cochons requis !'})

    votes = [p.vote for p in players]
    if not all(v is not None for v in votes):
        return jsonify({'ok': False, 'error': 'Tout le monde n\'a pas voté !'})
    if len(set(votes)) != 1:
        return jsonify({'ok': False, 'error': 'Pas d\'unanimité sur le buy-in.'})

    buy_in = votes[0]
    table.buy_in = buy_in

    # Débiter le buy-in de chaque joueur
    for p in players:
        u = User.query.get(p.user_id)
        if not u.can_afford(buy_in):
            return jsonify({'ok': False, 'error': f'{u.username} n\'a pas assez de BitGroins !'})
        ok = debit_user_balance(u.id, buy_in,
            reason_code='poker_buy_in',
            reason_label='Mise de départ Groin Poker',
            details=f'Buy-in {buy_in} BG — table #{table.id}',
            reference_type='poker_table', reference_id=table.id)
        if not ok:
            return jsonify({'ok': False, 'error': f'Impossible de débiter {u.username}.'})
        p.chips = buy_in
        p.status = 'active'
        p.is_spectator = False

    # Dealer aléatoire
    dealer_idx = random.randint(0, len(players) - 1)
    table.dealer_seat = players[dealer_idx].seat

    # Démarrer la première main
    _start_new_hand(table, players)

    db.session.commit()
    return jsonify({'ok': True, 'message': '🐷 La partie démarre ! Que le meilleur cochon gagne !'})


def _start_new_hand(table: PokerTable, players: list[PokerPlayer]) -> None:
    """Distribue les cartes pour une nouvelle main."""
    active = [p for p in players if not p.is_spectator and p.chips > 0]
    if len(active) < 2:
        table.status = 'finished'
        return

    deck = build_deck()

    # Distribuer 2 cartes à chaque joueur actif
    for p in active:
        hole = [deck.pop(), deck.pop()]
        p.hole_json = json.dumps(hole)
        p.current_bet = 0
        p.has_folded = False
        p.has_acted = False
        p.status = 'active'

    # Community cards (5 cartes piochées mais non révélées)
    community = [deck.pop() for _ in range(5)]

    # Blinds
    dealer = next((p for p in active if p.seat == table.dealer_seat), active[0])
    dealer_idx = active.index(dealer)
    sb_player = active[(dealer_idx + 1) % len(active)]
    bb_player = active[(dealer_idx + 2) % len(active)]

    small_blind = max(1, int(table.buy_in * SMALL_BLIND_RATIO))
    big_blind = small_blind * 2

    sb_amount = min(small_blind, sb_player.chips)
    bb_amount = min(big_blind, bb_player.chips)

    sb_player.chips -= sb_amount
    sb_player.current_bet = sb_amount
    bb_player.chips -= bb_amount
    bb_player.current_bet = bb_amount

    table.pot = float(sb_amount + bb_amount)
    table.current_bet = bb_amount
    table.deck_json = json.dumps(deck)
    table.community_json = json.dumps(community)
    table.phase = 'preflop'
    table.status = 'playing'
    table.hand_number = (table.hand_number or 0) + 1

    # Prochain à parler = UTG (après BB)
    utg_idx = (dealer_idx + 3) % len(active)
    table.action_seat = active[utg_idx].seat

    state = {
        'small_blind': small_blind,
        'big_blind': big_blind,
        'sb_seat': sb_player.seat,
        'bb_seat': bb_player.seat,
        'groin_msg': random.choice(GROIN_MSGS),
    }
    table.state_json = json.dumps(state)


@poker_bp.route('/poker/action', methods=['POST'])
@limiter.limit("30 per minute")
def poker_action():
    """Le joueur effectue une action (fold/call/raise/check/all-in)."""
    user = _resolve_user()
    if not user:
        return jsonify({'ok': False, 'error': 'Non connecté'}), 401

    table = _get_active_table()
    if not table or table.status != 'playing':
        return jsonify({'ok': False, 'error': 'Pas de partie en cours.'})

    player = PokerPlayer.query.filter_by(table_id=table.id, user_id=user.id, is_spectator=False).first()
    if not player:
        return jsonify({'ok': False, 'error': 'Tu n\'es pas joueur actif.'})

    if table.action_seat != player.seat:
        return jsonify({'ok': False, 'error': 'Ce n\'est pas ton tour, cochon impatient !'})

    data = request.get_json(silent=True, force=True) or {}
    action = data.get('action')  # fold | check | call | raise | allin

    players = PokerPlayer.query.filter_by(table_id=table.id).order_by(PokerPlayer.seat).all()
    active = [p for p in players if not p.is_spectator and not p.has_folded and p.chips >= 0]

    to_call = (table.current_bet or 0) - (player.current_bet or 0)

    if action == 'fold':
        player.has_folded = True
        player.has_acted = True

    elif action == 'check':
        if to_call > 0:
            return jsonify({'ok': False, 'error': f'Tu dois suivre {to_call} BitGroins ou te coucher !'})
        player.has_acted = True

    elif action == 'call':
        amount = min(to_call, player.chips)
        player.chips -= amount
        player.current_bet = (player.current_bet or 0) + amount
        table.pot = (table.pot or 0) + amount
        player.has_acted = True

    elif action == 'raise':
        raise_to = int(data.get('amount', 0))
        min_raise = (table.current_bet or 0) + max(1, int(table.buy_in * SMALL_BLIND_RATIO) * 2)
        if raise_to < min_raise:
            return jsonify({'ok': False, 'error': f'Relance minimum : {min_raise} BitGroins !'})
        if raise_to > player.chips + (player.current_bet or 0):
            return jsonify({'ok': False, 'error': 'Pas assez de jetons pour cette relance !'})
        additional = raise_to - (player.current_bet or 0)
        player.chips -= additional
        player.current_bet = raise_to
        table.pot = (table.pot or 0) + additional
        table.current_bet = raise_to
        # Réinitialiser has_acted pour les autres
        for p in active:
            if p.id != player.id and not p.has_folded:
                p.has_acted = False
        player.has_acted = True

    elif action == 'allin':
        amount = player.chips
        player.current_bet = (player.current_bet or 0) + amount
        table.pot = (table.pot or 0) + amount
        if player.current_bet > (table.current_bet or 0):
            table.current_bet = player.current_bet
            for p in active:
                if p.id != player.id and not p.has_folded:
                    p.has_acted = False
        player.chips = 0
        player.has_acted = True

    else:
        return jsonify({'ok': False, 'error': 'Action inconnue, cochon !'})

    # Avancer le jeu
    _advance_game(table, players)
    db.session.commit()

    # Rafraîchir
    return _game_state_json(table, user)


def _advance_game(table: PokerTable, players: list[PokerPlayer]) -> None:
    """Détermine le prochain joueur ou passe à la phase suivante."""
    active_in_hand = [p for p in players if not p.is_spectator and not p.has_folded]
    can_act = [p for p in active_in_hand if p.chips > 0]

    # Un seul joueur restant → il remporte le pot
    if len(active_in_hand) == 1:
        _award_pot(table, active_in_hand, players)
        return

    # Tous ont agi et les mises sont égales ?
    all_acted = all(
        p.has_acted or p.chips == 0
        for p in active_in_hand
    )
    bets_equal = len(set(p.current_bet for p in active_in_hand if p.chips > 0 or p.current_bet > 0)) <= 1

    if all_acted and bets_equal:
        _next_phase(table, players)
        return

    # Prochain joueur
    seats = [p.seat for p in active_in_hand if p.chips > 0 or not p.has_acted]
    if not seats:
        _next_phase(table, players)
        return

    current_idx = next((i for i, p in enumerate(active_in_hand) if p.seat == table.action_seat), 0)
    next_idx = (current_idx + 1) % len(active_in_hand)
    for i in range(len(active_in_hand)):
        candidate = active_in_hand[(next_idx + i) % len(active_in_hand)]
        if not candidate.has_acted and (candidate.chips > 0 or candidate.current_bet < (table.current_bet or 0)):
            table.action_seat = candidate.seat
            return
    # Tout le monde a agi
    _next_phase(table, players)


def _next_phase(table: PokerTable, players: list[PokerPlayer]) -> None:
    """Passe à la phase suivante (flop/turn/river/showdown)."""
    phase = table.phase
    community = json.loads(table.community_json or '[]')

    # Réinitialiser les mises
    active = [p for p in players if not p.is_spectator and not p.has_folded]
    for p in players:
        p.current_bet = 0
        if not p.has_folded and not p.is_spectator:
            p.has_acted = False
    table.current_bet = 0

    # Trouver le premier joueur actif après le dealer
    dealer = next((p for p in players if p.seat == table.dealer_seat), players[0])
    dealer_idx = next((i for i, p in enumerate(active) if p.seat == dealer.seat), 0)
    first_idx = (dealer_idx + 1) % len(active) if active else 0
    table.action_seat = active[first_idx].seat if active else table.dealer_seat

    if phase == 'preflop':
        table.phase = 'flop'
        # Révéler les 3 premières cartes community
        state = json.loads(table.state_json or '{}')
        state['revealed'] = 3
        table.state_json = json.dumps(state)

    elif phase == 'flop':
        table.phase = 'turn'
        state = json.loads(table.state_json or '{}')
        state['revealed'] = 4
        table.state_json = json.dumps(state)

    elif phase == 'turn':
        table.phase = 'river'
        state = json.loads(table.state_json or '{}')
        state['revealed'] = 5
        table.state_json = json.dumps(state)

    elif phase == 'river':
        # SHOWDOWN
        _showdown(table, players)


def _showdown(table: PokerTable, players: list[PokerPlayer]) -> None:
    """Détermine le(s) gagnant(s) et distribue le pot."""
    community = json.loads(table.community_json or '[]')[:5]
    active = [p for p in players if not p.is_spectator and not p.has_folded]

    best_rank = None
    winners = []
    hand_results = {}

    for p in active:
        hole = json.loads(p.hole_json or '[]')
        all_cards = hole + community
        rank = best_5_from_7(all_cards)
        hand_results[p.id] = rank
        if best_rank is None or rank > best_rank:
            best_rank = rank
            winners = [p]
        elif rank == best_rank:
            winners.append(p)

    _award_pot(table, winners, players, hand_results)


def _award_pot(table: PokerTable, winners: list[PokerPlayer], all_players: list[PokerPlayer],
               hand_results: dict = None) -> None:
    """Distribue le pot aux gagnants."""
    if not winners:
        return

    pot = table.pot or 0
    share = round(pot / len(winners), 2)

    winner_names = []
    for w in winners:
        w.chips = (w.chips or 0) + share
        u = User.query.get(w.user_id)
        winner_names.append(u.username if u else '?')
        hand_label = hand_name(hand_results[w.id]) if hand_results and w.id in hand_results else 'meilleure main'
        credit_user_balance(
            w.user_id, share,
            reason_code='poker_win',
            reason_label='Victoire Groin Poker',
            details=f'Pot {pot:.0f} BG ({hand_label}) — table #{table.id}',
            reference_type='poker_table', reference_id=table.id,
        )

    # Enregistrer l'historique
    history = PokerHandHistory(
        table_id=table.id,
        hand_number=table.hand_number or 1,
        pot=pot,
        winner_ids=json.dumps([w.user_id for w in winners]),
        hand_results=json.dumps({str(k): list(v) for k, v in (hand_results or {}).items()}),
        community_json=table.community_json,
        created_at=datetime.utcnow(),
    )
    db.session.add(history)

    # Mettre les joueurs à 0 en spectateurs
    for p in all_players:
        if not p.is_spectator and p.chips <= 0 and p not in winners:
            p.is_spectator = True
            p.status = 'spectator'

    state = json.loads(table.state_json or '{}')
    state['last_winners'] = winner_names
    state['last_pot'] = pot
    state['groin_msg'] = random.choice(GROIN_MSGS)
    table.state_json = json.dumps(state)
    table.pot = 0

    # Vérifier si la partie est terminée (1 joueur avec jetons)
    still_playing = [p for p in all_players if not p.is_spectator and p.chips > 0]
    if len(still_playing) <= 1:
        table.status = 'finished'
        if still_playing:
            # Le dernier restant encaisse ses jetons
            last = still_playing[0]
            u = User.query.get(last.user_id)
            if last.chips > 0:
                credit_user_balance(
                    last.user_id, last.chips,
                    reason_code='poker_leftover',
                    reason_label='Jetons restants Groin Poker',
                    details=f'Jetons restants: {last.chips:.0f} BG — table #{table.id}',
                    reference_type='poker_table', reference_id=table.id,
                )
                last.chips = 0
        return

    # Sinon, nouvelle main
    db.session.flush()
    # Faire tourner le dealer
    active_seats = sorted(p.seat for p in still_playing)
    cur_dealer_idx = next((i for i, s in enumerate(active_seats) if s >= table.dealer_seat), 0)
    next_dealer_seat = active_seats[(cur_dealer_idx + 1) % len(active_seats)]
    table.dealer_seat = next_dealer_seat

    _start_new_hand(table, all_players)


@poker_bp.route('/poker/leave', methods=['POST'])
@limiter.limit("5 per minute")
def poker_leave():
    """Quitter la partie — récupère ses jetons."""
    user = _resolve_user()
    if not user:
        return jsonify({'ok': False, 'error': 'Non connecté'}), 401

    table = _get_active_table()
    if not table:
        return jsonify({'ok': False, 'error': 'Pas de table trouvée.'})

    player = PokerPlayer.query.filter_by(table_id=table.id, user_id=user.id).first()
    if not player:
        return jsonify({'ok': False, 'error': 'Pas à cette table.'})

    chips = player.chips or 0
    if chips > 0:
        credit_user_balance(
            user.id, chips,
            reason_code='poker_cashout',
            reason_label='Retrait Groin Poker',
            details=f'Cashout {chips:.0f} BG en quittant la table #{table.id}',
            reference_type='poker_table', reference_id=table.id,
        )
        player.chips = 0

    player.status = 'left'
    player.has_folded = True

    # Si c'était au tour de ce joueur, avancer
    players = PokerPlayer.query.filter_by(table_id=table.id).all()
    if table.action_seat == player.seat and table.status == 'playing':
        _advance_game(table, players)

    db.session.commit()
    db.session.refresh(user)

    return jsonify({
        'ok': True,
        'chips_returned': chips,
        'new_balance': round(user.balance or 0, 2),
        'message': f'🐷 Tu quittes la porcherie avec {chips:.0f} BitGroins. À bientôt, couard !',
    })


@poker_bp.route('/poker/state')
def poker_state():
    """Renvoie l'état courant de la table (polling)."""
    user = _resolve_user()
    if not user:
        return jsonify({'ok': False, 'error': 'Non connecté'}), 401

    table = _get_active_table()
    if not table:
        return jsonify({'ok': False, 'table': None})

    return _game_state_json(table, user)


def _game_state_json(table: PokerTable, user: User):
    players = PokerPlayer.query.filter_by(table_id=table.id).order_by(PokerPlayer.seat).all()
    my_seat = next((p for p in players if p.user_id == user.id), None)

    community = json.loads(table.community_json or '[]')
    state = json.loads(table.state_json or '{}')
    revealed = state.get('revealed', 0)

    # Cartes communes visibles
    visible_community = community[:revealed] if table.phase != 'preflop' else []

    players_data = []
    for p in players:
        u = User.query.get(p.user_id)
        hole = json.loads(p.hole_json or '[]')
        # Ne montrer les cartes que si c'est le joueur lui-même ou showdown
        show_hole = (p.user_id == user.id and not p.has_folded) or table.phase == 'showdown'
        players_data.append({
            'seat': p.seat,
            'username': u.username if u else '?',
            'chips': round(p.chips or 0, 2),
            'current_bet': round(p.current_bet or 0, 2),
            'has_folded': p.has_folded,
            'is_spectator': p.is_spectator,
            'is_active': table.action_seat == p.seat,
            'vote': p.vote,
            'status': p.status,
            'hole': hole if show_hole else [{'rank': '?', 'suit': '🐷', 'label': '??'} for _ in hole],
            'is_me': p.user_id == user.id,
        })

    my_hole = []
    if my_seat and not my_seat.has_folded:
        my_hole = json.loads(my_seat.hole_json or '[]')

    votes_data = {str(opt): sum(1 for p in players if p.vote == opt) for opt in BUY_IN_OPTIONS}

    return jsonify({
        'ok': True,
        'table_id': table.id,
        'status': table.status,
        'phase': table.phase,
        'pot': round(table.pot or 0, 2),
        'current_bet': round(table.current_bet or 0, 2),
        'buy_in': table.buy_in,
        'action_seat': table.action_seat,
        'dealer_seat': table.dealer_seat,
        'community': visible_community,
        'players': players_data,
        'my_seat': my_seat.seat if my_seat else None,
        'my_chips': round((my_seat.chips or 0), 2) if my_seat else 0,
        'my_hole': my_hole,
        'my_bet': round((my_seat.current_bet or 0), 2) if my_seat else 0,
        'my_folded': my_seat.has_folded if my_seat else False,
        'my_spectator': my_seat.is_spectator if my_seat else True,
        'my_voted': my_seat.vote if my_seat else None,
        'state': state,
        'player_count': len(players),
        'votes': votes_data,
        'buy_in_options': BUY_IN_OPTIONS,
        'min_players': MIN_PLAYERS,
        'groin_taunt': random.choice(BLUFF_TAUNTS) if table.status == 'playing' else '',
    })
