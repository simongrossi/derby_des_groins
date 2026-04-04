from datetime import datetime, timedelta

from sqlalchemy import func, or_, update, Numeric

from data import (
    EMERGENCY_RELIEF_AMOUNT, EMERGENCY_RELIEF_HOURS, EMERGENCY_RELIEF_THRESHOLD,
    TAX_THRESHOLD_1, TAX_RATE_1, TAX_THRESHOLD_2, TAX_RATE_2, TAX_EXEMPT_REASON_CODES,
    CASINO_REASON_CODES, CASINO_DAILY_WIN_CAP,
)
from extensions import db
from models import BalanceTransaction, GameConfig, Pig, User


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


def _apply_progressive_tax(user_id, amount, reason_code):
    """Compute tax on a credit. Returns (net_amount, tax_amount).
    Tax is 0 for exempt reason codes and admin users."""
    if reason_code in TAX_EXEMPT_REASON_CODES:
        return amount, 0.0
    user = User.query.get(user_id)
    if not user or getattr(user, 'is_admin', False):
        return amount, 0.0
    balance = float(user.balance or 0.0)
    if balance >= TAX_THRESHOLD_2:
        tax_rate = TAX_RATE_2
    elif balance >= TAX_THRESHOLD_1:
        tax_rate = TAX_RATE_1
    else:
        return amount, 0.0
    tax_amount = round(amount * tax_rate, 2)
    net_amount = round(amount - tax_amount, 2)
    return net_amount, tax_amount


def _add_to_solidarity_fund(tax_amount):
    """Add taxed BitGroins to the solidarity fund stored in GameConfig."""
    if tax_amount <= 0:
        return
    fund = GameConfig.query.filter_by(key='solidarity_fund').first()
    if fund:
        fund.value = str(round(float(fund.value or '0') + tax_amount, 2))
    else:
        db.session.add(GameConfig(key='solidarity_fund', value=str(round(tax_amount, 2))))


def _apply_casino_cap(user_id, amount, reason_code):
    """Cap casino credits to CASINO_DAILY_WIN_CAP per day. Returns effective credit amount."""
    if reason_code not in CASINO_REASON_CODES:
        return amount
    user = User.query.get(user_id)
    if not user or getattr(user, 'is_admin', False):
        return amount
    from datetime import date as date_type
    today = date_type.today()
    if user.last_casino_date != today:
        user.daily_casino_wins = 0.0
        user.last_casino_date = today
    already_won = float(user.daily_casino_wins or 0.0)
    remaining_cap = max(0.0, CASINO_DAILY_WIN_CAP - already_won)
    effective = min(amount, remaining_cap)
    user.daily_casino_wins = round(already_won + effective, 2)
    return effective


def credit_user_balance(user_id, amount, reason_code='credit', reason_label='Crédit BitGroins',
                        details=None, reference_type=None, reference_id=None):
    if amount <= 0:
        return True
    amount = _apply_casino_cap(user_id, amount, reason_code)
    if amount <= 0:
        return True  # Cap reached, silently skip
    net_amount, tax_amount = _apply_progressive_tax(user_id, amount, reason_code)
    if tax_amount > 0:
        _add_to_solidarity_fund(tax_amount)
        if details:
            details = f"{details} (taxe progressive: -{tax_amount} 🪙 → Caisse Solidarité)"
    return adjust_user_balance(
        user_id,
        net_amount,
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


SOLIDARITY_RELIEF_THRESHOLD = 50.0   # déclenche si balance < 50 BG
SOLIDARITY_RELIEF_AMOUNT = 30.0      # montant prélevé sur la caisse


def _get_solidarity_fund_balance():
    fund = GameConfig.query.filter_by(key='solidarity_fund').first()
    return float(fund.value or '0') if fund else 0.0


def maybe_grant_solidarity_relief(user):
    """Distribute from the solidarity fund when the user's balance is below threshold."""
    if not user or getattr(user, 'is_admin', False):
        return 0.0

    now = datetime.utcnow()
    cooldown_limit = now - timedelta(hours=EMERGENCY_RELIEF_HOURS)

    # Only trigger if user has had no recent relief and balance is low
    balance = float(user.balance or 0.0)
    if balance >= SOLIDARITY_RELIEF_THRESHOLD:
        return 0.0
    if user.last_relief_at and user.last_relief_at > cooldown_limit:
        return 0.0

    fund_balance = _get_solidarity_fund_balance()
    if fund_balance < SOLIDARITY_RELIEF_AMOUNT:
        return 0.0

    # Deduct from solidarity fund
    fund = GameConfig.query.filter_by(key='solidarity_fund').first()
    fund.value = str(round(fund_balance - SOLIDARITY_RELIEF_AMOUNT, 2))

    result = db.session.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            balance=func.round((User.balance + SOLIDARITY_RELIEF_AMOUNT).cast(Numeric), 2),
            last_relief_at=now,
        )
        .returning(User.balance)
    )
    row = result.first()
    if not row:
        db.session.rollback()
        return 0.0

    balance_after = round(float(row[0] or 0.0), 2)
    balance_before = round(balance_after - SOLIDARITY_RELIEF_AMOUNT, 2)
    record_balance_transaction(
        user_id=user.id,
        amount=SOLIDARITY_RELIEF_AMOUNT,
        balance_before=balance_before,
        balance_after=balance_after,
        reason_code='solidarity_relief',
        reason_label='Aide de la Caisse de Solidarité',
        details="Redistribution automatique depuis la Caisse Porcine de Solidarité.",
        reference_type='system',
        reference_id=user.id,
    )
    db.session.commit()
    return SOLIDARITY_RELIEF_AMOUNT


def maybe_grant_emergency_relief(user):
    if not user:
        return 0.0

    # Try solidarity fund first (richer relief, requires fund to have money)
    solidarity = maybe_grant_solidarity_relief(user)
    if solidarity > 0:
        return solidarity

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
