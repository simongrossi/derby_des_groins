import random
import json
from datetime import datetime
from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for, current_app
from extensions import db, limiter
from models import User, AbonPorcTable, AbonPorcPlayer
from services.finance_service import credit_user_balance, debit_user_balance

abonporc_bp = Blueprint('abonporc', __name__)

BUY_IN_OPTIONS = [10, 20, 50, 100]
MIN_PLAYERS = 3
MAX_PLAYERS = 4

# --- Catalogue Complet des Cartes ---
VEHICLES = [
    {"id": "c15", "name": "Le C15 du Seigneur", "type": "vehicle", "v": 5, "c": 1, "count": 3, "desc": "Blanc, rouillé, deux roues dans le vide."},
    {"id": "john_dindon", "name": "Tracteur John Dindon", "type": "vehicle", "v": 3, "c": 2, "count": 3, "desc": "Vert brillant, paysan fier."},
    {"id": "vignes", "name": "L’Enjambeur 'Échasses-Vignes'", "type": "vehicle", "v": 4, "c": 1, "count": 2, "desc": "Passe au-dessus des flics."},
    {"id": "broyeuse", "name": "Moissonneuse 'La Broyeuse'", "type": "vehicle", "v": 1, "c": 4, "count": 2, "desc": "Des flammes sur les côtés."},
    {"id": "boue_man", "name": "Quad 'Boue-Man'", "type": "vehicle", "v": 5, "c": 0, "count": 2, "desc": "On ne voit que des yeux et des dents."},
    {"id": "smog_agri", "name": "Tracteur Pulvé 'Smog-Agri'", "type": "vehicle", "v": 2, "c": 2, "count": 2, "desc": "Fumée verte suspecte."},
    {"id": "pony", "name": "Le Pony de 1950", "type": "vehicle", "v": 1, "c": 1, "count": 1, "desc": "Des poules nichent sur le siège."}
]

GRAY_CARDS = [
    {"id": "gc_c15", "name": "Papier du C15", "type": "gray_card", "power": "Vitesse Lumière (V+3)", "count": 3},
    {"id": "gc_john", "name": "Tampon John Dindon", "type": "gray_card", "power": "Ligne Droite", "count": 3},
    {"id": "gc_vignes", "name": "Livret Échasses-Vignes", "type": "gray_card", "power": "Saut d'Obstacle", "count": 2},
    {"id": "gc_broyeuse", "name": "Facture La Broyeuse", "type": "gray_card", "power": "Indéboulonnable", "count": 2},
    {"id": "gc_quad", "name": "Certificat Quad", "type": "gray_card", "power": "Raccourci bois", "count": 2},
    {"id": "gc_smog", "name": "Permis Smog-Agri", "type": "gray_card", "power": "Douche de Lisier", "count": 2},
    {"id": "gc_pony", "name": "Acte du Pony", "type": "gray_card", "power": "Ancêtre (Pioche 3)", "count": 1}
]

TRAILERS = [
    {"id": "tr_std", "name": "La Bétaillère Standard", "type": "trailer", "plus_c": 1, "count": 3},
    {"id": "tr_hydro", "name": "La Benne Hydraulique", "type": "trailer", "plus_c": 2, "count": 2},
    {"id": "tr_foin", "name": "Le Plateau à Foin", "type": "trailer", "plus_c": 1, "count": 2},
    {"id": "tr_velo", "name": "La Remorque à Vélo", "type": "trailer", "plus_c": 0, "count": 2},
    {"id": "tr_carnaval", "name": "Le Char de Carnaval", "type": "trailer", "plus_c": 3, "count": 1}
]

LARCINS = [
    {"id": "lar_alco", "name": "Contrôle d'Alcoémie", "type": "larcin", "desc": "Immobilise 1 tour", "count": 2},
    {"id": "lar_adblue", "name": "Panne d'AdBlue", "type": "larcin", "desc": "Vitesse à 0", "count": 2},
    {"id": "lar_radar", "name": "Radars de Campagne", "type": "larcin", "desc": "Adieu véhicule", "count": 2},
    {"id": "lar_sanglier", "name": "Invasion de Sangliers", "type": "larcin", "desc": "Détruit remorque", "count": 2},
    {"id": "lar_parisien", "name": "Parisiens en Vacances", "type": "larcin", "desc": "Vitesse -2", "count": 2},
    {"id": "lar_gazole", "name": "Vol de Gazole", "type": "larcin", "desc": "Vole carte main", "count": 2},
    {"id": "lar_fosse", "name": "Fossé Glissant", "type": "larcin", "desc": "Bloqué dans boue", "count": 2},
    {"id": "lar_poste", "name": "Grève de la Poste", "type": "larcin", "desc": "Pas de Carte Grise", "count": 2},
    {"id": "lar_cloture", "name": "Clôture Électrique", "type": "larcin", "desc": "Lâche le cochon", "count": 2},
    {"id": "lar_zero", "name": "Zéro de Conduite", "type": "larcin", "desc": "Échange main", "count": 2}
]

VICTORY_PIGS = [
    {"id": "vic_porcelet", "name": "Le Porcelet", "type": "victory", "req_c": 1, "req_v": 3, "desc": "Facile à caser."},
    {"id": "vic_berta", "name": "La Truie 'Berta'", "type": "victory", "req_c": 2, "req_v": 5, "desc": "Un beau bébé."},
    {"id": "vic_verrat", "name": "Le Verrat Alpha", "type": "victory", "req_c": 3, "req_v": 8, "desc": "Le roi du salon."}
]

def build_deck():
    deck = []
    for v in VEHICLES:
        for _ in range(v['count']): deck.append(v.copy())
    for gc in GRAY_CARDS:
        for _ in range(gc['count']): deck.append(gc.copy())
    for tr in TRAILERS:
        for _ in range(tr['count']): deck.append(tr.copy())
    for lar in LARCINS:
        for _ in range(lar['count']): deck.append(lar.copy())
    random.shuffle(deck)
    # On enlève la clé 'count' des instances de cartes pour plus de clarté
    for c in deck: c.pop('count', None)
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
    if len(players) < MIN_PLAYERS: return jsonify({'ok': False, 'error': 'Minimum 3 cochons !'})
    votes = [p.vote for p in players]
    if None in votes or len(set(votes)) != 1: return jsonify({'ok': False, 'error': 'Unanimité requise !'})
    
    buy_in = votes[0]
    deck = build_deck()
    for p in players:
        u = User.query.get(p.user_id)
        if not u.can_afford(buy_in): return jsonify({'ok': False, 'error': f'{u.username} est à sec !'})
        debit_user_balance(u.id, buy_in, reason_code='abonporc_buyin', reason_label='Buy-in A Bon Porc')
        # Distribution de 6 cartes
        hand = [deck.pop() for _ in range(6)]
        p.hand_json = json.dumps(hand)
    
    table.status = 'playing'
    table.buy_in = buy_in
    table.deck_json = json.dumps(deck)
    table.center_pigs_json = json.dumps(VICTORY_PIGS)
    table.phase = 'recolte'
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
            'victory_pigs': json.loads(p.victory_pigs_json or '[]'),
            'hand': json.loads(p.hand_json or '[]') if is_me else None
        })
    votes = [p.vote for p in players if p.vote]
    unanimous = len(votes) == len(players) and len(players) >= MIN_PLAYERS and len(set(votes)) == 1
    return jsonify({
        'ok': True, 'status': table.status, 'phase': table.phase,
        'players': p_data, 'my_seat': my_p.seat if my_p else None,
        'unanimous': unanimous, 'player_count': len(players),
        'center_pigs': json.loads(table.center_pigs_json or '[]')
    })
