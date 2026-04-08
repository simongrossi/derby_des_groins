from services.trophy_builder_service import build_user_trophies


def _default_bet_entry():
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


def build_empty_chart_data():
    return {
        'labels': [],
        'balances': [],
        'wins': [],
        'dead': [],
        'all_labels': [],
        'all_dead': [],
        'all_challenge': [],
        'all_blessure': [],
        'all_sacrifice': [],
        'all_vieillesse': [],
        'all_bet_profit': [],
        'all_win_rate': [],
        'all_races': [],
    }


def build_empty_classement_context():
    return {
        'rankings': [],
        'chart_data': build_empty_chart_data(),
        'awards': [],
    }


def _build_death_metrics(user_pigs):
    dead_pigs = [pig for pig in user_pigs if not pig.is_alive]
    tracked_dead_pigs = [pig for pig in dead_pigs if pig.death_cause != 'vendu']
    deaths_by_cause = {}
    for pig in tracked_dead_pigs:
        if pig.death_cause:
            deaths_by_cause[pig.death_cause] = deaths_by_cause.get(pig.death_cause, 0) + 1

    return {
        'dead_count': len(tracked_dead_pigs),
        'deaths_challenge': deaths_by_cause.get('challenge', 0),
        'deaths_blessure': deaths_by_cause.get('blessure', 0),
        'deaths_sacrifice': deaths_by_cause.get('sacrifice_volontaire', 0) + deaths_by_cause.get('sacrifice', 0),
        'deaths_vieillesse': deaths_by_cause.get('vieillesse', 0),
        'legendary_dead': sum(1 for pig in tracked_dead_pigs if (pig.races_won or 0) >= 3),
    }


def _build_bet_metrics(entry):
    entry = entry or _default_bet_entry()
    won_bets = entry['won']
    lost_bets = entry['lost']
    settled_staked = entry['won_staked'] + entry['lost_staked']
    settled_count = won_bets + lost_bets

    return {
        'total_bets': entry['total'],
        'won_bets': won_bets,
        'lost_bets': lost_bets,
        'total_staked': round(entry['staked'], 2),
        'total_winnings': round(entry['winnings'], 2),
        'bet_profit': round(entry['winnings'] - settled_staked, 2),
        'bet_win_rate': round((won_bets / settled_count) * 100, 1) if settled_count else 0.0,
        'best_odds_hit': round(entry['best_odds'], 1),
    }


def build_rankings(users, query_data):
    rankings = []

    for user in users:
        total_wins, total_races = query_data.pig_stats.get(user.id, (0, 0))
        win_rate = round((total_wins / total_races) * 100, 1) if total_races else 0.0
        user_pigs = query_data.pigs_by_user.get(user.id, [])
        active_pigs = [pig for pig in user_pigs if pig.is_alive]
        death_metrics = _build_death_metrics(user_pigs)
        bet_metrics = _build_bet_metrics(query_data.bet_stats.get(user.id))
        best_pig = max(
            user_pigs,
            key=lambda pig: (pig.races_won or 0, pig.level or 0),
            default=None,
        )

        ranking = {
            'user': user,
            'total_wins': total_wins,
            'total_races': total_races,
            'win_rate': win_rate,
            **death_metrics,
            **bet_metrics,
            'best_pig': best_pig,
            'max_level': max((pig.level or 1 for pig in user_pigs), default=1),
            'total_school': sum(pig.school_sessions_completed or 0 for pig in user_pigs),
            'total_xp': sum(pig.xp or 0 for pig in user_pigs),
            'legendary_count': sum(1 for pig in user_pigs if pig.rarity == 'legendaire'),
            'active_pigs_count': len(active_pigs),
            'total_spent_on_food': query_data.food_spent.get(user.id, 0.0),
            'total_earned': query_data.total_earned.get(user.id, 0.0),
        }
        ranking['score'] = round(user.balance + (ranking['total_wins'] * 50), 2)
        ranking['trophies'] = build_user_trophies(
            user,
            ranking,
            query_data.trophies_by_user.get(user.id, []),
        )
        rankings.append(ranking)

    rankings.sort(key=lambda item: item['score'], reverse=True)
    return rankings


def build_chart_data(rankings):
    if not rankings:
        return build_empty_chart_data()

    top_5 = rankings[:5]
    return {
        'labels': [entry['user'].username for entry in top_5],
        'balances': [entry['user'].balance for entry in top_5],
        'wins': [entry['total_wins'] for entry in top_5],
        'dead': [entry['dead_count'] for entry in top_5],
        'all_labels': [entry['user'].username for entry in rankings],
        'all_dead': [entry['dead_count'] for entry in rankings],
        'all_challenge': [entry['deaths_challenge'] for entry in rankings],
        'all_blessure': [entry['deaths_blessure'] for entry in rankings],
        'all_sacrifice': [entry['deaths_sacrifice'] for entry in rankings],
        'all_vieillesse': [entry['deaths_vieillesse'] for entry in rankings],
        'all_bet_profit': [entry['bet_profit'] for entry in rankings],
        'all_win_rate': [entry['win_rate'] for entry in rankings],
        'all_races': [entry['total_races'] for entry in rankings],
    }
