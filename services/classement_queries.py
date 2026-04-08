from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import func

from extensions import db
from models import BalanceTransaction, Bet, Pig, Trophy


@dataclass(frozen=True)
class ClassementQueryData:
    pig_stats: dict
    pigs_by_user: dict
    bet_stats: dict
    food_spent: dict
    total_earned: dict
    trophies_by_user: dict


def _build_default_bet_entry():
    return {
        'total': 0,
        'won': 0,
        'lost': 0,
        'staked': 0.0,
        'winnings': 0.0,
        'won_staked': 0.0,
        'lost_staked': 0.0,
        'best_odds': 0.0,
    }


def fetch_pig_stats_by_user():
    rows = (
        db.session.query(
            Pig.user_id,
            func.coalesce(func.sum(Pig.races_won), 0),
            func.coalesce(func.sum(Pig.races_entered), 0),
        )
        .group_by(Pig.user_id)
        .all()
    )
    return {user_id: (int(total_wins), int(total_races)) for user_id, total_wins, total_races in rows}


def fetch_pigs_by_user():
    pigs_by_user = defaultdict(list)
    for pig in Pig.query.all():
        pigs_by_user[pig.user_id].append(pig)
    return dict(pigs_by_user)


def fetch_bet_stats_by_user():
    rows = (
        db.session.query(
            Bet.user_id,
            Bet.status,
            func.count(Bet.id),
            func.coalesce(func.sum(Bet.amount), 0.0),
            func.coalesce(func.sum(Bet.winnings), 0.0),
            func.max(db.case((Bet.status == 'won', Bet.odds_at_bet), else_=0.0)),
        )
        .group_by(Bet.user_id, Bet.status)
        .all()
    )

    bet_stats = {}
    for user_id, status, count, staked, winnings, best_odds in rows:
        entry = bet_stats.setdefault(user_id, _build_default_bet_entry())
        entry['total'] += int(count or 0)
        entry['staked'] += float(staked or 0.0)
        if status == 'won':
            entry['won'] = int(count or 0)
            entry['winnings'] = float(winnings or 0.0)
            entry['won_staked'] = float(staked or 0.0)
            entry['best_odds'] = max(entry['best_odds'], float(best_odds or 0.0))
        elif status == 'lost':
            entry['lost'] = int(count or 0)
            entry['lost_staked'] = float(staked or 0.0)
    return bet_stats


def fetch_food_spent_by_user():
    rows = (
        db.session.query(
            BalanceTransaction.user_id,
            func.coalesce(func.sum(func.abs(BalanceTransaction.amount)), 0.0),
        )
        .filter(BalanceTransaction.reason_code == 'feed_purchase')
        .group_by(BalanceTransaction.user_id)
        .all()
    )
    return {user_id: round(float(value), 2) for user_id, value in rows}


def fetch_total_earned_by_user():
    rows = (
        db.session.query(
            BalanceTransaction.user_id,
            func.coalesce(func.sum(BalanceTransaction.amount), 0.0),
        )
        .filter(
            BalanceTransaction.amount > 0,
            BalanceTransaction.reason_code != 'snapshot',
        )
        .group_by(BalanceTransaction.user_id)
        .all()
    )
    return {user_id: round(float(value), 2) for user_id, value in rows}


def fetch_trophies_by_user():
    trophies_by_user = defaultdict(list)
    for trophy in Trophy.query.order_by(Trophy.earned_at.asc()).all():
        trophies_by_user[trophy.user_id].append(trophy)
    return dict(trophies_by_user)


def load_classement_query_data():
    return ClassementQueryData(
        pig_stats=fetch_pig_stats_by_user(),
        pigs_by_user=fetch_pigs_by_user(),
        bet_stats=fetch_bet_stats_by_user(),
        food_spent=fetch_food_spent_by_user(),
        total_earned=fetch_total_earned_by_user(),
        trophies_by_user=fetch_trophies_by_user(),
    )
