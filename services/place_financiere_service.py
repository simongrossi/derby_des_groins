"""Service pour la Place Financière — tableau de bord économique public."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func

from extensions import db
from models import GameConfig, User


DEFAULT_TIRELIRE_CEILING = 50_000.0


def _utcnow_naive():
    return datetime.now(UTC).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Tirelire Centrale
# ---------------------------------------------------------------------------

def get_tirelire_balance() -> float:
    entry = GameConfig.query.filter_by(key='tirelire_centrale').first()
    return float(entry.value or '0') if entry else 0.0


def get_tirelire_ceiling() -> float:
    from helpers.config import get_config
    try:
        return float(get_config('tirelire_ceiling', str(DEFAULT_TIRELIRE_CEILING)))
    except (TypeError, ValueError):
        return DEFAULT_TIRELIRE_CEILING


def _set_tirelire_balance(amount: float):
    amount = round(amount, 2)
    entry = GameConfig.query.filter_by(key='tirelire_centrale').first()
    if entry:
        entry.value = str(amount)
    else:
        db.session.add(GameConfig(key='tirelire_centrale', value=str(amount)))


def _trigger_tirelire_explosion(ceiling: float) -> float:
    """Distribue le plafond de la tirelire à tous les joueurs actifs (7 derniers jours)
    et remet la tirelire à 0. Retourne le montant distribué par joueur."""
    from services.finance_service import credit_user_balance

    cutoff = _utcnow_naive() - timedelta(days=7)
    active_users = User.query.filter(
        User.is_admin.is_(False),
        db.or_(
            User.last_daily_reward_at >= cutoff,
            User.created_at >= cutoff,
        ),
    ).all()

    if not active_users:
        _set_tirelire_balance(0.0)
        return 0.0

    share = round(ceiling / len(active_users), 2)
    for user in active_users:
        credit_user_balance(
            user.id,
            share,
            reason_code='tirelire_explosion',
            reason_label='🎉 Explosion de la Tirelire Centrale !',
            details=(
                f"La Tirelire Centrale a atteint {ceiling:.0f} BG et a explosé ! "
                f"Distribution égale entre {len(active_users)} éleveurs actifs."
            ),
        )

    _set_tirelire_balance(0.0)
    return share


def add_to_tirelire(amount: float) -> dict:
    """Ajoute `amount` à la Tirelire Centrale. Si le plafond est atteint,
    déclenche l'explosion. Retourne un dict avec le nouvel état."""
    if amount <= 0:
        return {'new_balance': get_tirelire_balance(), 'exploded': False, 'share_per_user': 0.0}

    amount = round(amount, 2)
    ceiling = get_tirelire_ceiling()

    entry = GameConfig.query.filter_by(key='tirelire_centrale').first()
    current = float(entry.value or '0') if entry else 0.0
    new_balance = round(current + amount, 2)

    if entry:
        entry.value = str(new_balance)
    else:
        db.session.add(GameConfig(key='tirelire_centrale', value=str(new_balance)))

    if new_balance >= ceiling:
        share = _trigger_tirelire_explosion(ceiling)
        return {'new_balance': 0.0, 'exploded': True, 'share_per_user': share}

    return {'new_balance': new_balance, 'exploded': False, 'share_per_user': 0.0}


# ---------------------------------------------------------------------------
# Caisse de Solidarité — compteur de sauvetages
# ---------------------------------------------------------------------------

def get_solidarity_rescues_count() -> int:
    entry = GameConfig.query.filter_by(key='solidarity_rescues_count').first()
    try:
        return int(entry.value or '0') if entry else 0
    except (TypeError, ValueError):
        return 0


def increment_solidarity_rescues():
    entry = GameConfig.query.filter_by(key='solidarity_rescues_count').first()
    current = 0
    if entry:
        try:
            current = int(entry.value or '0')
        except (TypeError, ValueError):
            current = 0
        entry.value = str(current + 1)
    else:
        db.session.add(GameConfig(key='solidarity_rescues_count', value='1'))


def _get_solidarity_fund_balance() -> float:
    entry = GameConfig.query.filter_by(key='solidarity_fund').first()
    return float(entry.value or '0') if entry else 0.0


# ---------------------------------------------------------------------------
# CAC-Cochon
# ---------------------------------------------------------------------------

def get_cac_cochon() -> float:
    """Somme de tous les soldes joueurs + Tirelire Centrale + Caisse de Solidarité."""
    total_balances = db.session.query(func.coalesce(func.sum(User.balance), 0.0)).scalar() or 0.0
    tirelire = get_tirelire_balance()
    solidarity = _get_solidarity_fund_balance()
    return round(float(total_balances) + tirelire + solidarity, 2)


# ---------------------------------------------------------------------------
# Données agrégées pour le template
# ---------------------------------------------------------------------------

def get_place_financiere_data() -> dict:
    tirelire_balance = get_tirelire_balance()
    tirelire_ceiling = get_tirelire_ceiling()
    tirelire_pct = min(100.0, round(tirelire_balance / tirelire_ceiling * 100, 1)) if tirelire_ceiling > 0 else 0.0

    return {
        'tirelire_balance': tirelire_balance,
        'tirelire_ceiling': tirelire_ceiling,
        'tirelire_pct': tirelire_pct,
        'solidarity_fund_balance': _get_solidarity_fund_balance(),
        'solidarity_rescues_count': get_solidarity_rescues_count(),
        'cac_cochon': get_cac_cochon(),
    }
