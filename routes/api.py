from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime

from extensions import db
from models import User, Pig, Race, Participant
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
def vet_solve():
    if 'user_id' not in session:
        return jsonify({'error': 'Non connecté'}), 401
    user = User.query.get(session['user_id'])
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
def vet_timeout():
    if 'user_id' not in session:
        return jsonify({'error': 'Non connecté'}), 401
    user = User.query.get(session['user_id'])
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
def api_countdown():
    next_race = Race.query.filter_by(status='open').order_by(Race.scheduled_at).first()
    if not next_race:
        return jsonify({'seconds': 86400, 'race_id': None})
    now = datetime.now()
    seconds = max(0, int((next_race.scheduled_at - now).total_seconds()))
    return jsonify({'seconds': seconds, 'race_id': next_race.id})


@api_bp.route('/api/latest_result')
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
                {'name': p.name, 'emoji': p.emoji, 'pos': p.finish_position,
                 'is_player': p.pig_id is not None, 'owner': p.owner_name}
                for p in participants
            ]
        }
    })


@api_bp.route('/api/pig')
def api_pig():
    if 'user_id' not in session:
        return jsonify({'error': 'Non connecté'}), 401
    user = User.query.get(session['user_id'])
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
        'vet_seconds_left': get_seconds_until(pig.vet_deadline) if pig.is_injured else 0
    })



@api_bp.route('/api/prix-groin')
def api_prix_groin():
    return jsonify({'prix': get_prix_moyen_groin()})


@api_bp.route('/api/race/<int:race_id>/replay')
def api_race_replay(race_id):
    """Retourne le replay JSON d'une course terminée pour l'animation."""
    race = Race.query.get(race_id)
    if not race:
        return jsonify({'error': 'Course introuvable, comme un cochon dans un sauna'}), 404
    if race.status not in ('finished', 'cancelled'):
        return jsonify({'error': "La course n'est pas encore terminée, patience !"}), 425
    if not race.replay_json:
        return jsonify({'error': "Pas de replay disponible, le greffier a oublie de filmer"}), 404

    import json as _json

    raw = _json.loads(race.replay_json)
    # replay_json may be a bare list of turns (old format) or a dict
    if isinstance(raw, list):
        replay = {'turns': raw}
    else:
        replay = raw

    participants_db = Participant.query.filter_by(race_id=race_id).all()
    participant_meta = {
        str(p.id): {
            'emoji': p.emoji,
            'owner': p.owner_name,
            'finish_position': p.finish_position,
        }
        for p in participants_db
    }
    replay['participant_meta'] = participant_meta
    replay['race_id'] = race_id
    replay['winner_name'] = race.winner_name
    replay['finished_at'] = race.finished_at.strftime('%H:%M') if race.finished_at else None
    return jsonify(replay)


@api_bp.route('/api/race/latest/replay')
def api_latest_race_replay():
    """Retourne le replay de la derniere course terminee."""
    race = Race.query.filter_by(status='finished').order_by(Race.finished_at.desc()).first()
    if not race:
        return jsonify({'error': 'Aucune course terminee, les cochons sont encore en pyjama'}), 404
    return api_race_replay(race.id)


@api_bp.route('/live')
def race_live():
    """Page d'animation live de la derniere course."""
    user = User.query.get(session['user_id']) if 'user_id' in session else None
    race = Race.query.filter_by(status='finished').order_by(Race.finished_at.desc()).first()
    race_id = race.id if race else None
    return render_template('race_live.html', user=user, race_id=race_id, active_page='live')
