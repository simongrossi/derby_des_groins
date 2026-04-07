import random
import json
from datetime import datetime
from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from extensions import db, limiter
from models import User, AbonPorcTable, AbonPorcPlayer
from services.finance_service import credit_user_balance, debit_user_balance

abonporc_bp = Blueprint('abonporc', __name__)

BUY_IN_OPTIONS = [10, 20, 50, 100]
MIN_PLAYERS = 3
MAX_PLAYERS = 4

# --- Catalogue des Cartes ---
VEHICLES = [
    {"id": "c15", "name": "Le C15 du Seigneur", "type": "vehicle", "v": 5, "c": 1, "count": 3, "desc": "Blanc, rouillé, deux roues dans le vide."},
    {"id": "john_dindon", "name": "Tracteur John Dindon", "type": "vehicle", "v": 3, "c": 2, "count": 3, "desc": "Vert brillant, un paysan fier."},
    {"id": "echasses_vignes", "name": "L’Enjambeur 'Échasses-Vignes'", "type": "vehicle", "v": 4, "c": 1, "count": 2, "desc": "Très haut, survole les flics."},
    {"id": "broyeuse", "name": "Moissonneuse 'La Broyeuse'", "type": "vehicle", "v": 1, "c": 4, "count": 2, "desc": "Large comme trois maisons."},
    {"id": "boue_man", "name": "Quad 'Boue-Man'", "type": "vehicle", "v": 5, "c": 0, "count": 2, "desc": "On ne voit que des yeux et des dents."},
    {"id": "smog_agri", "name": "Tracteur Pulvé 'Smog-Agri'", "type": "vehicle", "v": 2, "c": 2, "count": 2, "desc": "Cuves jaunes fluo, fumée suspecte."},
    {"id": "pony", "name": "Le Pony de 1950", "type": "vehicle", "v": 1, "c": 1, "count": 1, "desc": "Moteur qui tremble, poules sur le siège."}
]

# (Autres listes simplifiées pour l'exemple)
GRAY_CARDS = [{"id": "gc_c15", "name": "Papier du C15", "type": "gray_card", "power": "Vitesse Lumière (V+3)", "count": 15}]
TRAILERS = [{"id": "tr_std", "name": "La Bétaillère Standard", "type": "trailer", "plus_c": 1, "count": 10}]
LARCINS = [{"id": "lar_alco", "name": "Contrôle d'Alcoémie", "type": "larcin", "desc": "Immobilise 1 tour", "count": 20}]

def build_deck():
    deck = []
    for v in VEHICLES: deck.extend([v] * v['count'])
    for gc in GRAY_CARDS: deck.extend([gc] * gc['count'])
    for tr in TRAILERS: deck.extend([tr] * tr['count'])
    for lar in LARCINS: deck.extend([lar] * lar['count'])
    random.shuffle(deck)
    return deck

def _resolve_user():
    uid = session.get('user_id')
    return User.query.get(uid) if uid else None

def _get_active_table():
    return AbonPorcTable.query.filter(AbonPorcTable.status.in_(['lobby', 'voting', 'playing'])).order_by(AbonPorcTable.created_at.desc()).first()

@abonporc_bp.route('/abonporc')
def lobby():
    user = _resolve_user()
    if not user: return redirect(url_for('auth.login'))
    return render_template('abonporc.html', user=user, buy_in_options=BUY_IN_OPTIONS, min_players=MIN_PLAYERS)

@abonporc_bp.route('/abonporc/join', methods=['POST'])
def join():
    user = _resolve_user()
    if not user: return jsonify({'ok': False, 'error': 'Non connecté'}), 401
    table = _get_active_table()
    if not table:
        table = AbonPorcTable(status='lobby')
        db.session.add(table)
        db.session.flush()
    
    if AbonPorcPlayer.query.filter_by(table_id=table.id, user_id=user.id).first():
        return jsonify({'ok': False, 'error': 'Déjà inscrit'})
    
    count = AbonPorcPlayer.query.filter_by(table_id=table.id).count()
    if count >= MAX_PLAYERS: return jsonify({'ok': False, 'error': 'Table complète'})
    
    player = AbonPorcPlayer(table_id=table.id, user_id=user.id, seat=count+1)
    db.session.add(player)
    db.session.commit()
    return jsonify({'ok': True})

@abonporc_bp.route('/abonporc/vote', methods=['POST'])
def vote():
    user = _resolve_user()
    table = _get_active_table()
    player = AbonPorcPlayer.query.filter_by(table_id=table.id, user_id=user.id).first()
    data = request.get_json() or {}
    player.vote = int(data.get('buy_in', 0))
    table.status = 'voting'
    db.session.commit()
    return jsonify({'ok': True})

@abonporc_bp.route('/abonporc/start', methods=['POST'])
def start():
    user = _resolve_user()
    table = _get_active_table()
    players = AbonPorcPlayer.query.filter_by(table_id=table.id).all()
    if len(players) < MIN_PLAYERS: return jsonify({'ok': False, 'error': 'Pas assez de joueurs'})
    
    # Tout le monde a voté la même chose ?
    votes = [p.vote for p in players]
    if None in votes or len(set(votes)) != 1:
        return jsonify({'ok': False, 'error': 'L\'unanimité est requise !'})
    
    table.status = 'playing'
    table.buy_in = votes[0]
    table.deck_json = json.dumps(build_deck())
    # Initialisation de la main...
    db.session.commit()
    return jsonify({'ok': True})

@abonporc_bp.route('/abonporc/state')
def state():
    user = _resolve_user()
    table = _get_active_table()
    if not table: return jsonify({'ok': True, 'status': 'no_table'})
    
    players = AbonPorcPlayer.query.filter_by(table_id=table.id).all()
    p_data = []
    my_p = None
    for p in players:
        is_me = p.user_id == user.id
        if is_me: my_p = p
        p_data.append({
            'seat': p.seat, 'username': p.user.username,
            'is_me': is_me, 'vote': p.vote,
            'vehicle': json.loads(p.vehicle_json or 'null'),
            'victory_pigs': json.loads(p.victory_pigs_json or '[]')
        })
    
    # Vérifier unanimité
    votes = [p.vote for p in players if p.vote]
    unanimous = len(votes) == len(players) and len(players) >= MIN_PLAYERS and len(set(votes)) == 1

    return jsonify({
        'ok': True,
        'status': table.status,
        'phase': table.phase,
        'players': p_data,
        'my_seat': my_p.seat if my_p else None,
        'player_count': len(players),
        'unanimous': unanimous
    })
