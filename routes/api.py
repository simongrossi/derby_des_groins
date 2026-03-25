from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime
import json as _json

from extensions import db, limiter
from models import User, Pig, Race, Participant, Bet
from data import SCHOOL_COOLDOWN_MINUTES, MIN_INJURY_RISK, DEFAULT_PIG_WEIGHT_KG
from helpers import (
    get_user_active_pigs, calculate_pig_power,
    get_weight_profile, get_seconds_until, get_cooldown_remaining,
    xp_for_level, get_first_injured_pig,
    get_prix_moyen_groin,
)

api_bp = Blueprint('api', __name__)


@api_bp.route('/veterinaire/<int:pig_id>')
def veterinaire(pig_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('auth.login'))
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id:
        return redirect(url_for('pig.mon_cochon'))
    if not pig.is_alive:
        return redirect(url_for('abattoir.cimetiere'))
    if not pig.is_injured:
        return redirect(url_for('pig.mon_cochon'))
    seconds_left = get_seconds_until(pig.vet_deadline)
    return render_template('veterinaire.html', user=user, pig=pig, seconds_left=seconds_left)


@api_bp.route('/veterinaire')
def veterinaire_index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('auth.login'))
    injured_pig = get_first_injured_pig(user.id)
    if injured_pig:
        return redirect(url_for('api.veterinaire', pig_id=injured_pig.id))

    pigs = get_user_active_pigs(user)
    pigs_data = []
    for pig in pigs:
        pig.update_vitals()
        injury_risk = round(pig.injury_risk or MIN_INJURY_RISK, 1)
        pigs_data.append({
            'pig': pig,
            'injury_risk': injury_risk,
            'power': round(calculate_pig_power(pig), 1),
            'status': 'eleve' if injury_risk > 25 else ('modere' if injury_risk > 15 else 'faible'),
        })

    pigs_data.sort(key=lambda item: item['injury_risk'], reverse=True)
    avg_risk = round(sum(item['injury_risk'] for item in pigs_data) / len(pigs_data), 1) if pigs_data else 0.0
    max_risk = max((item['injury_risk'] for item in pigs_data), default=0.0)

    return render_template(
        'veterinaire_lobby.html',
        user=user,
        pigs_data=pigs_data,
        avg_risk=avg_risk,
        max_risk=max_risk,
    )


@api_bp.route('/api/vet/solve', methods=['POST'])
@limiter.limit("10 per minute")
def vet_solve():
    if 'user_id' not in session:
        return jsonify({'error': 'Non connecté'}), 401
    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return jsonify({'error': 'Session invalide'}), 401
    payload = request.get_json(silent=True) or {}
    pig_id = payload.get('pig_id')
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id:
        return jsonify({'error': 'Cochon introuvable'}), 404
    if not pig.is_alive:
        return jsonify({'dead': True, 'message': "Trop tard... il est passé de l'autre côté."}), 200
    if not pig.is_injured:
        return jsonify({'already_healed': True}), 200
    if pig.vet_deadline and datetime.utcnow() > pig.vet_deadline:
        pig.kill(cause='blessure')
        db.session.commit()
        return jsonify({'dead': True, 'message': 'Le délai était dépassé. RIP.'}), 200

    pig.heal()
    pig.injury_risk = min(35.0, max(MIN_INJURY_RISK, (pig.injury_risk or MIN_INJURY_RISK) + 2.0))
    pig.energy = max(0, pig.energy - 10)
    pig.happiness = max(0, pig.happiness - 5)
    db.session.commit()
    return jsonify({'healed': True, 'message': f"{pig.name} s'en sort ! Repos, soupe tiède et pas de sprint tout de suite."})


@api_bp.route('/api/vet/timeout', methods=['POST'])
@limiter.limit("10 per minute")
def vet_timeout():
    if 'user_id' not in session:
        return jsonify({'error': 'Non connecté'}), 401
    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return jsonify({'error': 'Session invalide'}), 401
    payload = request.get_json(silent=True) or {}
    pig_id = payload.get('pig_id')
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id:
        return jsonify({'error': 'Cochon introuvable'}), 404
    if pig.is_alive and pig.is_injured:
        pig.kill(cause='blessure')
        db.session.commit()
    return jsonify({'dead': True})


@api_bp.route('/api/countdown')
@limiter.limit("30 per minute")
def api_countdown():
    next_race = Race.query.filter_by(status='open').order_by(Race.scheduled_at).first()
    if not next_race:
        return jsonify({'seconds': 86400, 'race_id': None})
    now = datetime.now()
    seconds = max(0, int((next_race.scheduled_at - now).total_seconds()))
    return jsonify({'seconds': seconds, 'race_id': next_race.id})


@api_bp.route('/api/latest_result')
@limiter.limit("30 per minute")
def api_latest_result():
    race = Race.query.filter_by(status='finished').order_by(Race.finished_at.desc()).first()
    if not race:
        return jsonify({'result': None})
    participants = Participant.query.filter_by(race_id=race.id).order_by(Participant.finish_position).all()
    return jsonify({
        'result': {
            'winner': race.winner_name, 'odds': race.winner_odds,
            'finished_at': race.finished_at.strftime('%H:%M') if race.finished_at else None,
            'positions': [
                {'name': p.name, 'emoji': p.emoji, 'avatar_url': p.avatar_url,
                 'pos': p.finish_position, 'is_player': p.pig_id is not None, 'owner': p.owner_name}
                for p in participants
            ]
        }
    })


@api_bp.route('/api/pig')
@limiter.limit("30 per minute")
def api_pig():
    if 'user_id' not in session:
        return jsonify({'error': 'Non connecté'}), 401
    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return jsonify({'error': 'Session invalide'}), 401
    pig = Pig.query.filter_by(user_id=user.id, is_alive=True).first()
    if not pig:
        return jsonify({'error': 'Pas de cochon'}), 404
    pig.update_vitals()
    return jsonify({
        'name': pig.name, 'emoji': pig.emoji,
        'level': pig.level, 'xp': pig.xp,
        'xp_next': xp_for_level(pig.level + 1),
        'stats': {k: round(getattr(pig, k), 1) for k in ['vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral']},
        'energy': round(pig.energy, 1), 'hunger': round(pig.hunger, 1),
        'happiness': round(pig.happiness, 1),
        'weight_kg': round(pig.weight_kg or DEFAULT_PIG_WEIGHT_KG, 1),
        'weight_profile': get_weight_profile(pig),
        'power': round(calculate_pig_power(pig), 1),
        'origin': pig.origin_country, 'origin_flag': pig.origin_flag,
        'races_entered': pig.races_entered, 'races_won': pig.races_won,
        'school_sessions_completed': pig.school_sessions_completed or 0,
        'school_cooldown': get_cooldown_remaining(pig.last_school_at, SCHOOL_COOLDOWN_MINUTES),
        'is_injured': pig.is_injured,
        'injury_risk': round(pig.injury_risk or MIN_INJURY_RISK, 1),
        'vet_seconds_left': get_seconds_until(pig.vet_deadline) if pig.is_injured else 0,
        'avatar_url': pig.avatar_url,
    })



@api_bp.route('/api/prix-groin')
@limiter.limit("30 per minute")
def api_prix_groin():
    return jsonify({'prix': get_prix_moyen_groin()})


@api_bp.route('/api/race/<int:race_id>/replay')
@limiter.limit("30 per minute")
def api_race_replay(race_id):
    """Retourne le replay JSON d'une course terminée pour l'animation."""
    race = Race.query.get(race_id)
    if not race:
        return jsonify({'error': 'Course introuvable, comme un cochon dans un sauna'}), 404
    if race.status not in ('finished', 'cancelled'):
        return jsonify({'error': "La course n'est pas encore terminée, patience !"}), 425
    if not race.replay_json:
        return jsonify({'error': "Pas de replay disponible, le greffier a oublie de filmer"}), 404

    raw = _json.loads(race.replay_json)
    # replay_json may be a bare list of turns (old format) or a dict
    if isinstance(raw, list):
        replay = {'turns': raw}
    else:
        replay = raw

    participants_db = Participant.query.filter_by(race_id=race_id).all()
    pig_avatars = {}
    pig_ids = [p.pig_id for p in participants_db if p.pig_id]
    if pig_ids:
        from models import Pig as PigModel
        for pig in PigModel.query.filter(PigModel.id.in_(pig_ids)).all():
            pig_avatars[pig.id] = pig.avatar_url
    participant_meta = {
        str(p.id): {
            'emoji': p.emoji,
            'owner': p.owner_name,
            'finish_position': p.finish_position,
            'avatar_url': pig_avatars.get(p.pig_id),
        }
        for p in participants_db
    }
    replay['participant_meta'] = participant_meta
    replay['race_id'] = race_id
    replay['winner_name'] = race.winner_name
    replay['finished_at'] = race.finished_at.strftime('%H:%M') if race.finished_at else None
    return jsonify(replay)


@api_bp.route('/api/race/latest/replay')
@limiter.limit("30 per minute")
def api_latest_race_replay():
    """Retourne le replay de la derniere course terminee."""
    race = Race.query.filter_by(status='finished').order_by(Race.finished_at.desc()).first()
    if not race:
        return jsonify({'error': 'Aucune course terminee, les cochons sont encore en pyjama'}), 404
    return api_race_replay(race.id)


@api_bp.route('/api/race/live-state')
@limiter.limit("60 per minute")
def api_race_live_state():
    """Central synchronization endpoint for the circuit overlay.

    Returns the current phase of the race lifecycle so all connected clients
    can show the same overlay at the same time.
    """
    now = datetime.now()

    # Latest finished race (for replay)
    last_finished = Race.query.filter_by(status='finished').order_by(Race.finished_at.desc()).first()
    finished_race_id = last_finished.id if last_finished else None

    # Next open race
    next_race = Race.query.filter_by(status='open').order_by(Race.scheduled_at).first()
    if not next_race:
        return jsonify({
            'phase': 'idle',
            'race_id': None,
            'seconds_to_start': None,
            'finished_race_id': finished_race_id,
            'server_time': now.isoformat(),
        })

    seconds = int((next_race.scheduled_at - now).total_seconds())

    if seconds > 50:
        phase = 'idle'
    elif seconds > 10:
        phase = 'pre_race'
    elif seconds > 0:
        phase = 'countdown'
    else:
        phase = 'racing'  # Race is due but not yet processed by scheduler

    return jsonify({
        'phase': phase,
        'race_id': next_race.id,
        'seconds_to_start': max(0, seconds),
        'finished_race_id': finished_race_id,
        'server_time': now.isoformat(),
    })


@api_bp.route('/api/race/<int:race_id>/pre-race')
@limiter.limit("30 per minute")
def api_race_pre_race(race_id):
    """Returns participant lineup + circuit segments for the pre-race overlay."""
    race = Race.query.get(race_id)
    if not race:
        return jsonify({'error': 'Course introuvable'}), 404

    participants = Participant.query.filter_by(race_id=race.id).all()

    pre_pig_ids = [p.pig_id for p in participants if p.pig_id]
    pre_pig_avatars = {}
    if pre_pig_ids:
        from models import Pig as PigModel
        for pig in PigModel.query.filter(PigModel.id.in_(pre_pig_ids)).all():
            pre_pig_avatars[pig.id] = pig.avatar_url

    # Parse pre-generated segments
    segments = []
    if race.preview_segments_json:
        try:
            segments = _json.loads(race.preview_segments_json)
        except (ValueError, TypeError):
            pass

    return jsonify({
        'race_id': race.id,
        'scheduled_at': race.scheduled_at.strftime('%H:%M') if race.scheduled_at else None,
        'status': race.status,
        'segments': segments,
        'participants': [
            {
                'id': p.id,
                'name': p.name,
                'emoji': p.emoji,
                'odds': round(p.odds, 2) if p.odds else None,
                'win_probability': round(p.win_probability, 3) if p.win_probability else None,
                'owner_name': p.owner_name,
                'pig_id': p.pig_id,
                'strategy': p.strategy,
                'avatar_url': pre_pig_avatars.get(p.pig_id),
            }
            for p in participants
        ],
    })


@api_bp.route('/api/race/<int:race_id>/bets-spectator')
@limiter.limit("30 per minute")
def api_race_bets_spectator(race_id):
    """Returns all bets placed on a race for spectator view (anonymized amounts)."""
    race = Race.query.get(race_id)
    if not race:
        return jsonify({'error': 'Course introuvable'}), 404

    bets = Bet.query.filter_by(race_id=race.id).all()

    bets_data = []
    for bet in bets:
        user = User.query.get(bet.user_id)
        bets_data.append({
            'username': user.username if user else '???',
            'pig_name': bet.pig_name,
            'bet_type': getattr(bet, 'bet_type', 'win'),
            'amount': bet.amount,
            'odds': round(bet.odds_at_bet, 2) if bet.odds_at_bet else None,
            'status': bet.status,
        })

    return jsonify({'race_id': race.id, 'bets': bets_data})


@api_bp.route('/circuit')
def race_circuit():
    """Page du circuit live — visualisation plein ecran."""
    user = User.query.get(session['user_id']) if 'user_id' in session else None
    return render_template('race_circuit.html', user=user, active_page='circuit')


@api_bp.route('/live')
def race_live():
    """Page d'animation live de la derniere course."""
    user = User.query.get(session['user_id']) if 'user_id' in session else None
    race = Race.query.filter_by(status='finished').order_by(Race.finished_at.desc()).first()
    race_id = race.id if race else None
    return render_template('race_live.html', user=user, race_id=race_id, active_page='live')
