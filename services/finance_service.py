from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, or_, update, Numeric

from data import (
    EMERGENCY_RELIEF_AMOUNT, EMERGENCY_RELIEF_HOURS, EMERGENCY_RELIEF_THRESHOLD,
    TAX_THRESHOLD_1, TAX_RATE_1, TAX_THRESHOLD_2, TAX_RATE_2, TAX_EXEMPT_REASON_CODES,
    CASINO_REASON_CODES, CASINO_DAILY_WIN_CAP,
)
from extensions import db
from models import BalanceTransaction, GameConfig, Pig, User

DEFAULT_SOLIDARITY_RELIEF_THRESHOLD = 50.0
DEFAULT_SOLIDARITY_RELIEF_AMOUNT = 30.0


@dataclass(frozen=True)
class FinanceSettings:
    emergency_threshold: float
    emergency_amount: float
    emergency_hours: int
    casino_daily_cap: float
    tax_threshold_1: float
    tax_rate_1: float
    tax_threshold_2: float
    tax_rate_2: float
    solidarity_threshold: float
    solidarity_amount: float


def get_finance_settings():
    from helpers.config import get_config

    def _f(key, default):
        try:
            return float(get_config(key, str(default)))
        except (TypeError, ValueError):
            return float(default)

    def _i(key, default):
        try:
            return int(float(get_config(key, str(default))))
        except (TypeError, ValueError):
            return int(default)

    return FinanceSettings(
        emergency_threshold=_f('balance_emergency_threshold', EMERGENCY_RELIEF_THRESHOLD),
        emergency_amount=_f('balance_emergency_amount', EMERGENCY_RELIEF_AMOUNT),
        emergency_hours=_i('balance_emergency_hours', EMERGENCY_RELIEF_HOURS),
        casino_daily_cap=_f('balance_casino_daily_cap', CASINO_DAILY_WIN_CAP),
        tax_threshold_1=_f('balance_tax_threshold_1', TAX_THRESHOLD_1),
        tax_rate_1=_f('balance_tax_rate_1', TAX_RATE_1),
        tax_threshold_2=_f('balance_tax_threshold_2', TAX_THRESHOLD_2),
        tax_rate_2=_f('balance_tax_rate_2', TAX_RATE_2),
        solidarity_threshold=_f('balance_solidarity_threshold', DEFAULT_SOLIDARITY_RELIEF_THRESHOLD),
        solidarity_amount=_f('balance_solidarity_amount', DEFAULT_SOLIDARITY_RELIEF_AMOUNT),
    )


def build_finance_settings_from_form(form, current_settings=None):
    s = current_settings or get_finance_settings()
    def _f(key, default):
        try:
            return float(form.get(key, default))
        except (TypeError, ValueError):
            return float(default)

    def _i(key, default):
        try:
            return int(float(form.get(key, default)))
        except (TypeError, ValueError):
            return int(default)

    return FinanceSettings(
        emergency_threshold=_f('balance_emergency_threshold', s.emergency_threshold),
        emergency_amount=_f('balance_emergency_amount', s.emergency_amount),
        emergency_hours=_i('balance_emergency_hours', s.emergency_hours),
        casino_daily_cap=_f('balance_casino_daily_cap', s.casino_daily_cap),
        tax_threshold_1=_f('balance_tax_threshold_1', s.tax_threshold_1),
        tax_rate_1=_f('balance_tax_rate_1', s.tax_rate_1),
        tax_threshold_2=_f('balance_tax_threshold_2', s.tax_threshold_2),
        tax_rate_2=_f('balance_tax_rate_2', s.tax_rate_2),
        solidarity_threshold=_f('balance_solidarity_threshold', s.solidarity_threshold),
        solidarity_amount=_f('balance_solidarity_amount', s.solidarity_amount),
    )


def save_finance_settings(settings):
    from helpers.config import set_config, invalidate_config_cache

    payload = {
        'balance_emergency_threshold': settings.emergency_threshold,
        'balance_emergency_amount': settings.emergency_amount,
        'balance_emergency_hours': settings.emergency_hours,
        'balance_casino_daily_cap': settings.casino_daily_cap,
        'balance_tax_threshold_1': settings.tax_threshold_1,
        'balance_tax_rate_1': settings.tax_rate_1,
        'balance_tax_threshold_2': settings.tax_threshold_2,
        'balance_tax_rate_2': settings.tax_rate_2,
        'balance_solidarity_threshold': settings.solidarity_threshold,
        'balance_solidarity_amount': settings.solidarity_amount,
    }
    existing = {
        entry.key: entry
        for entry in GameConfig.query.filter(GameConfig.key.in_(list(payload.keys()))).all()
    }
    for key, value in payload.items():
        entry = existing.get(key)
        str_value = str(value)
        if entry:
            entry.value = str_value
        else:
            db.session.add(GameConfig(key=key, value=str_value))
    db.session.commit()
    invalidate_config_cache()


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
    fs = get_finance_settings()
    if balance >= fs.tax_threshold_2:
        tax_rate = fs.tax_rate_2
    elif balance >= fs.tax_threshold_1:
        tax_rate = fs.tax_rate_1
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
    """Cap casino credits to casino_daily_cap per day. Returns effective credit amount."""
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
    casino_daily_cap = get_finance_settings().casino_daily_cap
    remaining_cap = max(0.0, casino_daily_cap - already_won)
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


def _get_solidarity_fund_balance():
    fund = GameConfig.query.filter_by(key='solidarity_fund').first()
    return float(fund.value or '0') if fund else 0.0


def maybe_grant_solidarity_relief(user):
    """Distribute from the solidarity fund when the user's balance is below threshold."""
    if not user or getattr(user, 'is_admin', False):
        return 0.0

    fs = get_finance_settings()
    now = datetime.utcnow()
    cooldown_limit = now - timedelta(hours=fs.emergency_hours)

    # Only trigger if user has had no recent relief and balance is low
    balance = float(user.balance or 0.0)
    if balance >= fs.solidarity_threshold:
        return 0.0
    if user.last_relief_at and user.last_relief_at > cooldown_limit:
        return 0.0

    fund_balance = _get_solidarity_fund_balance()
    if fund_balance < fs.solidarity_amount:
        return 0.0

    # Deduct from solidarity fund
    fund = GameConfig.query.filter_by(key='solidarity_fund').first()
    fund.value = str(round(fund_balance - fs.solidarity_amount, 2))

    result = db.session.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            balance=func.round((User.balance + fs.solidarity_amount).cast(Numeric), 2),
            last_relief_at=now,
        )
        .returning(User.balance)
    )
    row = result.first()
    if not row:
        db.session.rollback()
        return 0.0

    balance_after = round(float(row[0] or 0.0), 2)
    balance_before = round(balance_after - fs.solidarity_amount, 2)
    record_balance_transaction(
        user_id=user.id,
        amount=fs.solidarity_amount,
        balance_before=balance_before,
        balance_after=balance_after,
        reason_code='solidarity_relief',
        reason_label='Aide de la Caisse de Solidarité',
        details="Redistribution automatique depuis la Caisse Porcine de Solidarité.",
        reference_type='system',
        reference_id=user.id,
    )
    db.session.commit()
    return fs.solidarity_amount


def maybe_grant_emergency_relief(user):
    if not user:
        return 0.0

    # Try solidarity fund first (richer relief, requires fund to have money)
    solidarity = maybe_grant_solidarity_relief(user)
    if solidarity > 0:
        return solidarity

    fs = get_finance_settings()
    now = datetime.utcnow()
    cooldown_limit = now - timedelta(hours=fs.emergency_hours)
    result = db.session.execute(
        update(User)
        .where(
            User.id == user.id,
            User.balance < fs.emergency_threshold,
            or_(User.last_relief_at.is_(None), User.last_relief_at <= cooldown_limit),
        )
        .values(
            balance=func.round((User.balance + fs.emergency_amount).cast(Numeric), 2),
            last_relief_at=now,
        )
        .returning(User.balance)
    )
    row = result.first()
    if not row:
        db.session.rollback()
        return 0.0

    balance_after = round(float(row[0] or 0.0), 2)
    balance_before = round(balance_after - fs.emergency_amount, 2)
    record_balance_transaction(
        user_id=user.id,
        amount=fs.emergency_amount,
        balance_before=balance_before,
        balance_after=balance_after,
        reason_code='emergency_relief',
        reason_label="Prime d'urgence",
        details="Filet de sécurité automatique pour éviter un blocage à 0 🪙.",
        reference_type='system',
        reference_id=user.id,
    )

    db.session.commit()
    return fs.emergency_amount
