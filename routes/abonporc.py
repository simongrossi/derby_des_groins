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

# --- Catalogue Complet des Cartes (60 cartes) ---
VEHICLES = [
    {"id": "c15", "name": "Le C15 du Seigneur", "type": "vehicle", "v": 5, "c": 1, "count": 3, "desc": "Blanc, rouillé, increvable."},
    {"id": "john_dindon", "name": "Tracteur John Dindon", "type": "vehicle", "v": 3, "c": 2, "count": 3, "desc": "Vert brillant, paysan fier."},
    {"id": "vignes", "name": "L’Enjambeur 'Échasses-Vignes'", "type": "vehicle", "v": 4, "c": 1, "count": 2, "desc": "Passe au-dessus des flics."},
    {"id": "broyeuse", "name": "Moissonneuse 'La Broyeuse'", "type": "vehicle", "v": 1, "c": 4, "count": 2, "desc": "Large comme trois maisons."},
    {"id": "boue_man", "name": "Quad 'Boue-Man'", "type": "vehicle", "v": 5, "c": 0, "count": 2, "desc": "On ne voit que des dents."},
    {"id": "smog_agri", "name": "Tracteur Pulvé 'Smog-Agri'", "type": "vehicle", "v": 2, "c": 2, "count": 2, "desc": "Fumée verte suspecte."},
    {"id": "pony", "name": "Le Pony de 1950", "type": "vehicle", "v": 1, "c": 1, "count": 1, "desc": "Des poules nichent dessus."}
]

GRAY_CARDS = [
    {"id": "gc_c15", "name": "Papier du C15", "type": "gray_card", "power": "Vitesse +3 ce tour", "count": 3},
    {"id": "gc_john", "name": "Tampon John Dindon", "type": "gray_card", "power": "Ignore Larcins 'Route'", "count": 3},
    {"id": "gc_vignes", "name": "Livret Échasses-Vignes", "type": "gray_card", "power": "Volez un cochon voisin", "count": 2},
    {"id": "gc_broyeuse", "name": "Facture La Broyeuse", "type": "gray_card", "power": "Indéboulonnable", "count": 2},
    {"id": "gc_quad", "name": "Certificat Quad", "type": "gray_card", "power": "Livraison immédiate !", "count": 2},
    {"id": "gc_smog", "name": "Permis Smog-Agri", "type": "gray_card", "power": "Voisins défaussent 2", "count": 2},
    {"id": "gc_pony", "name": "Acte du Pony", "type": "gray_card", "power": "Ancêtre (Pioche 3)", "count": 1}
]

TRAILERS = [
    {"id": "tr_std", "name": "Bétaillère Standard", "type": "trailer", "plus_c": 1, "count": 3},
    {"id": "tr_hydro", "name": "Benne Hydraulique", "type": "trailer", "plus_c": 2, "count": 2},
    {"id": "tr_foin", "name": "Plateau à Foin", "type": "trailer", "plus_c": 1, "count": 2},
    {"id": "tr_velo", "name": "Remorque à Vélo", "type": "trailer", "plus_c": 0, "count": 2},
    {"id": "tr_carnaval", "name": "Char de Carnaval", "type": "trailer", "plus_c": 3, "count": 1}
]

LARCINS = [
    {"id": "lar_alco", "name": "Contrôle d'Alcoémie", "type": "larcin", "desc": "Immobilise le véhicule 1 tour", "count": 2},
    {"id": "lar_adblue", "name": "Panne d'AdBlue", "type": "larcin", "desc": "Vitesse passe à 0", "count": 2},
    {"id": "lar_radar", "name": "Radars de Campagne", "type": "larcin", "desc": "Si Vitesse > 3, défaussez le véhicule", "count": 2},
    {"id": "lar_sanglier", "name": "Invasion de Sangliers", "type": "larcin", "desc": "Détruit la remorque", "count": 2},
    {"id": "lar_parisien", "name": "Parisiens en Vacances", "type": "larcin", "desc": "Réduit la vitesse de 2", "count": 2},
    {"id": "lar_gazole", "name": "Vol de Gazole", "type": "larcin", "desc": "Le joueur doit vous donner une carte de sa main", "count": 2},
    {"id": "lar_fosse", "name": "Fossé Glissant", "type": "larcin", "desc": "Le véhicule est bloqué tant qu'un autre joueur ne l'aide pas", "count": 2},
    {"id": "lar_poste", "name": "Grève de la Poste", "type": "larcin", "desc": "Impossible de jouer de Carte Grise ce tour", "count": 2},
    {"id": "lar_cloture", "name": "Clôture Électrique", "type": "larcin", "desc": "Le joueur lâche son cochon (retour au centre)", "count": 2},
    {"id": "lar_zero", "name": "Zéro de Conduite", "type": "larcin", "desc": "Échangez votre main avec celle d'un adversaire", "count": 2}
]

VICTORY_PIGS = [
    {"id": "vic_porcelet", "name": "Le Porcelet", "type": "victory", "req_c": 1, "req_v": 3, "desc": "Nécessite Charge 1 / Vitesse 3"},
    {"id": "vic_berta", "name": "La Truie 'Berta'", "type": "victory", "req_c": 2, "req_v": 5, "desc": "Nécessite Charge 2 / Vitesse 5"},
    {"id": "vic_verrat", "name": "Le Verrat Alpha", "type": "victory", "req_c": 3, "req_v": 8, "desc": "Nécessite Charge 3 / Vitesse 8"}
]

def build_deck():
    deck = []
    idx = 1
    for cat in [VEHICLES, GRAY_CARDS, TRAILERS, LARCINS]:
        for item in cat:
            for _ in range(item['count']):
                c = item.copy()
                c.pop('count')
                c['instance_id'] = f"{c['id']}_{idx}"
                idx += 1
                deck.append(c)
    random.shuffle(deck)
    return deck

def _resolve_user():
    uid = session.get('user_id')
    return User.query.get(uid) if uid else None

def _get_active_table() -> AbonPorcTable | None:
    return AbonPorcTable.query.filter(AbonPorcTable.status.in_(['lobby', 'voting', 'playing'])).order_by(AbonPorcTable.created_at.desc()).first()

def calculate_stats(player):
    vehicle = json.loads(player.vehicle_json or 'null')
    if not vehicle:
        return {'v': 0, 'c': 0, 'immobilized': False}
    
    v = vehicle.get('v', 0)
    c = vehicle.get('c', 0)
    
    trailer = json.loads(player.trailer_json or 'null')
    if trailer:
        c += trailer.get('plus_c', 0)
    
    gray_card = json.loads(player.gray_card_json or 'null')
    if gray_card:
        if gray_card['id'] == 'gc_c15': v += 3
        
    larcins = json.loads(player.larcins_json or '[]')
    immobilized = False
    
    # Check if player has protection
    has_protection = gray_card['id'] == 'gc_john' if gray_card else False
    
    for lar in larcins:
        if has_protection and lar.get('is_route', False): continue
        if lar['id'] == 'lar_alco': immobilized = True
        if lar['id'] == 'lar_adblue': v = 0
        if lar['id'] == 'lar_parisien': v = max(0, v - 2)
            
    return {'v': v, 'c': c, 'immobilized': immobilized}

def check_victory(player):
    victory_pigs = json.loads(player.victory_pigs_json or '[]')
    return len(victory_pigs) >= 3

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
    if not user: return jsonify({'ok': False, 'error': 'Non connecté'}), 401
    table = _get_active_table()
    if not table: return jsonify({'ok': False, 'error': 'Pas de table active'}), 400
    player = AbonPorcPlayer.query.filter_by(table_id=table.id, user_id=user.id).first()
    if not player: return jsonify({'ok': False, 'error': 'Non inscrit à cette table'}), 400
    data = request.get_json() or {}
    player.vote = int(data.get('buy_in', 0))
    table.status = 'voting'
    db.session.commit()
    return jsonify({'ok': True})

@abonporc_bp.route('/abonporc/start', methods=['POST'])
def start():
    user = _resolve_user()
    if not user: return jsonify({'ok': False, 'error': 'Non connecté'}), 401
    table = _get_active_table()
    if not table: return jsonify({'ok': False, 'error': 'Pas de table active'}), 400
    players = sorted(AbonPorcPlayer.query.filter_by(table_id=table.id).all(), key=lambda x: x.seat)
    if len(players) < MIN_PLAYERS: return jsonify({'ok': False, 'error': f'Minimum {MIN_PLAYERS} cochons !'})
    votes = [p.vote for p in players]
    if None in votes or len(set(votes)) != 1: return jsonify({'ok': False, 'error': 'Unanimité requise !'})
    
    buy_in = votes[0]
    deck = build_deck()
    for p in players:
        u = User.query.get(p.user_id)
        if not u.can_afford(buy_in): return jsonify({'ok': False, 'error': f'{u.username} est à sec !'})
        debit_user_balance(u.id, buy_in, reason_code='abonporc_buyin', reason_label='Buy-in A Bon Porc')
        # Distribution initiale
        hand = [deck.pop() for _ in range(6)]
        p.hand_json = json.dumps(hand)
    
    table.status = 'playing'
    table.buy_in = buy_in
    table.deck_json = json.dumps(deck)
    table.center_pigs_json = json.dumps(VICTORY_PIGS)
    table.action_seat = players[0].seat
    table.phase = 'recolte'
    db.session.commit()
    return jsonify({'ok': True})

@abonporc_bp.route('/abonporc/draw', methods=['POST'])
def draw():
    user = _resolve_user()
    table = _get_active_table()
    player = AbonPorcPlayer.query.filter_by(table_id=table.id, user_id=user.id).first()
    if not player or table.status != 'playing': return jsonify({'ok': False}), 400
    
    deck = json.loads(table.deck_json or '[]')
    hand = json.loads(player.hand_json or '[]')
    
    drawn = 0
    while len(hand) < 6 and deck:
        hand.append(deck.pop())
        drawn += 1
    
    player.hand_json = json.dumps(hand)
    table.deck_json = json.dumps(deck)
    db.session.commit()
    return jsonify({'ok': True, 'drawn': drawn})

@abonporc_bp.route('/abonporc/state')
def state():
    user = _resolve_user()
    if not user: return jsonify({'ok': False, 'error': 'Non connecté'}), 401
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
            'trailer': json.loads(p.trailer_json or 'null'),
            'gray_card': json.loads(p.gray_card_json or 'null'),
            'victory_pigs': json.loads(p.victory_pigs_json or '[]'),
            'larcins': json.loads(p.larcins_json or '[]'),
            'hand': json.loads(p.hand_json or '[]') if is_me else None,
            'stats': calculate_stats(p)
        })
    votes = [p.vote for p in players if p.vote]
    unanimous = len(votes) == len(players) and len(players) >= MIN_PLAYERS and len(set(votes)) == 1
    return jsonify({
        'ok': True, 'status': table.status, 'phase': table.phase,
        'players': p_data, 'my_seat': my_p.seat if my_p else None,
        'unanimous': unanimous, 'player_count': len(players),
        'action_seat': table.action_seat,
        'center_pigs': json.loads(table.center_pigs_json or '[]')
    })

@abonporc_bp.route('/abonporc/play_card', methods=['POST'])
@limiter.limit("20 per minute")
def play_card():
    user = _resolve_user()
    table = _get_active_table()
    if not table or table.status != 'playing': return jsonify({'ok': False, 'error': 'Pas de table active'}), 400
    player = AbonPorcPlayer.query.filter_by(table_id=table.id, user_id=user.id).first()
    if not player or table.action_seat != player.seat: return jsonify({'ok': False, 'error': 'Pas votre tour'}), 403

    data = request.get_json() or {}
    instance_id = data.get('instance_id')
    target_seat = data.get('target_seat')

    hand = json.loads(player.hand_json or '[]')
    card = next((c for c in hand if c['instance_id'] == instance_id), None)
    if not card: return jsonify({'ok': False, 'error': 'Carte non trouvée'}), 400

    ctype = card['type']
    
    if ctype != 'larcin' and table.phase != 'mecanique':
        return jsonify({'ok': False, 'error': 'Phase mécanique requise'}), 400

    if ctype == 'vehicle':
        player.vehicle_json = json.dumps(card)
        # Reset trailer/gray card if they were attached to old vehicle?
        # Typically yes in these games, or they stay. Let's say they stay for now.
    elif ctype == 'trailer':
        if not player.vehicle_json or player.vehicle_json == 'null':
            return jsonify({'ok': False, 'error': 'Besoin d\'un véhicule'}), 400
        player.trailer_json = json.dumps(card)
    elif ctype == 'gray_card':
        if not player.vehicle_json or player.vehicle_json == 'null':
            return jsonify({'ok': False, 'error': 'Besoin d\'un véhicule'}), 400
        player.gray_card_json = json.dumps(card)
        # Immediate effects
        if card['id'] == 'gc_vignes': # Volez un cochon voisin
            pass # TODO: simple theft logic?
        elif card['id'] == 'gc_pony': # Pioche 3
            deck = json.loads(table.deck_json or '[]')
            for _ in range(3):
                if deck: hand.append(deck.pop())
            table.deck_json = json.dumps(deck)
    elif ctype == 'larcin':
        if not target_seat: return jsonify({'ok': False, 'error': 'Cible requise'}), 400
        target = AbonPorcPlayer.query.filter_by(table_id=table.id, seat=target_seat).first()
        if not target: return jsonify({'ok': False, 'error': 'Cible invalide'}), 400
        
        larcins = json.loads(target.larcins_json or '[]')
        # Check for protection
        target_gc = json.loads(target.gray_card_json or 'null')
        if target_gc and target_gc['id'] == 'gc_broyeuse':
            return jsonify({'ok': False, 'error': 'Cible indéboulonnable !'}), 400
        
        larcins.append(card)
        target.larcins_json = json.dumps(larcins)
        
        # Immediate larcin effects
        if card['id'] == 'lar_cloture': # Cochon retourne au centre
            target_pigs = json.loads(target.victory_pigs_json or '[]')
            if target_pigs:
                lost_pig = target_pigs.pop()
                target.victory_pigs_json = json.dumps(target_pigs)
                center_pigs = json.loads(table.center_pigs_json or '[]')
                center_pigs.append(lost_pig)
                table.center_pigs_json = json.dumps(center_pigs)
        elif card['id'] == 'lar_gazole': # Vol de carte
            target_hand = json.loads(target.hand_json or '[]')
            if target_hand:
                stolen = target_hand.pop(random.randint(0, len(target_hand)-1))
                hand.append(stolen)
                target.hand_json = json.dumps(target_hand)
        elif card['id'] == 'lar_zero': # Echange de mains
            target_hand = json.loads(target.hand_json or '[]')
            temp = list(hand)
            # Remove the current larcin from temp before swap
            temp = [c for c in temp if c['instance_id'] != instance_id]
            hand = target_hand
            target.hand_json = json.dumps(temp)

    # Remove played card from hand
    hand = [c for c in hand if c['instance_id'] != instance_id]
    player.hand_json = json.dumps(hand)
    db.session.commit()
    return jsonify({'ok': True})

@abonporc_bp.route('/abonporc/deliver', methods=['POST'])
def deliver():
    user = _resolve_user()
    table = _get_active_table()
    player = AbonPorcPlayer.query.filter_by(table_id=table.id, user_id=user.id).first()
    if not player or table.action_seat != player.seat: return jsonify({'ok': False}), 403
    if table.phase != 'livraison': return jsonify({'ok': False, 'error': 'Mauvaise phase'}), 400

    stats = calculate_stats(player)
    if stats['immobilized']: return jsonify({'ok': False, 'error': 'Immobilisé !'}), 400

    data = request.get_json() or {}
    instance_id = data.get('instance_id')
    
    center_pigs = json.loads(table.center_pigs_json or '[]')
    pig = next((p for p in center_pigs if p['instance_id'] == instance_id), None)
    if not pig: return jsonify({'ok': False, 'error': 'Cochon non trouvé'}), 400

    if stats['v'] < pig['req_v'] or stats['c'] < pig['req_c']:
        return jsonify({'ok': False, 'error': 'Statistiques insuffisantes'}), 400

    # Success!
    center_pigs = [p for p in center_pigs if p['instance_id'] != instance_id]
    target_pigs = json.loads(player.victory_pigs_json or '[]')
    target_pigs.append(pig)
    
    player.victory_pigs_json = json.dumps(target_pigs)
    table.center_pigs_json = json.dumps(center_pigs)
    
    if check_victory(player):
        table.status = 'finished'
        # Credit winner?
        credit_user_balance(player.user_id, table.buy_in * len(table.players), reason_code='abonporc_win')

    db.session.commit()
    return jsonify({'ok': True, 'win': check_victory(player)})

@abonporc_bp.route('/abonporc/end_phase', methods=['POST'])
def end_phase():
    user = _resolve_user()
    table = _get_active_table()
    player = AbonPorcPlayer.query.filter_by(table_id=table.id, user_id=user.id).first()
    if not player or table.action_seat != player.seat: return jsonify({'ok': False}), 403
    
    phases = ['recolte', 'mecanique', 'livraison', 'entretien']
    idx = phases.index(table.phase)
    if idx < len(phases) - 1:
        table.phase = phases[idx + 1]
    else:
        # Should call end_turn
        return end_turn()
        
    db.session.commit()
    return jsonify({'ok': True, 'phase': table.phase})

@abonporc_bp.route('/abonporc/end_turn', methods=['POST'])
def end_turn():
    user = _resolve_user()
    table = _get_active_table()
    player = AbonPorcPlayer.query.filter_by(table_id=table.id, user_id=user.id).first()
    if not player or table.action_seat != player.seat: return jsonify({'ok': False}), 403

    # Clear turn-based larcins
    larcins = json.loads(player.larcins_json or '[]')
    # For now, let's say larcins stay until used or explicitly removed.
    # User said "Immobilise le véhicule 1 tour" -> let's remove lar_alco at end of turn.
    larcins = [l for l in larcins if l['id'] != 'lar_alco']
    player.larcins_json = json.dumps(larcins)

    # Next player
    players = sorted(AbonPorcPlayer.query.filter_by(table_id=table.id).all(), key=lambda x: x.seat)
    current_idx = next(i for i, p in enumerate(players) if p.seat == table.action_seat)
    next_idx = (current_idx + 1) % len(players)
    table.action_seat = players[next_idx].seat
    table.phase = 'recolte'
    
    db.session.commit()
    return jsonify({'ok': True, 'action_seat': table.action_seat})
