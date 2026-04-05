from datetime import datetime
from statistics import median

from helpers.race import get_race_history_entries
from models import BalanceTransaction, Bet, User
from services.economy_service import get_configured_bet_types
from services.race_service import attach_bet_outcome_snapshots


def _get_bet_net_delta(bet):
    if bet.status == 'won':
        return round(float((bet.winnings or 0.0) - (bet.amount or 0.0)), 2)
    if bet.status == 'lost':
        return round(float(-(bet.amount or 0.0)), 2)
    if bet.status == 'refunded':
        return 0.0
    return None


def _build_bitgroins_curve_context(transactions):
    ordered_transactions = sorted(
        transactions or [],
        key=lambda tx: (
            tx.created_at or datetime.min,
            tx.id or 0,
        ),
    )
    series_by_user = {}
    total_points = 0

    for tx in ordered_transactions:
        if not tx.user:
            continue
        created_at = tx.created_at or datetime.min
        timestamp_ms = int(created_at.timestamp() * 1000)
        username = tx.user.username
        user_series = series_by_user.setdefault(tx.user_id, {
            'user_id': tx.user_id,
            'label': username,
            'points': [],
            'tx_count': 0,
            'peak_balance': None,
            'lowest_balance': None,
            'largest_jump': 0.0,
            'largest_drop': 0.0,
            'current_balance': 0.0,
            'last_at': None,
        })

        balance_after = round(float(tx.balance_after or 0.0), 2)
        amount = round(float(tx.amount or 0.0), 2)
        user_series['points'].append({
            'x': timestamp_ms,
            'y': balance_after,
            'amount': amount,
            'reason': tx.reason_label,
            'date': created_at.strftime('%d/%m/%Y %H:%M'),
        })
        user_series['tx_count'] += 1
        user_series['current_balance'] = balance_after
        user_series['last_at'] = created_at.strftime('%d/%m %H:%M')
        user_series['peak_balance'] = balance_after if user_series['peak_balance'] is None else max(user_series['peak_balance'], balance_after)
        user_series['lowest_balance'] = balance_after if user_series['lowest_balance'] is None else min(user_series['lowest_balance'], balance_after)
        if tx.reason_code != 'snapshot':
            user_series['largest_jump'] = max(user_series['largest_jump'], amount)
            user_series['largest_drop'] = min(user_series['largest_drop'], amount)
        total_points += 1

    rows = sorted(
        (
            {
                'user_id': series['user_id'],
                'label': series['label'],
                'tx_count': series['tx_count'],
                'current_balance': round(series['current_balance'], 2),
                'peak_balance': round(series['peak_balance'] or 0.0, 2),
                'lowest_balance': round(series['lowest_balance'] or 0.0, 2),
                'largest_jump': round(series['largest_jump'], 2),
                'largest_drop': round(series['largest_drop'], 2),
                'last_at': series['last_at'],
            }
            for series in series_by_user.values()
            if series['points']
        ),
        key=lambda row: (-row['current_balance'], row['label'].lower()),
    )

    datasets = [
        {
            'label': series['label'],
            'user_id': series['user_id'],
            'data': series['points'],
        }
        for series in sorted(
            series_by_user.values(),
            key=lambda item: (-(item['current_balance'] or 0.0), item['label'].lower()),
        )
        if series['points']
    ]

    biggest_jump_row = max(rows, key=lambda row: row['largest_jump'], default=None)
    lowest_drop_row = min(rows, key=lambda row: row['largest_drop'], default=None)

    return {
        'datasets': datasets,
        'rows': rows,
        'total_points': total_points,
        'user_count': len(rows),
        'biggest_jump': biggest_jump_row,
        'biggest_drop': lowest_drop_row,
    }


def _build_bet_curve_context(bets):
    ordered_bets = sorted(
        bets or [],
        key=lambda bet: (
            bet.placed_at or datetime.min,
            bet.id or 0,
        ),
    )
    settled_deltas = [
        abs(delta)
        for bet in ordered_bets
        for delta in [_get_bet_net_delta(bet)]
        if delta is not None and abs(delta) > 0
    ]
    suspicious_threshold = 0.0
    if settled_deltas:
        suspicious_threshold = max(150.0, round(float(median(settled_deltas)) * 4, 2))

    series_by_user = {}
    total_points = 0
    for bet in ordered_bets:
        if not bet.user:
            continue
        delta = _get_bet_net_delta(bet)
        if delta is None:
            continue
        created_at = bet.placed_at or datetime.min
        timestamp_ms = int(created_at.timestamp() * 1000)
        username = bet.user.username
        user_series = series_by_user.setdefault(bet.user_id, {
            'user_id': bet.user_id,
            'label': username,
            'points': [],
            'bet_count': 0,
            'settled_count': 0,
            'cumulative_profit': 0.0,
            'peak_profit': 0.0,
            'lowest_profit': 0.0,
            'largest_jump': 0.0,
            'largest_drop': 0.0,
            'last_at': None,
        })
        user_series['bet_count'] += 1
        if bet.status in ('won', 'lost', 'refunded'):
            user_series['settled_count'] += 1
        user_series['cumulative_profit'] = round(user_series['cumulative_profit'] + delta, 2)
        user_series['peak_profit'] = max(user_series['peak_profit'], user_series['cumulative_profit'])
        user_series['lowest_profit'] = min(user_series['lowest_profit'], user_series['cumulative_profit'])
        user_series['largest_jump'] = max(user_series['largest_jump'], delta)
        user_series['largest_drop'] = min(user_series['largest_drop'], delta)
        user_series['last_at'] = created_at.strftime('%d/%m %H:%M')
        user_series['points'].append({
            'x': timestamp_ms,
            'y': user_series['cumulative_profit'],
            'delta': delta,
            'date': created_at.strftime('%d/%m/%Y %H:%M'),
            'bet_label': getattr(getattr(bet, 'outcome_snapshot', None), 'bet_label', bet.bet_type),
            'selection': bet.pig_name,
            'status': bet.status,
        })
        total_points += 1

    rows = []
    for series in series_by_user.values():
        if not series['points']:
            continue
        max_abs_swing = max(abs(series['largest_jump']), abs(series['largest_drop']))
        is_suspicious = bool(suspicious_threshold and max_abs_swing >= suspicious_threshold)
        rows.append({
            'user_id': series['user_id'],
            'label': series['label'],
            'bet_count': series['bet_count'],
            'settled_count': series['settled_count'],
            'cumulative_profit': round(series['cumulative_profit'], 2),
            'peak_profit': round(series['peak_profit'], 2),
            'lowest_profit': round(series['lowest_profit'], 2),
            'largest_jump': round(series['largest_jump'], 2),
            'largest_drop': round(series['largest_drop'], 2),
            'max_abs_swing': round(max_abs_swing, 2),
            'last_at': series['last_at'],
            'is_suspicious': is_suspicious,
        })

    rows.sort(key=lambda row: (-row['cumulative_profit'], row['label'].lower()))
    datasets = [
        {
            'label': series['label'],
            'user_id': series['user_id'],
            'data': series['points'],
            'is_suspicious': next((row['is_suspicious'] for row in rows if row['user_id'] == series['user_id']), False),
        }
        for series in sorted(
            series_by_user.values(),
            key=lambda item: (-(item['cumulative_profit'] or 0.0), item['label'].lower()),
        )
        if series['points']
    ]
    biggest_jump_row = max(rows, key=lambda row: row['largest_jump'], default=None)
    biggest_drop_row = min(rows, key=lambda row: row['largest_drop'], default=None)

    return {
        'datasets': datasets,
        'rows': rows,
        'total_points': total_points,
        'user_count': len(rows),
        'biggest_jump': biggest_jump_row,
        'biggest_drop': biggest_drop_row,
        'suspicious_threshold': suspicious_threshold,
        'suspicious_count': sum(1 for row in rows if row['is_suspicious']),
    }


def _normalize_selected_user_ids(raw_values):
    selected_ids = []
    for raw_value in raw_values or []:
        if raw_value == 'all':
            return []
        try:
            selected_ids.append(int(raw_value))
        except (TypeError, ValueError):
            continue
    return sorted(set(selected_ids))


def build_history_page_context(current_user_id, view_user_id=None, bet_filter_values=None, tx_filter_values=None):
    current_user = User.query.get(current_user_id)
    target_user = User.query.get(view_user_id or current_user.id) if current_user else None
    if not target_user:
        target_user = current_user

    all_users = User.query.order_by(User.username).all()

    bet_filter_raw = 'all'
    bet_filter_user = None
    bet_filter_users = []
    bet_query = Bet.query.order_by(Bet.placed_at.desc(), Bet.id.desc())

    bet_selected_user_ids = _normalize_selected_user_ids(bet_filter_values)
    if bet_selected_user_ids:
        bet_filter_users = User.query.filter(User.id.in_(bet_selected_user_ids)).order_by(User.username).all()
        bet_selected_user_ids = [user.id for user in bet_filter_users]
        if bet_selected_user_ids:
            bet_query = bet_query.filter(Bet.user_id.in_(bet_selected_user_ids))
            bet_filter_raw = 'multi'
            bet_filter_user = bet_filter_users[0] if len(bet_filter_users) == 1 else None

    bets = bet_query.all()
    attach_bet_outcome_snapshots(bets)
    bet_curve = _build_bet_curve_context(bets)

    tx_filter_raw = 'all'
    tx_filter_user = None
    tx_filter_users = []
    tx_query = BalanceTransaction.query.order_by(BalanceTransaction.created_at.desc(), BalanceTransaction.id.desc())

    tx_selected_user_ids = _normalize_selected_user_ids(tx_filter_values)
    if tx_selected_user_ids:
        tx_filter_users = User.query.filter(User.id.in_(tx_selected_user_ids)).order_by(User.username).all()
        tx_selected_user_ids = [user.id for user in tx_filter_users]
        if tx_selected_user_ids:
            tx_query = tx_query.filter(BalanceTransaction.user_id.in_(tx_selected_user_ids))
            tx_filter_raw = 'multi'
            tx_filter_user = tx_filter_users[0] if len(tx_filter_users) == 1 else None

    transactions = tx_query.all()
    bitgroins_curve = _build_bitgroins_curve_context(transactions)
    race_history = get_race_history_entries()

    won_bets = [bet for bet in bets if bet.status == 'won']
    lost_bets = [bet for bet in bets if bet.status == 'lost']
    settled_bets = won_bets + lost_bets
    credited_amount = round(
        sum(tx.amount for tx in transactions if tx.amount > 0 and tx.reason_code != 'snapshot'),
        2,
    )
    debited_amount = round(
        sum(abs(tx.amount) for tx in transactions if tx.amount < 0 and tx.reason_code != 'snapshot'),
        2,
    )

    return {
        'user': current_user,
        'target_user': target_user,
        'all_users': all_users,
        'bets': bets,
        'won_bets': won_bets,
        'lost_bets': lost_bets,
        'settled_bets': settled_bets,
        'bet_filter_raw': bet_filter_raw,
        'bet_filter_user': bet_filter_user,
        'bet_filter_users': bet_filter_users,
        'bet_selected_user_ids': bet_selected_user_ids,
        'bet_curve': bet_curve,
        'transactions': transactions,
        'bitgroins_curve': bitgroins_curve,
        'tx_filter_raw': tx_filter_raw,
        'tx_filter_user': tx_filter_user,
        'tx_filter_users': tx_filter_users,
        'tx_selected_user_ids': tx_selected_user_ids,
        'race_history': race_history,
        'bet_types': get_configured_bet_types(),
        'credited_amount': credited_amount,
        'debited_amount': debited_amount,
    }
