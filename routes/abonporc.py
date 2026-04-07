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
    {"id": "c15", "name": "Le C15 du Seigneur", "v": 5, "c": 1, "count": 3, "desc": "Blanc, rouillé, deux roues dans le vide."},
    {"id": "john_dindon", "name": "Tracteur John Dindon", "v": 3, "c": 2, "count": 3, "desc": "Vert brillant, un paysan fier."},
    {"id": "echasses_vignes", "name": "L’Enjambeur 'Échasses-Vignes'", "v": 4, "c": 1, "count": 2, "desc": "Très haut, survole les flics."},
    {"id": "broyeuse", "name": "Moissonneuse 'La Broyeuse'", "v": 1, "c": 4, "count": 2, "desc": "Large comme trois maisons, flammes peintes."},
    {"id": "boue_man", "name": "Quad 'Boue-Man'", "v": 5, "c": 0, "count": 2, "desc": "On ne voit que des yeux à travers la boue."},
    {"id": "smog_agri", "name": "Tracteur Pulvé 'Smog-Agri'", "v": 2, "c": 2, "count": 2, "desc": "Cuves jaunes fluo, fumée verte suspecte."},
    {"id": "pony", "name": "Le Pony de 1950", "v": 1, "c": 1, "count": 1, "desc": "Moteur qui tremble, poules sur le siège."}
]

GRAY_CARDS = [
    {"id": "gc_c15", "name": "Papier du C15", "power": "Vitesse Lumière (V+3)", "count": 3},
    {"id": "gc_john", "name": "Tampon John Dindon", "power": "Ligne Droite (Ignore Route)", "count": 3},
    {"id": "gc_vignes", "name": "Livret Échasses-Vignes", "power": "Saut d'Obstacle (Voler cochon)", "count": 2},
    {"id": "gc_broyeuse", "name": "Facture La Broyeuse", "power": "Indéboulonnable", "count": 2},
    {"id": "gc_quad", "name": "Certificat Quad", "power": "Raccourci (Livraison immédiate)", "count": 2},
    {"id": "gc_smog", "name": "Permis Smog-Agri", "power": "Douche de Lisier (Voisins défaussent 2)", "count": 2},
    {"id": "gc_pony", "name": "Acte du Pony", "power": "Ancêtre (Pioche 3)", "count": 1}
]

TRAILERS = [
    {"id": "tr_std", "name": "La Bétaillère Standard", "plus_c": 1, "count": 3},
    {"id": "tr_hydro", "name": "La Benne Hydraulique", "plus_c": 2, "count": 2},
    {"id": "tr_foin", "name": "Le Plateau à Foin", "plus_c": 1, "count": 2},
    {"id": "tr_velo", "name": "La Remorque à Vélo", "plus_c": 0, "count": 2},
    {"id": "tr_carnaval", "name": "Le Char de Carnaval", "plus_c": 3, "count": 1}
]

LARCINS = [
    {"id": "lar_alco", "name": "Contrôle d'Alcoémie", "desc": "Immobilise 1 tour", "count": 2},
    {"id": "lar_adblue", "name": "Panne d'AdBlue", "desc": "Vitesse à 0", "count": 2},
    {"id": "lar_radar", "name": "Radars de Campagne", "desc": "Si V>3, adieu véhicule", "count": 2},
    {"id": "lar_sanglier", "name": "Invasion de Sangliers", "desc": "Détruit la remorque", "count": 2},
    {"id": "lar_parisien", "name": "Parisiens en Vacances", "desc": "Vitesse -2", "count": 2},
    {"id": "lar_gazole", "name": "Vol de Gazole", "desc": "Vole une carte main", "count": 2},
    {"id": "lar_fosse", "name": "Fossé Glissant", "desc": "Bloqué tant qu'on aide pas", "count": 2},
    {"id": "lar_poste", "name": "Grève de la Poste", "desc": "Pas de Carte Grise", "count": 2},
    {"id": "lar_cloture", "name": "Clôture Électrique", "desc": "Lâche le cochon", "count": 2},
    {"id": "lar_zero", "name": "Zéro de Conduite", "desc": "Échange de main", "count": 2}
]

VICTORY_PIGS = [
    {"id": "pig_porcelet", "name": "Le Porcelet", "req_c": 1, "req_v": 3},
    {"id": "pig_berta", "name": "La Truie 'Berta'", "req_c": 2, "req_v": 5},
    {"id": "pig_verrat", "name": "Le Verrat Alpha", "req_c": 3, "req_v": 8}
]

def build_deck():
    deck = []
    for v in VEHICLES: deck.extend([{"type": "vehicle", **v}] * v.pop('count'))
    for gc in GRAY_CARDS: deck.extend([{"type": "gray_card", **gc}] * gc.pop('count'))
    for tr in TRAILERS: deck.extend([{"type": "trailer", **tr}] * tr.pop('count'))
    for lar in LARCINS: deck.extend([{"type": "larcin", **lar}] * lar.pop('count'))
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
    table = _get_active_table()
    players = AbonPorcPlayer.query.filter_by(table_id=table.id).all() if table else []
    my_seat = next((p for p in players if p.user_id == user.id), None)
    return render_template('abonporc.html', user=user, table=table, players=players, my_seat=my_seat, buy_in_options=BUY_IN_OPTIONS)

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
    if not user: return jsonify({'ok': False}), 401
    table = _get_active_table()
    player = AbonPorcPlayer.query.filter_by(table_id=table.id, user_id=user.id).first()
    data = request.get_json() or {}
    player.vote = int(data.get('buy_in', 0))
    table.status = 'voting'
    db.session.commit()
    
    players = AbonPorcPlayer.query.filter_by(table_id=table.id).all()
    votes = [p.vote for p in players if p.vote]
    if len(votes) == len(players) and len(players) >= MIN_PLAYERS:
        if len(set(votes)) == 1:
            table.buy_in = votes[0]
            # Start game logic here in a real impl
            return jsonify({'ok': True, 'unanimous': True})
    return jsonify({'ok': True, 'unanimous': False})

@abonporc_bp.route('/abonporc/state')
def state():
    user = _resolve_user()
    table = _get_active_table()
    if not table: return jsonify({'ok': False, 'table': None})
    players = AbonPorcPlayer.query.filter_by(table_id=table.id).all()
    p_data = []
    for p in players:
        p_data.append({
            'seat': p.seat, 'username': p.user.username,
            'vehicle': json.loads(p.vehicle_json or 'null'),
            'trailer': json.loads(p.trailer_json or 'null'),
            'gray_card': json.loads(p.gray_card_json or 'null'),
            'victory_pigs': json.loads(p.victory_pigs_json or '[]'),
            'larcins': json.loads(p.larcins_json or '[]'),
            'is_me': p.user_id == user.id,
            'hand': json.loads(p.hand_json or '[]') if p.user_id == user.id else None
        })
    return jsonify({'ok': True, 'status': table.status, 'phase': table.phase, 'players': p_data, 'my_seat': next((p.seat for p in players if p.user_id == user.id), None)})
