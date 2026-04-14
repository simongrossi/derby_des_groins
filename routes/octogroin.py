from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from extensions import db, limiter
from models import Pig, User
from services.octogroin_service import (
    ACTIONS_PER_ROUND,
    OctogroinError,
    cancel_duel,
    create_duel,
    get_matchup_rating,
    get_round_duration_seconds,
    get_stake_bounds,
    get_visible_duel,
    join_duel,
    list_open_duels,
    list_user_duels,
    submit_actions,
)
from services.octogroin_engine import ACTIONS

octogroin_bp = Blueprint('octogroin', __name__)


def _current_user():
    uid = session.get('user_id')
    return User.query.get(uid) if uid else None


def _require_login():
    user = _current_user()
    if user is None:
        return None, redirect(url_for('auth.login'))
    return user, None


@octogroin_bp.route('/octogroin')
def lobby():
    user, redir = _require_login()
    if redir:
        return redir
    min_stake, max_stake = get_stake_bounds()
    open_duels = list_open_duels()
    my_duels = list_user_duels(user)
    my_pigs = [p for p in user.pigs if p.is_alive and not p.is_injured]
    return render_template(
        'octogroin_lobby.html',
        user=user,
        active_page='octogroin',
        open_duels=open_duels,
        my_duels=my_duels,
        my_pigs=my_pigs,
        min_stake=min_stake,
        max_stake=max_stake,
        default_stake=min_stake,
    )


@octogroin_bp.route('/octogroin/create', methods=['POST'])
@limiter.limit("20 per minute")
def create():
    user, redir = _require_login()
    if redir:
        return redir

    pig_id = request.form.get('pig_id', type=int)
    stake = request.form.get('stake', type=float)
    visibility = (request.form.get('visibility') or 'public').lower()
    challenged_username = (request.form.get('challenged_username') or '').strip()

    pig = Pig.query.get(pig_id) if pig_id else None
    challenged_user = None
    if visibility == 'direct':
        if not challenged_username:
            flash("Indique le nom de l'adversaire pour un défi direct.", 'error')
            return redirect(url_for('octogroin.lobby'))
        challenged_user = User.query.filter_by(username=challenged_username).first()
        if challenged_user is None:
            flash("Adversaire introuvable.", 'error')
            return redirect(url_for('octogroin.lobby'))

    try:
        duel = create_duel(user, pig, stake or 0.0, visibility, challenged_user)
    except OctogroinError as exc:
        db.session.rollback()
        flash(str(exc), 'error')
        return redirect(url_for('octogroin.lobby'))

    flash("Duel ouvert ! En attente d'un adversaire.", 'success')
    return redirect(url_for('octogroin.duel_view', duel_id=duel.id))


@octogroin_bp.route('/octogroin/<int:duel_id>/join', methods=['POST'])
@limiter.limit("20 per minute")
def join(duel_id):
    user, redir = _require_login()
    if redir:
        return redir

    duel = get_visible_duel(duel_id, user)
    if duel is None:
        flash("Duel introuvable.", 'error')
        return redirect(url_for('octogroin.lobby'))

    pig_id = request.form.get('pig_id', type=int)
    pig = Pig.query.get(pig_id) if pig_id else None

    try:
        join_duel(duel, user, pig)
    except OctogroinError as exc:
        db.session.rollback()
        flash(str(exc), 'error')
        return redirect(url_for('octogroin.lobby'))

    flash("Duel rejoint, que le meilleur groin gagne !", 'success')
    return redirect(url_for('octogroin.duel_view', duel_id=duel.id))


@octogroin_bp.route('/octogroin/<int:duel_id>/cancel', methods=['POST'])
@limiter.limit("20 per minute")
def cancel(duel_id):
    user, redir = _require_login()
    if redir:
        return redir

    duel = get_visible_duel(duel_id, user)
    if duel is None:
        flash("Duel introuvable.", 'error')
        return redirect(url_for('octogroin.lobby'))

    try:
        cancel_duel(duel, user)
    except OctogroinError as exc:
        db.session.rollback()
        flash(str(exc), 'error')
        return redirect(url_for('octogroin.duel_view', duel_id=duel.id))

    flash("Duel annulé, mise remboursée.", 'success')
    return redirect(url_for('octogroin.lobby'))


@octogroin_bp.route('/octogroin/<int:duel_id>')
def duel_view(duel_id):
    user, redir = _require_login()
    if redir:
        return redir

    duel = get_visible_duel(duel_id, user)
    if duel is None:
        flash("Duel introuvable.", 'error')
        return redirect(url_for('octogroin.lobby'))

    # Compute whether this user can join (used to render the Rejoindre form).
    can_join = (
        duel.status == 'waiting'
        and duel.player1_id != user.id
        and (duel.visibility == 'public' or duel.challenged_user_id == user.id)
    )
    my_pigs = []
    if can_join:
        my_pigs = [p for p in user.pigs if p.is_alive and not p.is_injured]

    matchup = get_matchup_rating(duel)

    return render_template(
        'octogroin_duel.html',
        user=user,
        active_page='octogroin',
        duel=duel,
        round_duration=get_round_duration_seconds(),
        can_join=can_join,
        my_pigs=my_pigs,
        matchup=matchup,
    )


@octogroin_bp.route('/octogroin/<int:duel_id>/actions', methods=['POST'])
@limiter.limit("30 per minute")
def submit(duel_id):
    user = _current_user()
    if user is None:
        return jsonify({'ok': False, 'error': 'Non connecté'}), 401

    duel = get_visible_duel(duel_id, user)
    if duel is None:
        return jsonify({'ok': False, 'error': 'Duel introuvable'}), 404

    payload = request.get_json(silent=True) or {}
    actions = payload.get('actions')

    try:
        result = submit_actions(duel, user, actions)
    except OctogroinError as exc:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(exc)}), 400

    return jsonify({
        'ok': True,
        'resolved': result['resolved'],
        'status': duel.status,
        'current_round': duel.current_round,
        'pig1_position': duel.pig1_position,
        'pig2_position': duel.pig2_position,
        'pig1_endurance': duel.pig1_endurance,
        'pig2_endurance': duel.pig2_endurance,
        'winner_id': duel.winner_id,
    })


@octogroin_bp.route('/octogroin/<int:duel_id>/replay')
def duel_replay(duel_id):
    user = _current_user()
    if user is None:
        return jsonify({'ok': False, 'error': 'Non connecté'}), 401
    duel = get_visible_duel(duel_id, user)
    if duel is None:
        return jsonify({'ok': False, 'error': 'Duel introuvable'}), 404
    try:
        import json as _json
        rounds = _json.loads(duel.replay_json) if duel.replay_json else []
    except (TypeError, ValueError):
        rounds = []
    return jsonify({'ok': True, 'rounds': rounds})


@octogroin_bp.route('/octogroin/<int:duel_id>/state')
def duel_state(duel_id):
    user = _current_user()
    if user is None:
        return jsonify({'ok': False, 'error': 'Non connecté'}), 401

    duel = get_visible_duel(duel_id, user)
    if duel is None:
        return jsonify({'ok': False, 'error': 'Duel introuvable'}), 404

    return jsonify({
        'ok': True,
        'id': duel.id,
        'status': duel.status,
        'visibility': duel.visibility,
        'stake': duel.stake,
        'current_round': duel.current_round,
        'pig1_position': duel.pig1_position,
        'pig2_position': duel.pig2_position,
        'pig1_endurance': duel.pig1_endurance,
        'pig2_endurance': duel.pig2_endurance,
        'arena_type': duel.arena_type,
        'round_deadline_at': duel.round_deadline_at.isoformat() if duel.round_deadline_at else None,
        'winner_id': duel.winner_id,
        'p1_submitted': bool(duel.round_actions_p1),
        'p2_submitted': bool(duel.round_actions_p2),
        'you_are': 'p1' if user.id == duel.player1_id else ('p2' if user.id == duel.player2_id else 'spectator'),
        'allowed_actions': list(ACTIONS),
        'matchup': get_matchup_rating(duel),
    })
