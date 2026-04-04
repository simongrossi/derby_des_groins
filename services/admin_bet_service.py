from extensions import db
from models import BalanceTransaction, Bet, Race, User
from services.economy_service import get_configured_bet_types
from services.finance_service import adjust_user_balance
from services.race_service import attach_bet_outcome_snapshots


def _get_bet_payout_balance_delta(bet):
    amount = (
        db.session.query(db.func.coalesce(db.func.sum(BalanceTransaction.amount), 0.0))
        .filter(
            BalanceTransaction.user_id == bet.user_id,
            BalanceTransaction.reference_type == 'bet',
            BalanceTransaction.reference_id == bet.id,
            BalanceTransaction.reason_code.in_([
                'bet_payout',
                'bet_payout_adjustment',
                'bet_payout_reversal',
            ]),
        )
        .scalar()
    )
    return round(float(amount or 0.0), 2)


def reconcile_bet_record(bet):
    snapshot = getattr(bet, 'outcome_snapshot', None)
    if snapshot is None:
        attach_bet_outcome_snapshots([bet])
        snapshot = getattr(bet, 'outcome_snapshot', None)
    if snapshot is None or snapshot.actual_status is None:
        return False, "Course non terminee: aucun recalcul possible."

    expected_winnings = round(bet.amount * bet.odds_at_bet, 2) if snapshot.actual_status == 'won' else 0.0
    current_payout_delta = _get_bet_payout_balance_delta(bet)
    payout_delta = round(expected_winnings - current_payout_delta, 2)

    if payout_delta > 0:
        adjust_user_balance(
            bet.user_id,
            payout_delta,
            reason_code='bet_payout_adjustment',
            reason_label='Correction gain de pari',
            details=f"Correction admin du ticket #{bet.id} sur la course #{bet.race_id}.",
            reference_type='bet',
            reference_id=bet.id,
        )
    elif payout_delta < 0:
        adjust_user_balance(
            bet.user_id,
            payout_delta,
            reason_code='bet_payout_reversal',
            reason_label='Correction pari',
            details=f"Annulation du trop-percu sur le ticket #{bet.id} de la course #{bet.race_id}.",
            reference_type='bet',
            reference_id=bet.id,
        )

    bet.status = snapshot.actual_status
    bet.winnings = expected_winnings
    return True, snapshot.actual_status


def build_admin_bets_page_context(status_filter='', race_id_filter=None, username_filter='', mismatch_only=False):
    query = Bet.query.join(User, User.id == Bet.user_id).join(Race, Race.id == Bet.race_id)
    if status_filter:
        query = query.filter(Bet.status == status_filter)
    if race_id_filter:
        query = query.filter(Bet.race_id == race_id_filter)
    if username_filter:
        query = query.filter(User.username.ilike(f"%{username_filter}%"))

    bets = (
        query
        .order_by(Bet.placed_at.desc(), Bet.id.desc())
        .limit(150)
        .all()
    )
    attach_bet_outcome_snapshots(bets)

    if mismatch_only:
        bets = [bet for bet in bets if not bet.outcome_snapshot.is_consistent]

    mismatch_count = sum(1 for bet in bets if not bet.outcome_snapshot.is_consistent)
    finished_count = sum(1 for bet in bets if bet.outcome_snapshot.race_finished)

    return {
        'bets': bets,
        'bet_types': get_configured_bet_types(),
        'filters': {
            'status': status_filter,
            'race_id': race_id_filter or '',
            'username': username_filter,
            'mismatch': mismatch_only,
        },
        'stats': {
            'visible': len(bets),
            'finished': finished_count,
            'mismatch': mismatch_count,
        },
    }


def reconcile_finished_bets():
    bets = (
        Bet.query
        .join(Race, Race.id == Bet.race_id)
        .filter(Race.status == 'finished')
        .order_by(Bet.id.asc())
        .all()
    )
    attach_bet_outcome_snapshots(bets)

    updated = 0
    for bet in bets:
        if bet.outcome_snapshot.is_consistent:
            continue
        did_update, _ = reconcile_bet_record(bet)
        if did_update:
            updated += 1

    db.session.commit()
    return updated


def reconcile_bet_by_id(bet_id):
    bet = Bet.query.get(bet_id)
    if not bet:
        return None, False, "Ticket introuvable."

    attach_bet_outcome_snapshots([bet])
    did_update, result = reconcile_bet_record(bet)
    if not did_update:
        return bet, False, result

    db.session.commit()
    return bet, True, result
