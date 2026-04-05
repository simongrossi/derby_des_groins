from sqlalchemy import func

from extensions import db
from models import BalanceTransaction, Bet, Pig, Trophy, User


def build_empty_classement_page_context():
    return {
        'rankings': [],
        'chart_data': {
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
        },
        'awards': [],
    }


def build_classement_page_context():
    all_users = User.query.all()
    if not all_users:
        return build_empty_classement_page_context()

    pig_stats_rows = (
        db.session.query(
            Pig.user_id,
            func.coalesce(func.sum(Pig.races_won), 0),
            func.coalesce(func.sum(Pig.races_entered), 0),
        )
        .group_by(Pig.user_id)
        .all()
    )
    pig_stats = {uid: (int(w), int(r)) for uid, w, r in pig_stats_rows}

    all_pigs_list = Pig.query.all()
    pigs_by_user = {}
    for pig in all_pigs_list:
        pigs_by_user.setdefault(pig.user_id, []).append(pig)

    bet_stats_rows = (
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
    for uid, status, count, staked, winnings, best_odds in bet_stats_rows:
        entry = bet_stats.setdefault(uid, {
            'total': 0,
            'won': 0,
            'lost': 0,
            'staked': 0.0,
            'winnings': 0.0,
            'won_staked': 0.0,
            'lost_staked': 0.0,
            'best_odds': 0.0,
        })
        entry['total'] += count
        entry['staked'] += float(staked)
        if status == 'won':
            entry['won'] = count
            entry['winnings'] = float(winnings)
            entry['won_staked'] = float(staked)
            entry['best_odds'] = max(entry['best_odds'], float(best_odds or 0))
        elif status == 'lost':
            entry['lost'] = count
            entry['lost_staked'] = float(staked)

    food_rows = (
        db.session.query(
            BalanceTransaction.user_id,
            func.coalesce(func.sum(func.abs(BalanceTransaction.amount)), 0.0),
        )
        .filter(BalanceTransaction.reason_code == 'feed_purchase')
        .group_by(BalanceTransaction.user_id)
        .all()
    )
    food_spent = {uid: round(float(value), 2) for uid, value in food_rows}

    earned_rows = (
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
    total_earned_map = {uid: round(float(value), 2) for uid, value in earned_rows}

    all_trophies = Trophy.query.order_by(Trophy.earned_at.asc()).all()
    trophies_by_user = {}
    for trophy in all_trophies:
        trophies_by_user.setdefault(trophy.user_id, []).append(trophy)

    rankings = []
    for user in all_users:
        total_wins, total_races = pig_stats.get(user.id, (0, 0))
        win_rate = (total_wins / total_races * 100) if total_races > 0 else 0

        user_pigs = pigs_by_user.get(user.id, [])
        dead_pigs = [pig for pig in user_pigs if not pig.is_alive]
        dead_pigs_count = len([pig for pig in dead_pigs if pig.death_cause != 'vendu'])
        deaths_by_cause = {}
        for pig in dead_pigs:
            if pig.death_cause and pig.death_cause != 'vendu':
                deaths_by_cause[pig.death_cause] = deaths_by_cause.get(pig.death_cause, 0) + 1
        deaths_challenge = deaths_by_cause.get('challenge', 0)
        deaths_blessure = deaths_by_cause.get('blessure', 0)
        deaths_sacrifice = deaths_by_cause.get('sacrifice_volontaire', 0) + deaths_by_cause.get('sacrifice', 0)
        deaths_vieillesse = deaths_by_cause.get('vieillesse', 0)
        legendary_dead = sum(
            1 for pig in dead_pigs if pig.death_cause != 'vendu' and (pig.races_won or 0) >= 3
        )

        bet_entry = bet_stats.get(user.id, {
            'total': 0,
            'won': 0,
            'lost': 0,
            'staked': 0.0,
            'winnings': 0.0,
            'won_staked': 0.0,
            'lost_staked': 0.0,
            'best_odds': 0.0,
        })
        total_bets = bet_entry['total']
        won_bets_count = bet_entry['won']
        lost_bets_count = bet_entry['lost']
        total_staked = round(bet_entry['staked'], 2)
        total_winnings = round(bet_entry['winnings'], 2)
        settled_staked = bet_entry['won_staked'] + bet_entry['lost_staked']
        bet_profit = round(total_winnings - settled_staked, 2)
        settled_count = won_bets_count + lost_bets_count
        bet_win_rate = round((won_bets_count / settled_count) * 100, 1) if settled_count else 0.0
        best_odds_hit = bet_entry['best_odds']

        active_pigs = [pig for pig in user_pigs if pig.is_alive]
        best_pig = max(
            user_pigs,
            key=lambda pig: (pig.races_won or 0, pig.level or 0),
            default=None,
        )
        max_level = max((pig.level or 1 for pig in user_pigs), default=1)
        total_school = sum(pig.school_sessions_completed or 0 for pig in user_pigs)
        total_xp = sum(pig.xp or 0 for pig in user_pigs)
        legendary_count = sum(1 for pig in user_pigs if pig.rarity == 'legendaire')

        total_spent_on_food = food_spent.get(user.id, 0.0)
        total_earned = total_earned_map.get(user.id, 0.0)

        trophies = []
        if user.balance >= 500:
            trophies.append({'n': 'Cresus', 'e': '💰', 'd': 'Plus de 500 🪙 en caisse'})
        if user.balance >= 1000:
            trophies.append({'n': 'Oligarque', 'e': '👑', 'd': 'Plus de 1000 🪙 en caisse'})
        if total_wins >= 10:
            trophies.append({'n': 'Legende', 'e': '🏆', 'd': '10 victoires au total'})
        if total_wins >= 25:
            trophies.append({'n': 'Dynastie', 'e': '🏛️', 'd': '25 victoires au total'})
        if dead_pigs_count >= 5:
            trophies.append({'n': 'Boucher', 'e': '🔪', 'd': '5 cochons morts'})
        if dead_pigs_count >= 10:
            trophies.append({'n': 'Equarrisseur', 'e': '💀', 'd': '10 cochons morts'})
        if total_races >= 50:
            trophies.append({'n': 'Veteran', 'e': '🎖️', 'd': '50 courses disputees'})
        if total_races >= 100:
            trophies.append({'n': 'Marathonien', 'e': '🏃', 'd': '100 courses disputees'})
        if deaths_challenge >= 3:
            trophies.append({'n': 'Kamikaze', 'e': '💣', 'd': '3 cochons morts au Challenge'})
        if deaths_blessure >= 3:
            trophies.append({'n': 'Negligent', 'e': '🩹', 'd': '3 cochons morts par blessure'})
        if deaths_vieillesse >= 2:
            trophies.append({'n': 'Eleveur Sage', 'e': '🧓', 'd': '2 cochons morts de vieillesse'})
        if total_school >= 20:
            trophies.append({'n': 'Pedagogue', 'e': '📚', 'd': '20 sessions ecole'})
        if total_school >= 50:
            trophies.append({'n': 'Doyen', 'e': '🎓', 'd': '50 sessions ecole'})
        if won_bets_count >= 10:
            trophies.append({'n': 'Parieur', 'e': '🎟️', 'd': '10 paris gagnes'})
        if best_odds_hit >= 5.0:
            trophies.append({'n': 'Sniper', 'e': '🎯', 'd': 'Pari gagne a x5+'})
        if best_odds_hit >= 10.0:
            trophies.append({'n': 'Fou Furieux', 'e': '🔥', 'd': 'Pari gagne a x10+'})
        if bet_profit <= -100:
            trophies.append({'n': 'Ruine', 'e': '📉', 'd': 'Perdu plus de 100 🪙 en paris'})
        if legendary_count >= 1:
            trophies.append({'n': 'Collectionneur', 'e': '🟡', 'd': 'Posseder un cochon legendaire'})
        if deaths_sacrifice >= 3:
            trophies.append({'n': 'Sans Pitie', 'e': '🗡️', 'd': '3 cochons sacrifies'})
        if legendary_dead >= 1:
            trophies.append({'n': 'Sacrilege', 'e': '⚱️', 'd': 'Avoir perdu un cochon legendaire'})
        if total_bets > 0 and won_bets_count == 0:
            trophies.append({'n': 'La Poisse', 'e': '🐌', 'd': 'Aucun pari gagne'})
        if win_rate >= 40 and total_races >= 10:
            trophies.append({'n': 'Stratege', 'e': '🧠', 'd': '40%+ win rate (10+ courses)'})
        for trophy in trophies_by_user.get(user.id, []):
            trophies.append({'n': trophy.label, 'e': trophy.emoji, 'd': trophy.description})

        rankings.append({
            'user': user,
            'total_wins': total_wins,
            'total_races': total_races,
            'win_rate': round(win_rate, 1),
            'dead_count': dead_pigs_count,
            'deaths_challenge': deaths_challenge,
            'deaths_blessure': deaths_blessure,
            'deaths_sacrifice': deaths_sacrifice,
            'deaths_vieillesse': deaths_vieillesse,
            'legendary_dead': legendary_dead,
            'total_bets': total_bets,
            'won_bets': won_bets_count,
            'lost_bets': lost_bets_count,
            'total_staked': total_staked,
            'total_winnings': total_winnings,
            'bet_profit': bet_profit,
            'bet_win_rate': bet_win_rate,
            'best_odds_hit': round(best_odds_hit, 1),
            'best_pig': best_pig,
            'max_level': max_level,
            'total_school': total_school,
            'total_xp': total_xp,
            'legendary_count': legendary_count,
            'active_pigs_count': len(active_pigs),
            'total_spent_on_food': total_spent_on_food,
            'total_earned': total_earned,
            'trophies': trophies,
            'score': round(user.balance + (total_wins * 50), 2),
        })

    rankings.sort(key=lambda item: item['score'], reverse=True)

    top_5 = rankings[:5]
    all_labels = [entry['user'].username for entry in rankings]
    chart_data = {
        'labels': [entry['user'].username for entry in top_5],
        'balances': [entry['user'].balance for entry in top_5],
        'wins': [entry['total_wins'] for entry in top_5],
        'dead': [entry['dead_count'] for entry in top_5],
        'all_labels': all_labels,
        'all_dead': [entry['dead_count'] for entry in rankings],
        'all_challenge': [entry['deaths_challenge'] for entry in rankings],
        'all_blessure': [entry['deaths_blessure'] for entry in rankings],
        'all_sacrifice': [entry['deaths_sacrifice'] for entry in rankings],
        'all_vieillesse': [entry['deaths_vieillesse'] for entry in rankings],
        'all_bet_profit': [entry['bet_profit'] for entry in rankings],
        'all_win_rate': [entry['win_rate'] for entry in rankings],
        'all_races': [entry['total_races'] for entry in rankings],
    }

    def best_by(key, reverse=True):
        valid = [entry for entry in rankings if entry.get(key, 0)]
        if not valid:
            return None
        return (max if reverse else min)(valid, key=lambda entry: entry[key])

    awards = []

    top_score = best_by('score')
    if top_score:
        awards.append({'emoji': '👑', 'title': 'Roi du Derby', 'desc': 'Meilleur score global', 'user': top_score['user'].username, 'value': f"{top_score['score']:.0f} pts", 'color': 'yellow'})

    top_wins = best_by('total_wins')
    if top_wins and top_wins['total_wins'] > 0:
        awards.append({'emoji': '🏆', 'title': 'Champion Absolu', 'desc': 'Le plus de victoires', 'user': top_wins['user'].username, 'value': f"{top_wins['total_wins']} victoire(s)", 'color': 'green'})

    most_deaths = best_by('dead_count')
    if most_deaths and most_deaths['dead_count'] > 0:
        awards.append({'emoji': '🔪', 'title': 'Boucher en Chef', 'desc': 'Le plus de cochons morts', 'user': most_deaths['user'].username, 'value': f"{most_deaths['dead_count']} victime(s)", 'color': 'red'})

    challenge_losses = best_by('deaths_challenge')
    if challenge_losses and challenge_losses['deaths_challenge'] > 0:
        awards.append({'emoji': '💀', 'title': 'Kamikaze Supreme', 'desc': 'Le plus de morts au Challenge', 'user': challenge_losses['user'].username, 'value': f"{challenge_losses['deaths_challenge']} sacrifice(s)", 'color': 'purple'})

    top_staked = best_by('total_staked')
    if top_staked and top_staked['total_staked'] > 0:
        awards.append({'emoji': '🎰', 'title': 'Le Flambeur', 'desc': 'Le plus mise au total', 'user': top_staked['user'].username, 'value': f"{top_staked['total_staked']:.0f} 🪙 misés", 'color': 'amber'})

    top_profit = best_by('bet_profit')
    if top_profit and top_profit['bet_profit'] > 0:
        awards.append({'emoji': '🤑', 'title': 'Le Bookmaker', 'desc': 'Le plus gros profit aux paris', 'user': top_profit['user'].username, 'value': f"+{top_profit['bet_profit']:.0f} 🪙", 'color': 'emerald'})

    worst_profit = best_by('bet_profit', reverse=False)
    if worst_profit and worst_profit['bet_profit'] < 0:
        awards.append({'emoji': '📉', 'title': 'Le Pigeon', 'desc': 'Les pires pertes aux paris', 'user': worst_profit['user'].username, 'value': f"{worst_profit['bet_profit']:.0f} 🪙", 'color': 'red'})

    top_school = best_by('total_school')
    if top_school and top_school['total_school'] > 0:
        awards.append({'emoji': '🎓', 'title': "L'Intellectuel", 'desc': 'Le plus de sessions ecole', 'user': top_school['user'].username, 'value': f"{top_school['total_school']} sessions", 'color': 'blue'})

    top_odds = best_by('best_odds_hit')
    if top_odds and top_odds['best_odds_hit'] >= 2.0:
        awards.append({'emoji': '🎯', 'title': 'Le Sniper', 'desc': 'La meilleure cote touchee', 'user': top_odds['user'].username, 'value': f"x{top_odds['best_odds_hit']:.1f}", 'color': 'cyan'})

    top_races = best_by('total_races')
    if top_races and top_races['total_races'] > 0:
        awards.append({'emoji': '🏃', 'title': 'Le Marathonien', 'desc': 'Le plus de courses disputees', 'user': top_races['user'].username, 'value': f"{top_races['total_races']} courses", 'color': 'indigo'})

    top_sacrifice = best_by('deaths_sacrifice')
    if top_sacrifice and top_sacrifice['deaths_sacrifice'] > 0:
        awards.append({'emoji': '🗡️', 'title': 'Sans Pitie', 'desc': 'Le plus de cochons sacrifies', 'user': top_sacrifice['user'].username, 'value': f"{top_sacrifice['deaths_sacrifice']} sacrifice(s)", 'color': 'rose'})

    top_injury_deaths = best_by('deaths_blessure')
    if top_injury_deaths and top_injury_deaths['deaths_blessure'] > 0:
        awards.append({'emoji': '🩹', 'title': 'Le Negligent', 'desc': 'Le plus de morts par blessure non soignee', 'user': top_injury_deaths['user'].username, 'value': f"{top_injury_deaths['deaths_blessure']} victime(s)", 'color': 'orange'})

    top_food_spend = best_by('total_spent_on_food')
    if top_food_spend and top_food_spend['total_spent_on_food'] > 0:
        awards.append({'emoji': '🌽', 'title': 'Le Nourricier', 'desc': 'Le plus depense en nourriture', 'user': top_food_spend['user'].username, 'value': f"{top_food_spend['total_spent_on_food']:.0f} 🪙", 'color': 'lime'})

    top_legendary_losses = best_by('legendary_dead')
    if top_legendary_losses and top_legendary_losses['legendary_dead'] > 0:
        awards.append({'emoji': '⚱️', 'title': 'Le Sacrilege', 'desc': 'Le plus de legendaires perdus', 'user': top_legendary_losses['user'].username, 'value': f"{top_legendary_losses['legendary_dead']} legendaire(s)", 'color': 'fuchsia'})

    top_xp = best_by('total_xp')
    if top_xp and top_xp['total_xp'] > 0:
        awards.append({'emoji': '⭐', 'title': "L'Eleveur Supreme", 'desc': "Le plus d'XP accumulee", 'user': top_xp['user'].username, 'value': f"{top_xp['total_xp']} XP", 'color': 'violet'})

    top_level = best_by('max_level')
    if top_level and top_level['max_level'] > 1:
        awards.append({'emoji': '🔝', 'title': 'Le Maitre', 'desc': 'Cochon au plus haut niveau', 'user': top_level['user'].username, 'value': f"Niv. {top_level['max_level']}", 'color': 'teal'})

    top_earner = best_by('total_earned')
    if top_earner and top_earner['total_earned'] > 0:
        awards.append({'emoji': '💸', 'title': 'La Machine à 🪙', 'desc': 'Le plus de BitGroins gagnes au total', 'user': top_earner['user'].username, 'value': f"{top_earner['total_earned']:.0f} 🪙", 'color': 'emerald'})

    top_retirements = best_by('deaths_vieillesse')
    if top_retirements and top_retirements['deaths_vieillesse'] > 0:
        awards.append({'emoji': '🧓', 'title': 'Eleveur Patient', 'desc': 'Le plus de cochons morts de vieillesse', 'user': top_retirements['user'].username, 'value': f"{top_retirements['deaths_vieillesse']} retraite(s)", 'color': 'sky'})

    losers = [entry for entry in rankings if entry['total_races'] >= 5]
    if losers:
        loser = min(losers, key=lambda entry: entry['win_rate'])
        if loser['win_rate'] < 30:
            awards.append({'emoji': '🐌', 'title': 'Le Looser Officiel', 'desc': 'Pire taux de victoire (5+ courses)', 'user': loser['user'].username, 'value': f"{loser['win_rate']}%", 'color': 'slate'})

    survivors = [entry for entry in rankings if entry['total_races'] >= 10 and entry['dead_count'] == 0]
    if survivors:
        survivor = max(survivors, key=lambda entry: entry['total_races'])
        awards.append({'emoji': '🛡️', 'title': 'Le Survivant', 'desc': 'Le plus de courses sans aucune perte', 'user': survivor['user'].username, 'value': f"{survivor['total_races']} courses, 0 mort", 'color': 'emerald'})

    return {
        'rankings': rankings,
        'chart_data': chart_data,
        'awards': awards,
    }
