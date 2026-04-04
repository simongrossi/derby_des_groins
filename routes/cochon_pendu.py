import random
from datetime import date, datetime

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from data import PENDU_FREE_PLAYS_PER_DAY, PENDU_EXTRA_PLAY_COST
from extensions import db, limiter
from helpers import get_user_active_pigs
from helpers.game_data import get_hangman_words
from models import User
from services.finance_service import credit_user_balance, debit_user_balance

cochon_pendu_bp = Blueprint('cochon_pendu', __name__)

MAX_ERRORS = 7
WIN_REWARD = 50
LOSS_HAPPINESS_PENALTY = 20
LOSS_ENERGY_PENALTY = 10


def _new_game_state():
    words = get_hangman_words()
    return {
        'word': random.choice(words),
        'guessed_letters': [],
        'errors': 0,
        'status': 'playing',
        'reward_granted': False,
        'penalty_applied': False,
    }


def _get_state():
    state = session.get('cochon_pendu_game')
    if not state:
        state = _new_game_state()
        session['cochon_pendu_game'] = state
        session.modified = True
    return state


def _build_masked_word(word, guessed_letters):
    guessed_set = set(guessed_letters)
    masked = []
    for letter in word:
        if letter == ' ':
            masked.append(' ')
        else:
            masked.append(letter if letter in guessed_set else '_')
    return masked


def _serialize_state(state):
    word = state['word']
    guessed_letters = state.get('guessed_letters', [])
    masked = _build_masked_word(word, guessed_letters)
    return {
        'masked_word': masked,
        'guessed_letters': guessed_letters,
        'errors': state.get('errors', 0),
        'max_errors': MAX_ERRORS,
        'status': state.get('status', 'playing'),
        'word': word if state.get('status') in ('won', 'lost') else None,
    }


def _sync_pendu_daily_counter(user):
    """Reset the daily counter when the stored play date is from a previous day."""
    if getattr(user, 'is_admin', False):
        return
    today = date.today()
    if user.last_pendu_at and user.last_pendu_at.date() < today and user.pendu_plays_today:
        user.pendu_plays_today = 0
        db.session.commit()
        db.session.refresh(user)


def _get_pendu_info(user):
    """Return dict with remaining free plays and extra play cost."""
    if getattr(user, 'is_admin', False):
        return {'remaining_free': PENDU_FREE_PLAYS_PER_DAY, 'extra_cost': 0, 'plays_today': 0}
    _sync_pendu_daily_counter(user)
    plays = user.pendu_plays_today or 0
    remaining = max(0, PENDU_FREE_PLAYS_PER_DAY - plays)
    return {
        'remaining_free': remaining,
        'extra_cost': PENDU_EXTRA_PLAY_COST,
        'plays_today': plays,
    }


@cochon_pendu_bp.route('/cochon-pendu')
def cochon_pendu():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    user = User.query.get(user_id)
    pendu_info = _get_pendu_info(user)

    current_state = session.get('cochon_pendu_game')
    if not current_state:
        # First ever visit: auto-start a free game
        _record_new_game(user)
        session['cochon_pendu_game'] = _new_game_state()
        session.modified = True

    return render_template(
        'cochon_pendu.html',
        user=user,
        active_page='cochon_pendu',
        game_state=_serialize_state(session['cochon_pendu_game']),
        reward=WIN_REWARD,
        happiness_penalty=LOSS_HAPPINESS_PENALTY,
        energy_penalty=LOSS_ENERGY_PENALTY,
        pendu_info=pendu_info,
        free_plays=PENDU_FREE_PLAYS_PER_DAY,
        extra_cost=PENDU_EXTRA_PLAY_COST,
    )


def _record_new_game(user):
    """Increment the daily play counter."""
    user.last_pendu_at = datetime.utcnow()
    user.pendu_plays_today = (user.pendu_plays_today or 0) + 1
    db.session.commit()


@cochon_pendu_bp.route('/api/cochon-pendu/new-game', methods=['POST'])
@limiter.limit('20 per minute')
def cochon_pendu_new_game():
    """Start a new game. Free up to PENDU_FREE_PLAYS_PER_DAY/day, then costs PENDU_EXTRA_PLAY_COST BG."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'error': 'Non connecté'}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({'ok': False, 'error': 'Utilisateur introuvable'}), 404

    info = _get_pendu_info(user)

    if info['remaining_free'] <= 0 and not getattr(user, 'is_admin', False):
        # Paid replay
        cost = PENDU_EXTRA_PLAY_COST
        if (user.balance or 0) < cost:
            return jsonify({
                'ok': False,
                'error': f'Fonds insuffisants. Une partie supplémentaire coûte {cost} 🪙.',
                'extra_cost': cost,
            }), 400

        debit_ok = debit_user_balance(
            user.id,
            cost,
            reason_code='pendu_replay',
            reason_label='Rejouer au Cochon Pendu',
            details=f'Rejeu payant du Cochon Pendu ({cost} 🪙).',
            reference_type='user',
            reference_id=user.id,
        )
        if not debit_ok:
            db.session.rollback()
            return jsonify({'ok': False, 'error': 'Fonds insuffisants'}), 400

    _record_new_game(user)
    db.session.refresh(user)
    session['cochon_pendu_game'] = _new_game_state()
    session.modified = True

    info_after = _get_pendu_info(user)
    return jsonify({
        'ok': True,
        'new_balance': round(user.balance or 0.0, 2),
        'remaining_free': info_after['remaining_free'],
        'extra_cost': PENDU_EXTRA_PLAY_COST,
    })


@cochon_pendu_bp.route('/api/cochon-pendu/guess', methods=['POST'])
@limiter.limit('60 per minute')
def cochon_pendu_guess():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'error': 'Non connecté'}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({'ok': False, 'error': 'Utilisateur introuvable'}), 404

    payload = request.get_json(silent=True) or {}
    letter = (payload.get('letter') or '').strip().upper()
    if len(letter) != 1 or not letter.isalpha():
        return jsonify({'ok': False, 'error': 'Lettre invalide'}), 400

    state = _get_state()
    if state.get('status') in ('won', 'lost'):
        return jsonify({'ok': True, **_serialize_state(state), 'already_finished': True})

    guessed_letters = state.setdefault('guessed_letters', [])
    if letter in guessed_letters:
        return jsonify({'ok': True, **_serialize_state(state), 'already_guessed': True})

    guessed_letters.append(letter)
    word = state['word']

    if letter not in word:
        state['errors'] = min(MAX_ERRORS, int(state.get('errors', 0)) + 1)

    masked = _build_masked_word(word, guessed_letters)
    if '_' not in masked:
        state['status'] = 'won'
    elif state.get('errors', 0) >= MAX_ERRORS:
        state['status'] = 'lost'

    if state['status'] == 'won' and not state.get('reward_granted'):
        credit_user_balance(
            user.id,
            WIN_REWARD,
            reason_code='cochon_pendu_win',
            reason_label='Victoire Cochon Pendu',
            details='Mot trouvé dans le mini-jeu Cochon Pendu.',
            reference_type='user',
            reference_id=user.id,
        )
        state['reward_granted'] = True

    if state['status'] == 'lost' and not state.get('penalty_applied'):
        player_pigs = get_user_active_pigs(user)
        if player_pigs:
            pig = player_pigs[0]
            pig.happiness = max(0.0, float(pig.happiness or 0.0) - LOSS_HAPPINESS_PENALTY)
            pig.energy = max(0.0, float(pig.energy or 0.0) - LOSS_ENERGY_PENALTY)
        state['penalty_applied'] = True

    session['cochon_pendu_game'] = state
    session.modified = True
    db.session.commit()
    db.session.refresh(user)

    response_state = _serialize_state(state)
    response_state['balance'] = round(user.balance or 0.0, 2)

    return jsonify({'ok': True, **response_state})
