def build_user_trophies(user, metrics, earned_trophies=None):
    trophies = []

    thresholds = [
        (user.balance >= 500, {'n': 'Cresus', 'e': '💰', 'd': 'Plus de 500 🪙 en caisse'}),
        (user.balance >= 1000, {'n': 'Oligarque', 'e': '👑', 'd': 'Plus de 1000 🪙 en caisse'}),
        (metrics['total_wins'] >= 10, {'n': 'Legende', 'e': '🏆', 'd': '10 victoires au total'}),
        (metrics['total_wins'] >= 25, {'n': 'Dynastie', 'e': '🏛️', 'd': '25 victoires au total'}),
        (metrics['dead_count'] >= 5, {'n': 'Boucher', 'e': '🔪', 'd': '5 cochons morts'}),
        (metrics['dead_count'] >= 10, {'n': 'Equarrisseur', 'e': '💀', 'd': '10 cochons morts'}),
        (metrics['total_races'] >= 50, {'n': 'Veteran', 'e': '🎖️', 'd': '50 courses disputees'}),
        (metrics['total_races'] >= 100, {'n': 'Marathonien', 'e': '🏃', 'd': '100 courses disputees'}),
        (metrics['deaths_challenge'] >= 3, {'n': 'Kamikaze', 'e': '💣', 'd': '3 cochons morts au Challenge'}),
        (metrics['deaths_blessure'] >= 3, {'n': 'Negligent', 'e': '🩹', 'd': '3 cochons morts par blessure'}),
        (metrics['deaths_vieillesse'] >= 2, {'n': 'Eleveur Sage', 'e': '🧓', 'd': '2 cochons morts de vieillesse'}),
        (metrics['total_school'] >= 20, {'n': 'Pedagogue', 'e': '📚', 'd': '20 sessions ecole'}),
        (metrics['total_school'] >= 50, {'n': 'Doyen', 'e': '🎓', 'd': '50 sessions ecole'}),
        (metrics['won_bets'] >= 10, {'n': 'Parieur', 'e': '🎟️', 'd': '10 paris gagnes'}),
        (metrics['best_odds_hit'] >= 5.0, {'n': 'Sniper', 'e': '🎯', 'd': 'Pari gagne a x5+'}),
        (metrics['best_odds_hit'] >= 10.0, {'n': 'Fou Furieux', 'e': '🔥', 'd': 'Pari gagne a x10+'}),
        (metrics['bet_profit'] <= -100, {'n': 'Ruine', 'e': '📉', 'd': 'Perdu plus de 100 🪙 en paris'}),
        (metrics['legendary_count'] >= 1, {'n': 'Collectionneur', 'e': '🟡', 'd': 'Posseder un cochon legendaire'}),
        (metrics['deaths_sacrifice'] >= 3, {'n': 'Sans Pitie', 'e': '🗡️', 'd': '3 cochons sacrifies'}),
        (metrics['legendary_dead'] >= 1, {'n': 'Sacrilege', 'e': '⚱️', 'd': 'Avoir perdu un cochon legendaire'}),
        (metrics['total_bets'] > 0 and metrics['won_bets'] == 0, {'n': 'La Poisse', 'e': '🐌', 'd': 'Aucun pari gagne'}),
        (
            metrics['win_rate'] >= 40 and metrics['total_races'] >= 10,
            {'n': 'Stratege', 'e': '🧠', 'd': '40%+ win rate (10+ courses)'},
        ),
    ]

    for should_add, trophy in thresholds:
        if should_add:
            trophies.append(trophy)

    for trophy in earned_trophies or []:
        trophies.append({'n': trophy.label, 'e': trophy.emoji, 'd': trophy.description})

    return trophies


def _best_by(rankings, key, reverse=True):
    valid = [entry for entry in rankings if entry.get(key, 0)]
    if not valid:
        return None
    return (max if reverse else min)(valid, key=lambda entry: entry[key])


def build_awards(rankings):
    awards = []

    definitions = [
        ('score', True, lambda entry: True, {'emoji': '👑', 'title': 'Roi du Derby', 'desc': 'Meilleur score global', 'color': 'yellow'}, lambda entry: f"{entry['score']:.0f} pts"),
        ('total_wins', True, lambda entry: entry['total_wins'] > 0, {'emoji': '🏆', 'title': 'Champion Absolu', 'desc': 'Le plus de victoires', 'color': 'green'}, lambda entry: f"{entry['total_wins']} victoire(s)"),
        ('dead_count', True, lambda entry: entry['dead_count'] > 0, {'emoji': '🔪', 'title': 'Boucher en Chef', 'desc': 'Le plus de cochons morts', 'color': 'red'}, lambda entry: f"{entry['dead_count']} victime(s)"),
        ('deaths_challenge', True, lambda entry: entry['deaths_challenge'] > 0, {'emoji': '💀', 'title': 'Kamikaze Supreme', 'desc': 'Le plus de morts au Challenge', 'color': 'purple'}, lambda entry: f"{entry['deaths_challenge']} sacrifice(s)"),
        ('total_staked', True, lambda entry: entry['total_staked'] > 0, {'emoji': '🎰', 'title': 'Le Flambeur', 'desc': 'Le plus mise au total', 'color': 'amber'}, lambda entry: f"{entry['total_staked']:.0f} 🪙 misés"),
        ('bet_profit', True, lambda entry: entry['bet_profit'] > 0, {'emoji': '🤑', 'title': 'Le Bookmaker', 'desc': 'Le plus gros profit aux paris', 'color': 'emerald'}, lambda entry: f"+{entry['bet_profit']:.0f} 🪙"),
        ('bet_profit', False, lambda entry: entry['bet_profit'] < 0, {'emoji': '📉', 'title': 'Le Pigeon', 'desc': 'Les pires pertes aux paris', 'color': 'red'}, lambda entry: f"{entry['bet_profit']:.0f} 🪙"),
        ('total_school', True, lambda entry: entry['total_school'] > 0, {'emoji': '🎓', 'title': "L'Intellectuel", 'desc': 'Le plus de sessions ecole', 'color': 'blue'}, lambda entry: f"{entry['total_school']} sessions"),
        ('best_odds_hit', True, lambda entry: entry['best_odds_hit'] >= 2.0, {'emoji': '🎯', 'title': 'Le Sniper', 'desc': 'La meilleure cote touchee', 'color': 'cyan'}, lambda entry: f"x{entry['best_odds_hit']:.1f}"),
        ('total_races', True, lambda entry: entry['total_races'] > 0, {'emoji': '🏃', 'title': 'Le Marathonien', 'desc': 'Le plus de courses disputees', 'color': 'indigo'}, lambda entry: f"{entry['total_races']} courses"),
        ('deaths_sacrifice', True, lambda entry: entry['deaths_sacrifice'] > 0, {'emoji': '🗡️', 'title': 'Sans Pitie', 'desc': 'Le plus de cochons sacrifies', 'color': 'rose'}, lambda entry: f"{entry['deaths_sacrifice']} sacrifice(s)"),
        ('deaths_blessure', True, lambda entry: entry['deaths_blessure'] > 0, {'emoji': '🩹', 'title': 'Le Negligent', 'desc': 'Le plus de morts par blessure non soignee', 'color': 'orange'}, lambda entry: f"{entry['deaths_blessure']} victime(s)"),
        ('total_spent_on_food', True, lambda entry: entry['total_spent_on_food'] > 0, {'emoji': '🌽', 'title': 'Le Nourricier', 'desc': 'Le plus depense en nourriture', 'color': 'lime'}, lambda entry: f"{entry['total_spent_on_food']:.0f} 🪙"),
        ('legendary_dead', True, lambda entry: entry['legendary_dead'] > 0, {'emoji': '⚱️', 'title': 'Le Sacrilege', 'desc': 'Le plus de legendaires perdus', 'color': 'fuchsia'}, lambda entry: f"{entry['legendary_dead']} legendaire(s)"),
        ('total_xp', True, lambda entry: entry['total_xp'] > 0, {'emoji': '⭐', 'title': "L'Eleveur Supreme", 'desc': "Le plus d'XP accumulee", 'color': 'violet'}, lambda entry: f"{entry['total_xp']} XP"),
        ('max_level', True, lambda entry: entry['max_level'] > 1, {'emoji': '🔝', 'title': 'Le Maitre', 'desc': 'Cochon au plus haut niveau', 'color': 'teal'}, lambda entry: f"Niv. {entry['max_level']}"),
        ('total_earned', True, lambda entry: entry['total_earned'] > 0, {'emoji': '💸', 'title': 'La Machine à 🪙', 'desc': 'Le plus de BitGroins gagnes au total', 'color': 'emerald'}, lambda entry: f"{entry['total_earned']:.0f} 🪙"),
        ('deaths_vieillesse', True, lambda entry: entry['deaths_vieillesse'] > 0, {'emoji': '🧓', 'title': 'Eleveur Patient', 'desc': 'Le plus de cochons morts de vieillesse', 'color': 'sky'}, lambda entry: f"{entry['deaths_vieillesse']} retraite(s)"),
    ]

    for key, reverse, validator, meta, value_builder in definitions:
        winner = _best_by(rankings, key, reverse=reverse)
        if winner and validator(winner):
            awards.append({
                **meta,
                'user': winner['user'].username,
                'value': value_builder(winner),
            })

    losers = [entry for entry in rankings if entry['total_races'] >= 5]
    if losers:
        loser = min(losers, key=lambda entry: entry['win_rate'])
        if loser['win_rate'] < 30:
            awards.append({
                'emoji': '🐌',
                'title': 'Le Looser Officiel',
                'desc': 'Pire taux de victoire (5+ courses)',
                'user': loser['user'].username,
                'value': f"{loser['win_rate']}%",
                'color': 'slate',
            })

    survivors = [entry for entry in rankings if entry['total_races'] >= 10 and entry['dead_count'] == 0]
    if survivors:
        survivor = max(survivors, key=lambda entry: entry['total_races'])
        awards.append({
            'emoji': '🛡️',
            'title': 'Le Survivant',
            'desc': 'Le plus de courses sans aucune perte',
            'user': survivor['user'].username,
            'value': f"{survivor['total_races']} courses, 0 mort",
            'color': 'emerald',
        })

    return awards
