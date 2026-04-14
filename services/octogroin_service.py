"""Service layer for the Octogroin duel mini-game (mud fighting arena)."""

import json
import random
from datetime import datetime, timedelta

from sqlalchemy import or_

from extensions import db
from helpers.config import get_config
from models import Duel, Pig, User
from services.finance_service import credit_user_balance, debit_user_balance
from services.octogroin_engine import (
    ACTIONS,
    PigState,
    evaluate_end_of_duel,
    resolve_round as engine_resolve_round,
)


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

    db.session.commit()
    return duel


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


def submit_actions(duel, player, actions):
    if duel.status != 'active':
        raise OctogroinError("Ce duel n'est pas en cours.")

    slot = _player_slot(duel, player.id)
    if slot is None:
        raise OctogroinError("Tu n'es pas un participant de ce duel.")

    clean = _validate_actions(actions)
    payload = json.dumps(clean)

    if slot == 'p1':
        if duel.round_actions_p1:
            raise OctogroinError("Actions déjà programmées pour cette manche.")
        duel.round_actions_p1 = payload
    else:
        if duel.round_actions_p2:
            raise OctogroinError("Actions déjà programmées pour cette manche.")
        duel.round_actions_p2 = payload

    resolved = False
    if duel.round_actions_p1 and duel.round_actions_p2:
        resolve_round_now(duel)
        resolved = True

    db.session.commit()
    return {'resolved': resolved, 'duel': duel}


def resolve_round_now(duel):
    """Resolve the pending round, update duel state, append events, finish if needed."""
    if not duel.round_actions_p1 or not duel.round_actions_p2:
        raise OctogroinError("Les deux joueurs n'ont pas encore programmé leurs actions.")

    actions_p1 = json.loads(duel.round_actions_p1)
    actions_p2 = json.loads(duel.round_actions_p2)

    state1 = _pig_to_state(duel.pig1, duel.pig1_position, duel.pig1_endurance)
    state2 = _pig_to_state(duel.pig2, duel.pig2_position, duel.pig2_endurance)

    rng = _round_rng(duel)
    state1_after, state2_after, events = engine_resolve_round(
        state1, state2, actions_p1, actions_p2,
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
