from datetime import datetime, timedelta

from sqlalchemy import func, or_, update, Numeric

from data import EMERGENCY_RELIEF_AMOUNT, EMERGENCY_RELIEF_HOURS, EMERGENCY_RELIEF_THRESHOLD
from extensions import db
from models import BalanceTransaction, Pig, User


def record_balance_transaction(user_id, amount, balance_before, balance_after,
                               reason_code='adjustment', reason_label='Mouvement BitGroins',
                               details=None, reference_type=None, reference_id=None):
    tx = BalanceTransaction(
        user_id=user_id,
        amount=round(amount, 2),
        balance_before=None if balance_before is None else round(balance_before, 2),
        balance_after=None if balance_after is None else round(balance_after, 2),
        reason_code=reason_code or 'adjustment',
        reason_label=reason_label or 'Mouvement BitGroins',
        details=details,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    db.session.add(tx)
    return tx


def adjust_user_balance(user_id, delta, minimum_balance=None,
                        reason_code='adjustment', reason_label='Mouvement BitGroins',
                        details=None, reference_type=None, reference_id=None):
    delta = round(float(delta or 0.0), 2)
    if delta == 0:
        return True

    stmt = update(User).where(User.id == user_id)
    if minimum_balance is not None:
        stmt = stmt.where(User.balance >= minimum_balance)
    stmt = stmt.values(balance=func.round((User.balance + delta).cast(Numeric), 2)).returning(User.balance)

    row = db.session.execute(stmt).first()
    if not row:
        db.session.rollback()
        return False
    balance_after = round(float(row[0] or 0.0), 2)
    balance_before = round(balance_after - delta, 2)
    record_balance_transaction(
        user_id=user_id,
        amount=delta,
        balance_before=balance_before,
        balance_after=balance_after,
        reason_code=reason_code,
        reason_label=reason_label,
        details=details,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    return True


def debit_user_balance(user_id, amount, reason_code='debit', reason_label='Débit BitGroins',
                       details=None, reference_type=None, reference_id=None):
    if amount <= 0:
        return False
    return adjust_user_balance(
        user_id,
        -amount,
        minimum_balance=amount,
        reason_code=reason_code,
        reason_label=reason_label,
        details=details,
        reference_type=reference_type,
        reference_id=reference_id,
    )


def credit_user_balance(user_id, amount, reason_code='credit', reason_label='Crédit BitGroins',
                        details=None, reference_type=None, reference_id=None):
    if amount <= 0:
        return True
    return adjust_user_balance(
        user_id,
        amount,
        reason_code=reason_code,
        reason_label=reason_label,
        details=details,
        reference_type=reference_type,
        reference_id=reference_id,
    )


def reserve_pig_challenge_slot(pig_id, wager):
    result = db.session.execute(
        update(Pig)
        .where(Pig.id == pig_id, Pig.is_alive == True, Pig.challenge_mort_wager <= 0)
        .values(challenge_mort_wager=wager)
    )
    if result.rowcount != 1:
        db.session.rollback()
        return False
    return True


def release_pig_challenge_slot(pig_id):
    pig = Pig.query.get(pig_id)
    if not pig or pig.challenge_mort_wager <= 0:
        return 0.0

    current_wager = round(pig.challenge_mort_wager or 0.0, 2)
    refund = round(current_wager * 0.5, 2)
    result = db.session.execute(
        update(Pig)
        .where(Pig.id == pig_id, Pig.is_alive == True, Pig.challenge_mort_wager == current_wager)
        .values(challenge_mort_wager=0.0)
    )
    if result.rowcount != 1:
        db.session.rollback()
        return 0.0
    return refund


def maybe_grant_emergency_relief(user):
    if not user:
        return 0.0

    now = datetime.utcnow()
    cooldown_limit = now - timedelta(hours=EMERGENCY_RELIEF_HOURS)
    result = db.session.execute(
        update(User)
        .where(
            User.id == user.id,
            User.balance < EMERGENCY_RELIEF_THRESHOLD,
            or_(User.last_relief_at.is_(None), User.last_relief_at <= cooldown_limit),
        )
        .values(
            balance=func.round((User.balance + EMERGENCY_RELIEF_AMOUNT).cast(Numeric), 2),
            last_relief_at=now,
        )
        .returning(User.balance)
    )
    row = result.first()
    if not row:
        db.session.rollback()
        return 0.0

    balance_after = round(float(row[0] or 0.0), 2)
    balance_before = round(balance_after - EMERGENCY_RELIEF_AMOUNT, 2)
    record_balance_transaction(
        user_id=user.id,
        amount=EMERGENCY_RELIEF_AMOUNT,
        balance_before=balance_before,
        balance_after=balance_after,
        reason_code='emergency_relief',
        reason_label="Prime d'urgence",
        details="Filet de sécurité automatique pour éviter un blocage à 0 🪙.",
        reference_type='system',
        reference_id=user.id,
    )

    db.session.commit()
    return EMERGENCY_RELIEF_AMOUNT
