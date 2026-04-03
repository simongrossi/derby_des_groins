import random

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from extensions import db, limiter
from helpers import get_user_active_pigs
from helpers.game_data import get_hangman_words
from models import User
from services.finance_service import credit_user_balance

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
    return [letter if letter in guessed_set else '_' for letter in word]


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


@cochon_pendu_bp.route('/cochon-pendu')
def cochon_pendu():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    current_state = session.get('cochon_pendu_game')
    if not current_state or current_state.get('status') in ('won', 'lost'):
        session['cochon_pendu_game'] = _new_game_state()
        session.modified = True

    user = User.query.get(user_id)
    return render_template(
        'cochon_pendu.html',
        user=user,
        active_page='cochon_pendu',
        game_state=_serialize_state(session['cochon_pendu_game']),
        reward=WIN_REWARD,
        happiness_penalty=LOSS_HAPPINESS_PENALTY,
        energy_penalty=LOSS_ENERGY_PENALTY,
    )


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
