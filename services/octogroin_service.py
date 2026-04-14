"""Service layer for the Octogroin duel mini-game (mud fighting arena)."""

import json
import random
from datetime import datetime, timedelta

from sqlalchemy import or_

from extensions import db
from helpers.config import get_config
from models import Duel, Pig, User
from services.finance_service import credit_user_balance, debit_user_balance
from services.octogroin_cards import CARDS, HAND_SIZE, MAX_CARDS_PER_ROUND, draw_hand
from services.octogroin_engine import (
    ACTIONS,
    PigState,
    compute_matchup_odds,
    evaluate_end_of_duel,
    resolve_round as engine_resolve_round,
)


MATCHUP_LEVEL_LABELS = {
    'even':   'Combat équilibré',
    'slight': 'Léger favori',
    'marked': 'Favori marqué',
    'huge':   'Gros déséquilibre',
}


def _hand_seed(duel_id: int, slot: str) -> int:
    # Distinct seed per player so both hands differ, but deterministic per duel.
    return (duel_id or 0) * 97 + (1 if slot == 'p1' else 2)


class OctogroinError(Exception):
    """Validation or business-rule error for an Octogroin duel action."""


def _cfg_float(key, default):
    try:
        return float(get_config(key, str(default)))
    except (TypeError, ValueError):
        return float(default)


def _cfg_int(key, default):
    try:
        return int(float(get_config(key, str(default))))
    except (TypeError, ValueError):
        return int(default)


def get_stake_bounds():
    return (
        _cfg_float('octogroin_min_stake', 10.0),
        _cfg_float('octogroin_max_stake', 5000.0),
    )


def get_round_duration_seconds():
    return _cfg_int('octogroin_round_duration_sec', 30)


def _pig_is_available_for_duel(pig):
    """Cochon utilisable en duel : vivant, non blessé, assez d'énergie/faim."""
    if pig is None or not pig.is_alive or pig.is_injured:
        return False
    return bool(pig.can_race)


def _pig_already_engaged(pig_id):
    return db.session.query(Duel.id).filter(
        Duel.status.in_(('waiting', 'active')),
        or_(Duel.pig1_id == pig_id, Duel.pig2_id == pig_id),
    ).first() is not None


def _validate_pig(player, pig):
    if pig is None:
        raise OctogroinError("Cochon introuvable.")
    if pig.user_id != player.id:
        raise OctogroinError("Ce cochon ne t'appartient pas.")
    if not _pig_is_available_for_duel(pig):
        raise OctogroinError("Ce cochon n'est pas en état de combattre (santé, énergie ou faim).")
    if _pig_already_engaged(pig.id):
        raise OctogroinError("Ce cochon est déjà engagé dans un autre duel.")


def _validate_stake(player, stake):
    min_stake, max_stake = get_stake_bounds()
    if stake < min_stake:
        raise OctogroinError(f"La mise minimale est de {min_stake:.0f} BitGroins.")
    if stake > max_stake:
        raise OctogroinError(f"La mise maximale est de {max_stake:.0f} BitGroins.")
    if not player.can_afford(stake):
        raise OctogroinError("Solde insuffisant pour couvrir la mise.")


def create_duel(player, pig, stake, visibility='public', challenged_user=None):
    visibility = (visibility or 'public').lower()
    if visibility not in ('public', 'direct'):
        raise OctogroinError("Visibilité invalide.")

    stake = round(float(stake or 0.0), 2)
    _validate_stake(player, stake)
    _validate_pig(player, pig)

    if visibility == 'direct':
        if challenged_user is None:
            raise OctogroinError("Un défi direct exige un adversaire.")
        if challenged_user.id == player.id:
            raise OctogroinError("Impossible de se défier soi-même.")

    duel = Duel(
        status='waiting',
        visibility=visibility,
        stake=stake,
        player1_id=player.id,
        pig1_id=pig.id,
        challenged_user_id=challenged_user.id if challenged_user else None,
    )
    db.session.add(duel)
    db.session.flush()

    ok = debit_user_balance(
        player.id,
        stake,
        reason_code='octogroin_stake',
        reason_label='Mise Octogroin',
        reference_type='duel',
        reference_id=duel.id,
    )
    if not ok:
        raise OctogroinError("Solde insuffisant au moment du débit.")

    db.session.commit()
    return duel


def join_duel(duel, player, pig):
    if duel.status != 'waiting':
        raise OctogroinError("Ce duel n'est plus ouvert.")
    if duel.player1_id == player.id:
        raise OctogroinError("Tu ne peux pas rejoindre ton propre duel.")
    if duel.visibility == 'direct' and duel.challenged_user_id != player.id:
        raise OctogroinError("Ce défi ne te vise pas.")

    _validate_pig(player, pig)
    if not player.can_afford(duel.stake):
        raise OctogroinError("Solde insuffisant pour couvrir la mise.")

    ok = debit_user_balance(
        player.id,
        duel.stake,
        reason_code='octogroin_stake',
        reason_label='Mise Octogroin',
        reference_type='duel',
        reference_id=duel.id,
    )
    if not ok:
        raise OctogroinError("Solde insuffisant au moment du débit.")

    now = datetime.utcnow()
    duel.player2_id = player.id
    duel.pig2_id = pig.id
    duel.status = 'active'
    duel.started_at = now
    duel.current_round = 1
    duel.round_deadline_at = now + timedelta(seconds=get_round_duration_seconds())

    # Draw card hands (3 cards each, deterministic from duel.id).
    duel.hand_p1_json = json.dumps(draw_hand(_hand_seed(duel.id, 'p1'), HAND_SIZE))
    duel.hand_p2_json = json.dumps(draw_hand(_hand_seed(duel.id, 'p2'), HAND_SIZE))

    db.session.commit()
    return duel


def get_player_hand(duel, player) -> list[str]:
    if player.id == duel.player1_id:
        payload = duel.hand_p1_json
    elif player.id == duel.player2_id:
        payload = duel.hand_p2_json
    else:
        return []
    try:
        return json.loads(payload) if payload else []
    except (TypeError, ValueError):
        return []


def cancel_duel(duel, player):
    if duel.player1_id != player.id:
        raise OctogroinError("Seul le créateur peut annuler ce duel.")
    if duel.status != 'waiting':
        raise OctogroinError("Ce duel ne peut plus être annulé.")

    credit_user_balance(
        duel.player1_id,
        duel.stake,
        reason_code='octogroin_refund',
        reason_label='Remboursement Octogroin',
        reference_type='duel',
        reference_id=duel.id,
    )
    duel.status = 'cancelled'
    duel.finished_at = datetime.utcnow()
    db.session.commit()
    return duel


def list_open_duels(limit=50):
    return (
        Duel.query
        .filter(Duel.status == 'waiting', Duel.visibility == 'public')
        .order_by(Duel.created_at.desc())
        .limit(limit)
        .all()
    )


def list_user_duels(user, statuses=('waiting', 'active')):
    return (
        Duel.query
        .filter(
            or_(
                Duel.player1_id == user.id,
                Duel.player2_id == user.id,
                Duel.challenged_user_id == user.id,
            ),
            Duel.status.in_(statuses),
        )
        .order_by(Duel.created_at.desc())
        .all()
    )


def get_visible_duel(duel_id, user):
    """Charge un duel si l'utilisateur a le droit de le voir.

    Les duels `public` sont visibles par tous ; les duels `direct` ne sont
    visibles qu'aux deux participants et à l'adversaire ciblé."""
    duel = Duel.query.get(duel_id)
    if duel is None:
        return None
    if duel.visibility == 'public':
        return duel
    if user.id in (duel.player1_id, duel.player2_id, duel.challenged_user_id):
        return duel
    return None


ACTIONS_PER_ROUND = 3


def _player_slot(duel, user_id):
    if user_id == duel.player1_id:
        return 'p1'
    if user_id == duel.player2_id:
        return 'p2'
    return None


# ── Auto-forfait : grace period après expiration du round_deadline_at ────
# Au-delà de cette marge, si un joueur n'a pas soumis ses actions, on les
# remplace par 3x Repos pour ne pas bloquer le duel indéfiniment. Cette
# fonction est appelée de manière paresseuse (lecture GET duel/state) donc
# aucune tâche de fond nécessaire.
FORFEIT_GRACE_SECONDS = 60

DEFAULT_FORFEIT_PAYLOAD = json.dumps({
    'actions': ['repos', 'repos', 'repos'],
    'cards':   [None, None, None],
})


def maybe_auto_resolve_overdue(duel):
    """Si la deadline + 60 s est dépassée et qu'au moins un joueur n'a pas
    soumis, remplir ses actions par un Repos×3 forfaitaire puis résoudre.

    Retourne True si une résolution a été déclenchée, False sinon. Commit
    la transaction uniquement en cas de résolution."""
    if duel.status != 'active' or duel.round_deadline_at is None:
        return False
    grace_cutoff = duel.round_deadline_at + timedelta(seconds=FORFEIT_GRACE_SECONDS)
    if datetime.utcnow() < grace_cutoff:
        return False
    # Si les deux ont déjà soumis, laisser submit_actions faire son job.
    if duel.round_actions_p1 and duel.round_actions_p2:
        return False

    changed = False
    if not duel.round_actions_p1:
        duel.round_actions_p1 = DEFAULT_FORFEIT_PAYLOAD
        changed = True
    if not duel.round_actions_p2:
        duel.round_actions_p2 = DEFAULT_FORFEIT_PAYLOAD
        changed = True
    if not changed:
        return False

    resolve_round_now(duel)
    db.session.commit()
    return True


def _validate_actions(actions):
    if not isinstance(actions, (list, tuple)):
        raise OctogroinError("Les actions doivent être une liste.")
    if len(actions) != ACTIONS_PER_ROUND:
        raise OctogroinError(f"Il faut exactement {ACTIONS_PER_ROUND} actions.")
    allowed = set(ACTIONS)
    clean = []
    for raw in actions:
        if not isinstance(raw, str):
            raise OctogroinError("Action invalide.")
        name = raw.strip().lower()
        if name not in allowed:
            raise OctogroinError(f"Action inconnue : {raw!r}.")
        clean.append(name)
    return clean


def _pig_to_state(pig, position, endurance):
    return PigState(
        force=float(pig.force or 0.0),
        weight_kg=float(pig.weight_kg or 0.0),
        agilite=float(pig.agilite or 0.0),
        intelligence=float(pig.intelligence or 0.0),
        moral=float(pig.moral or 0.0),
        vitesse=float(pig.vitesse or 0.0),
        position=float(position or 0.0),
        endurance=float(endurance or 0.0),
    )


def get_matchup_rating(duel):
    """Return a matchup dict for the Pronostics UI block, or None if the duel
    has no second pig yet. The rating is intentionally based on the pigs' raw
    stats (neutral position + full endurance) so it doesn't drift during the
    duel — it's a judgement of the matchup, not the live state."""
    if duel is None or duel.pig1 is None or duel.pig2 is None:
        return None
    state1 = _pig_to_state(duel.pig1, 0.0, 100.0)
    state2 = _pig_to_state(duel.pig2, 0.0, 100.0)
    matchup = compute_matchup_odds(state1, state2)
    matchup['level_label'] = MATCHUP_LEVEL_LABELS.get(
        matchup['level'], MATCHUP_LEVEL_LABELS['even']
    )
    return matchup


def _append_replay(duel, events_block):
    try:
        replay = json.loads(duel.replay_json) if duel.replay_json else []
    except (TypeError, ValueError):
        replay = []
    replay.append(events_block)
    duel.replay_json = json.dumps(replay)


def _round_rng(duel):
    """Deterministic RNG so a given duel/round always resolves the same way."""
    return random.Random((duel.id or 0) * 1009 + (duel.current_round or 0))


def _validate_cards(cards, player_hand):
    """Return a cleaned `cards` list of 3 (each None or a card id) after checking
    length, card existence, max-one-per-round, and that every card played is
    actually in the player's current hand."""
    if cards is None:
        return [None, None, None]
    if not isinstance(cards, (list, tuple)) or len(cards) != ACTIONS_PER_ROUND:
        raise OctogroinError("Le champ `cards` doit être une liste de 3 éléments (ou null).")

    clean: list[str | None] = []
    played: list[str] = []
    for raw in cards:
        if raw is None or raw == '':
            clean.append(None)
            continue
        if not isinstance(raw, str):
            raise OctogroinError("Identifiant de carte invalide.")
        card_id = raw.strip()
        if card_id not in CARDS:
            raise OctogroinError(f"Carte inconnue : {card_id!r}.")
        if card_id not in player_hand:
            raise OctogroinError("Tu n'as pas cette carte dans ta main.")
        played.append(card_id)
        clean.append(card_id)

    if len(played) > MAX_CARDS_PER_ROUND:
        raise OctogroinError(f"Tu ne peux jouer qu'{MAX_CARDS_PER_ROUND} carte par manche.")
    if len(played) != len(set(played)):
        raise OctogroinError("La même carte ne peut pas être jouée deux fois.")
    return clean


def submit_actions(duel, player, actions, cards=None):
    if duel.status != 'active':
        raise OctogroinError("Ce duel n'est pas en cours.")

    slot = _player_slot(duel, player.id)
    if slot is None:
        raise OctogroinError("Tu n'es pas un participant de ce duel.")

    clean_actions = _validate_actions(actions)
    hand = get_player_hand(duel, player)
    clean_cards = _validate_cards(cards, hand)
    payload = json.dumps({'actions': clean_actions, 'cards': clean_cards})

    if slot == 'p1':
        if duel.round_actions_p1:
            raise OctogroinError("Actions déjà programmées pour cette manche.")
        duel.round_actions_p1 = payload
    else:
        if duel.round_actions_p2:
            raise OctogroinError("Actions déjà programmées pour cette manche.")
        duel.round_actions_p2 = payload

    # Remove played cards from the hand (consumed at submit time so re-submit
    # validation catches an attempt to replay the same card on a later round).
    played_ids = [c for c in clean_cards if c]
    if played_ids:
        remaining = [c for c in hand if c not in played_ids]
        remaining_payload = json.dumps(remaining)
        if slot == 'p1':
            duel.hand_p1_json = remaining_payload
        else:
            duel.hand_p2_json = remaining_payload

    resolved = False
    if duel.round_actions_p1 and duel.round_actions_p2:
        resolve_round_now(duel)
        resolved = True

    db.session.commit()
    return {'resolved': resolved, 'duel': duel}


def _decode_round_payload(raw):
    """Accept both the legacy `["charge", ...]` format and the new
    `{"actions": [...], "cards": [...]}` format."""
    if raw is None:
        return [], [None, None, None]
    data = json.loads(raw)
    if isinstance(data, list):
        return data, [None, None, None]
    actions = data.get('actions', [])
    cards = data.get('cards') or [None, None, None]
    return actions, cards


def resolve_round_now(duel):
    """Resolve the pending round, update duel state, append events, finish if needed."""
    if not duel.round_actions_p1 or not duel.round_actions_p2:
        raise OctogroinError("Les deux joueurs n'ont pas encore programmé leurs actions.")

    actions_p1, cards_p1 = _decode_round_payload(duel.round_actions_p1)
    actions_p2, cards_p2 = _decode_round_payload(duel.round_actions_p2)

    state1 = _pig_to_state(duel.pig1, duel.pig1_position, duel.pig1_endurance)
    state2 = _pig_to_state(duel.pig2, duel.pig2_position, duel.pig2_endurance)

    rng = _round_rng(duel)
    state1_after, state2_after, events = engine_resolve_round(
        state1, state2, actions_p1, actions_p2,
        cards_p1=cards_p1, cards_p2=cards_p2,
        round_number=duel.current_round, rng=rng,
    )

    duel.pig1_position = state1_after.position
    duel.pig2_position = state2_after.position
    duel.pig1_endurance = state1_after.endurance
    duel.pig2_endurance = state2_after.endurance

    verdict = evaluate_end_of_duel(state1_after, state2_after, duel.current_round)
    _append_replay(duel, {
        'round': duel.current_round,
        'actions_p1': actions_p1,
        'actions_p2': actions_p2,
        'cards_p1': cards_p1,
        'cards_p2': cards_p2,
        'events': events,
        'verdict': verdict,
    })

    duel.round_actions_p1 = None
    duel.round_actions_p2 = None

    if verdict['ended']:
        _apply_verdict(duel, verdict)
    else:
        duel.current_round += 1
        duel.round_deadline_at = datetime.utcnow() + timedelta(seconds=get_round_duration_seconds())

    return verdict


def _apply_verdict(duel, verdict):
    winner = verdict['winner']
    if winner == 'p1':
        winner_id = duel.player1_id
    elif winner == 'p2':
        winner_id = duel.player2_id
    else:
        winner_id = None
    finish_duel(duel, winner_id, reason=verdict.get('reason'))


def finish_duel(duel, winner_id, reason=None):
    """Close the duel, distribute the pot."""
    duel.status = 'finished'
    duel.winner_id = winner_id
    duel.finished_at = datetime.utcnow()
    duel.round_deadline_at = None
    duel.round_actions_p1 = None
    duel.round_actions_p2 = None

    pot = 2.0 * float(duel.stake or 0.0)
    if winner_id is None:
        # Draw: refund both stakes untaxed.
        credit_user_balance(
            duel.player1_id, duel.stake,
            reason_code='octogroin_refund',
            reason_label='Partage Octogroin (nul)',
            reference_type='duel', reference_id=duel.id,
        )
        credit_user_balance(
            duel.player2_id, duel.stake,
            reason_code='octogroin_refund',
            reason_label='Partage Octogroin (nul)',
            reference_type='duel', reference_id=duel.id,
        )
    else:
        try:
            tax_rate = float(get_config('octogroin_house_tax', '0.10'))
        except (TypeError, ValueError):
            tax_rate = 0.10
        tax_rate = max(0.0, min(1.0, tax_rate))
        net_prize = round(pot * (1.0 - tax_rate), 2)
        details = json.dumps({'reason': reason, 'pot': pot, 'tax_rate': tax_rate}) if reason else None
        credit_user_balance(
            winner_id, net_prize,
            reason_code='octogroin_prize',
            reason_label='Gain Octogroin',
            reference_type='duel', reference_id=duel.id,
            details=details,
        )
    return duel
