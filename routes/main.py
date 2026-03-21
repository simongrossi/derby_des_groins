from flask import Blueprint, render_template, redirect, url_for, session, flash
from sqlalchemy import func
from datetime import datetime

from extensions import db
from models import User, Pig, Race, Participant, Bet, BalanceTransaction, CoursePlan, Trophy
from data import BET_TYPES, WEEKLY_BACON_TICKETS, DAILY_LOGIN_REWARD
from helpers import ensure_next_race, get_user_active_pigs, get_race_history_entries
from services.market_service import get_prix_moyen_groin, is_market_open, get_next_market_time
from services.pig_service import calculate_pig_power, get_weight_profile
from services.race_service import get_pig_dashboard_status, build_course_schedule, get_user_weekly_bet_count, get_course_theme

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    ensure_next_race()
    next_race = Race.query.filter(Race.status == 'open').order_by(Race.scheduled_at).first()
    recent_races = Race.query.filter_by(status='finished').order_by(Race.finished_at.desc()).limit(5).all()

    user = None
    user_bets = []
    pigs = []
    pigs_data = []
    week_slots = []
    featured_pig = None
    featured_pig_status = None
    headline_status = None
    bacon_tickets_remaining = WEEKLY_BACON_TICKETS
    latest_race = recent_races[0] if recent_races else None
    latest_race_participants = []
    news_items = []
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            # --- Prime de pointage journalière ---
            reward = user.claim_daily_reward()
            if reward > 0:
                db.session.commit()
                flash(f"🎁 Prime de pointage : Vous avez reçu {reward:.0f} 🪙 BitGroins pour votre première connexion de la journée !", "success")

            pigs = Pig.query.filter_by(user_id=user.id, is_alive=True).all()
            for pig in pigs:
                pig.update_vitals()
            pigs_data = [{
                'pig': pig,
                'power': round(calculate_pig_power(pig), 1),
                'weight_profile': get_weight_profile(pig),
                'dashboard': get_pig_dashboard_status(pig),
            } for pig in pigs]
            week_slots = build_course_schedule(user, pigs, days=7)
            weekly_bet_count = get_user_weekly_bet_count(user, datetime.now())
            bacon_tickets_remaining = max(0, WEEKLY_BACON_TICKETS - weekly_bet_count)
            if next_race:
                user_bets = Bet.query.filter_by(user_id=user.id, race_id=next_race.id).all()

    participants = []
    if next_race:
        participants = Participant.query.filter_by(race_id=next_race.id).order_by(Participant.odds).all()
    participants_by_pig_id = {participant.pig_id: participant for participant in participants if participant.pig_id}

    if latest_race:
        latest_race_participants = Participant.query.filter_by(race_id=latest_race.id).order_by(Participant.finish_position).all()

    if pigs_data:
        featured_candidates = [entry for entry in pigs_data if entry['pig'].id in participants_by_pig_id]
        featured_pig = (featured_candidates[0] if featured_candidates else pigs_data[0])
        featured_pig_status = featured_pig['dashboard']
        featured_pig_obj = featured_pig['pig']
        participant = participants_by_pig_id.get(featured_pig_obj.id)
        if participant:
            headline_status = {
                'participates': True,
                'label': f"{featured_pig_obj.emoji} {featured_pig_obj.name} y participe !",
                'subtext': f"Cote actuelle x{participant.odds:.1f}. {featured_pig_status['rest_label']}.",
                'tone': 'success',
            }
        else:
            next_plan = (
                CoursePlan.query
                .filter(CoursePlan.user_id == user.id, CoursePlan.pig_id == featured_pig_obj.id, CoursePlan.scheduled_at >= datetime.now())
                .order_by(CoursePlan.scheduled_at.asc())
                .first()
            )
            if next_plan:
                plan_label = next_plan.scheduled_at.strftime('%d/%m %H:%M')
                headline_status = {
                    'participates': False,
                    'label': f"📅 {featured_pig_obj.name} vise le {plan_label}",
                    'subtext': featured_pig_status['rest_note'],
                    'tone': 'planned',
                }
            else:
                headline_status = {
                    'participates': False,
                    'label': f"💤 {featured_pig_obj.name} se repose",
                    'subtext': featured_pig_status['rest_note'],
                    'tone': 'rest',
                }

    injured_pig = Pig.query.filter_by(is_alive=True, is_injured=True).order_by(Pig.vet_deadline.asc(), Pig.id.asc()).first()
    if injured_pig:
        owner_name = injured_pig.owner.username if injured_pig.owner else "Un eleveur"
        news_items.append({
            'emoji': '🏥',
            'title': f"{injured_pig.name} s'est blesse",
            'text': f"{owner_name} doit l'envoyer au veto avant la deadline.",
        })

    latest_big_win = (
        BalanceTransaction.query
        .filter(BalanceTransaction.reason_code.in_(['bet_payout', 'challenge_payout']))
        .order_by(BalanceTransaction.created_at.desc(), BalanceTransaction.id.desc())
        .first()
    )
    if latest_big_win and latest_big_win.user:
        news_items.append({
            'emoji': '🎟️',
            'title': f"{latest_big_win.user.username} a touche gros",
            'text': f"{latest_big_win.reason_label}: {latest_big_win.amount:.0f} 🪙.",
        })

    if latest_race and latest_race_participants:
        winner = latest_race_participants[0]
        winner_owner = winner.owner_name or 'Ordinateur'
        news_items.append({
            'emoji': '🏆',
            'title': f"{winner.name} a gagne la derniere course",
            'text': f"Victoire signee {winner_owner} sur la course #{latest_race.id}.",
        })

    week_race_cards = week_slots[:5] if week_slots else []
    next_race_theme = get_course_theme(next_race.scheduled_at) if next_race else None

    prix_groin = get_prix_moyen_groin()

    return render_template('index.html',
        user=user, pigs=pigs, next_race=next_race,
        participants=participants, recent_races=recent_races,
        user_bets=user_bets, now=datetime.now(),
        bet_types=BET_TYPES,
        prix_groin=prix_groin,
        market_open=is_market_open(),
        next_market=get_next_market_time(),
        featured_pig=featured_pig,
        featured_pig_status=featured_pig_status,
        headline_status=headline_status,
        bacon_tickets_remaining=bacon_tickets_remaining,
        weekly_bacon_tickets=WEEKLY_BACON_TICKETS,
        week_race_cards=week_race_cards,
        next_race_theme=next_race_theme,
        latest_race=latest_race,
        latest_race_participants=latest_race_participants,
        news_items=news_items[:3],
    )


@main_bp.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    bets = Bet.query.filter_by(user_id=user.id).order_by(Bet.placed_at.desc()).all()
    transactions = BalanceTransaction.query.filter_by(user_id=user.id).order_by(BalanceTransaction.created_at.desc(), BalanceTransaction.id.desc()).all()
    global_transactions = []
    if user.is_admin:
        global_transactions = BalanceTransaction.query.order_by(BalanceTransaction.created_at.desc(), BalanceTransaction.id.desc()).all()

    race_history = get_race_history_entries()

    won_bets = [bet for bet in bets if bet.status == 'won']
    lost_bets = [bet for bet in bets if bet.status == 'lost']
    settled_bets = won_bets + lost_bets
    credited_amount = round(sum(tx.amount for tx in transactions if tx.amount > 0 and tx.reason_code != 'snapshot'), 2)
    debited_amount = round(sum(abs(tx.amount) for tx in transactions if tx.amount < 0 and tx.reason_code != 'snapshot'), 2)

    return render_template(
        'history.html',
        user=user,
        bets=bets,
        won_bets=won_bets,
        lost_bets=lost_bets,
        settled_bets=settled_bets,
        transactions=transactions,
        global_transactions=global_transactions,
        race_history=race_history,
        bet_types=BET_TYPES,
        credited_amount=credited_amount,
        debited_amount=debited_amount,
    )


@main_bp.route('/classement')
def classement():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])

    all_users = User.query.all()
    rankings = []

    for u in all_users:
        # --- Stats courses ---
        total_wins = db.session.query(db.func.sum(Pig.races_won)).filter(Pig.user_id == u.id).scalar() or 0
        total_races = db.session.query(db.func.sum(Pig.races_entered)).filter(Pig.user_id == u.id).scalar() or 0
        win_rate = (total_wins / total_races * 100) if total_races > 0 else 0

        # --- Stats morts par cause ---
        dead_pigs = Pig.query.filter_by(user_id=u.id, is_alive=False).all()
        dead_pigs_count = len([p for p in dead_pigs if p.death_cause != 'vendu'])
        deaths_by_cause = {}
        for p in dead_pigs:
            if p.death_cause and p.death_cause != 'vendu':
                deaths_by_cause[p.death_cause] = deaths_by_cause.get(p.death_cause, 0) + 1
        deaths_challenge = deaths_by_cause.get('challenge', 0)
        deaths_blessure = deaths_by_cause.get('blessure', 0)
        deaths_sacrifice = deaths_by_cause.get('sacrifice_volontaire', 0) + deaths_by_cause.get('sacrifice', 0)
        deaths_vieillesse = deaths_by_cause.get('vieillesse', 0)
        legendary_dead = sum(1 for p in dead_pigs if p.death_cause != 'vendu' and (p.races_won or 0) >= 3)

        # --- Stats paris ---
        user_bets = Bet.query.filter_by(user_id=u.id).all()
        total_bets = len(user_bets)
        won_bets = [b for b in user_bets if b.status == 'won']
        lost_bets = [b for b in user_bets if b.status == 'lost']
        settled_bets = won_bets + lost_bets
        total_staked = round(sum(b.amount or 0 for b in user_bets), 2)
        total_winnings = round(sum(b.winnings or 0 for b in won_bets), 2)
        bet_profit = round(total_winnings - sum(b.amount or 0 for b in settled_bets), 2)
        bet_win_rate = round((len(won_bets) / len(settled_bets)) * 100, 1) if settled_bets else 0.0
        best_odds_hit = max((b.odds_at_bet for b in won_bets), default=0.0)

        # --- Stats elevage ---
        all_pigs = Pig.query.filter_by(user_id=u.id).all()
        active_pigs = [p for p in all_pigs if p.is_alive]
        best_pig = max(all_pigs, key=lambda p: (p.races_won or 0, p.level or 0), default=None)
        max_level = max((p.level or 1 for p in all_pigs), default=1)
        total_school = sum(p.school_sessions_completed or 0 for p in all_pigs)
        total_xp = sum(p.xp or 0 for p in all_pigs)
        legendary_count = sum(1 for p in all_pigs if p.rarity == 'legendaire')

        # --- Stats depenses (BalanceTransaction) ---
        total_spent_on_food = db.session.query(
            func.coalesce(func.sum(func.abs(BalanceTransaction.amount)), 0.0)
        ).filter(
            BalanceTransaction.user_id == u.id,
            BalanceTransaction.reason_code == 'feed_purchase'
        ).scalar() or 0.0
        total_earned = db.session.query(
            func.coalesce(func.sum(BalanceTransaction.amount), 0.0)
        ).filter(
            BalanceTransaction.user_id == u.id,
            BalanceTransaction.amount > 0,
            BalanceTransaction.reason_code != 'snapshot'
        ).scalar() or 0.0

        # --- Trophees ---
        trophies = []
        if u.balance >= 500: trophies.append({'n': 'Cresus', 'e': '💰', 'd': 'Plus de 500 🪙 en caisse'})
        if u.balance >= 1000: trophies.append({'n': 'Oligarque', 'e': '👑', 'd': 'Plus de 1000 🪙 en caisse'})
        if total_wins >= 10: trophies.append({'n': 'Legende', 'e': '🏆', 'd': '10 victoires au total'})
        if total_wins >= 25: trophies.append({'n': 'Dynastie', 'e': '🏛️', 'd': '25 victoires au total'})
        if dead_pigs_count >= 5: trophies.append({'n': 'Boucher', 'e': '🔪', 'd': '5 cochons morts'})
        if dead_pigs_count >= 10: trophies.append({'n': 'Equarrisseur', 'e': '💀', 'd': '10 cochons morts'})
        if total_races >= 50: trophies.append({'n': 'Veteran', 'e': '🎖️', 'd': '50 courses disputees'})
        if total_races >= 100: trophies.append({'n': 'Marathonien', 'e': '🏃', 'd': '100 courses disputees'})
        if deaths_challenge >= 3: trophies.append({'n': 'Kamikaze', 'e': '💣', 'd': '3 cochons morts au Challenge'})
        if deaths_blessure >= 3: trophies.append({'n': 'Negligent', 'e': '🩹', 'd': '3 cochons morts par blessure'})
        if deaths_vieillesse >= 2: trophies.append({'n': 'Eleveur Sage', 'e': '🧓', 'd': '2 cochons morts de vieillesse'})
        if total_school >= 20: trophies.append({'n': 'Pedagogue', 'e': '📚', 'd': '20 sessions ecole'})
        if total_school >= 50: trophies.append({'n': 'Doyen', 'e': '🎓', 'd': '50 sessions ecole'})
        if len(won_bets) >= 10: trophies.append({'n': 'Parieur', 'e': '🎟️', 'd': '10 paris gagnes'})
        if best_odds_hit >= 5.0: trophies.append({'n': 'Sniper', 'e': '🎯', 'd': 'Pari gagne a x5+'})
        if best_odds_hit >= 10.0: trophies.append({'n': 'Fou Furieux', 'e': '🔥', 'd': 'Pari gagne a x10+'})
        if bet_profit <= -100: trophies.append({'n': 'Ruine', 'e': '📉', 'd': 'Perdu plus de 100 🪙 en paris'})
        if legendary_count >= 1: trophies.append({'n': 'Collectionneur', 'e': '🟡', 'd': 'Posseder un cochon legendaire'})
        if deaths_sacrifice >= 3: trophies.append({'n': 'Sans Pitie', 'e': '🗡️', 'd': '3 cochons sacrifies'})
        if legendary_dead >= 1: trophies.append({'n': 'Sacrilege', 'e': '⚱️', 'd': 'Avoir perdu un cochon legendaire'})
        if total_bets > 0 and len(won_bets) == 0: trophies.append({'n': 'La Poisse', 'e': '🐌', 'd': 'Aucun pari gagne'})
        if win_rate >= 40 and total_races >= 10: trophies.append({'n': 'Stratege', 'e': '🧠', 'd': '40%+ win rate (10+ courses)'})
        memorial_trophies = Trophy.query.filter_by(user_id=u.id).order_by(Trophy.earned_at.asc()).all()
        for trophy in memorial_trophies:
            trophies.append({'n': trophy.label, 'e': trophy.emoji, 'd': trophy.description})

        rankings.append({
            'user': u,
            # Courses
            'total_wins': total_wins,
            'total_races': total_races,
            'win_rate': round(win_rate, 1),
            # Morts
            'dead_count': dead_pigs_count,
            'deaths_challenge': deaths_challenge,
            'deaths_blessure': deaths_blessure,
            'deaths_sacrifice': deaths_sacrifice,
            'deaths_vieillesse': deaths_vieillesse,
            'legendary_dead': legendary_dead,
            # Paris
            'total_bets': total_bets,
            'won_bets': len(won_bets),
            'lost_bets': len(lost_bets),
            'total_staked': total_staked,
            'total_winnings': total_winnings,
            'bet_profit': bet_profit,
            'bet_win_rate': bet_win_rate,
            'best_odds_hit': round(best_odds_hit, 1),
            # Elevage
            'best_pig': best_pig,
            'max_level': max_level,
            'total_school': total_school,
            'total_xp': total_xp,
            'legendary_count': legendary_count,
            'active_pigs_count': len(active_pigs),
            'total_spent_on_food': round(float(total_spent_on_food), 2),
            'total_earned': round(float(total_earned), 2),
            # Meta
            'trophies': trophies,
            'score': round(u.balance + (total_wins * 50), 2),
        })

    rankings.sort(key=lambda x: x['score'], reverse=True)

    # --- Charts top 5 ---
    top_5 = rankings[:5]
    all_labels = [r['user'].username for r in rankings]
    chart_data = {
        'labels': [r['user'].username for r in top_5],
        'balances': [r['user'].balance for r in top_5],
        'wins': [r['total_wins'] for r in top_5],
        'dead': [r['dead_count'] for r in top_5],
        'all_labels': all_labels,
        'all_dead': [r['dead_count'] for r in rankings],
        'all_challenge': [r['deaths_challenge'] for r in rankings],
        'all_blessure': [r['deaths_blessure'] for r in rankings],
        'all_sacrifice': [r['deaths_sacrifice'] for r in rankings],
        'all_vieillesse': [r['deaths_vieillesse'] for r in rankings],
        'all_bet_profit': [r['bet_profit'] for r in rankings],
        'all_win_rate': [r['win_rate'] for r in rankings],
        'all_races': [r['total_races'] for r in rankings],
    }

    # --- Awards speciaux ---
    def best_by(key, reverse=True):
        valid = [r for r in rankings if r.get(key, 0)]
        if not valid:
            return None
        return (max if reverse else min)(valid, key=lambda r: r[key])

    awards = []

    a = best_by('score')
    if a: awards.append({'emoji': '👑', 'title': 'Roi du Derby', 'desc': 'Meilleur score global', 'user': a['user'].username, 'value': f"{a['score']:.0f} pts", 'color': 'yellow'})

    a = best_by('total_wins')
    if a and a['total_wins'] > 0: awards.append({'emoji': '🏆', 'title': 'Champion Absolu', 'desc': 'Le plus de victoires', 'user': a['user'].username, 'value': f"{a['total_wins']} victoire(s)", 'color': 'green'})

    a = best_by('dead_count')
    if a and a['dead_count'] > 0: awards.append({'emoji': '🔪', 'title': 'Boucher en Chef', 'desc': 'Le plus de cochons morts', 'user': a['user'].username, 'value': f"{a['dead_count']} victime(s)", 'color': 'red'})

    a = best_by('deaths_challenge')
    if a and a['deaths_challenge'] > 0: awards.append({'emoji': '💀', 'title': 'Kamikaze Supreme', 'desc': 'Le plus de morts au Challenge', 'user': a['user'].username, 'value': f"{a['deaths_challenge']} sacrifice(s)", 'color': 'purple'})

    a = best_by('total_staked')
    if a and a['total_staked'] > 0: awards.append({'emoji': '🎰', 'title': 'Le Flambeur', 'desc': 'Le plus mise au total', 'user': a['user'].username, 'value': f"{a['total_staked']:.0f} 🪙 misés", 'color': 'amber'})

    a = best_by('bet_profit')
    if a and a['bet_profit'] > 0: awards.append({'emoji': '🤑', 'title': 'Le Bookmaker', 'desc': 'Le plus gros profit aux paris', 'user': a['user'].username, 'value': f"+{a['bet_profit']:.0f} 🪙", 'color': 'emerald'})

    a = best_by('bet_profit', reverse=False)
    if a and a['bet_profit'] < 0: awards.append({'emoji': '📉', 'title': 'Le Pigeon', 'desc': 'Les pires pertes aux paris', 'user': a['user'].username, 'value': f"{a['bet_profit']:.0f} 🪙", 'color': 'red'})

    a = best_by('total_school')
    if a and a['total_school'] > 0: awards.append({'emoji': '🎓', 'title': "L'Intellectuel", 'desc': 'Le plus de sessions ecole', 'user': a['user'].username, 'value': f"{a['total_school']} sessions", 'color': 'blue'})

    a = best_by('best_odds_hit')
    if a and a['best_odds_hit'] >= 2.0: awards.append({'emoji': '🎯', 'title': 'Le Sniper', 'desc': 'La meilleure cote touchee', 'user': a['user'].username, 'value': f"x{a['best_odds_hit']:.1f}", 'color': 'cyan'})

    a = best_by('total_races')
    if a and a['total_races'] > 0: awards.append({'emoji': '🏃', 'title': 'Le Marathonien', 'desc': 'Le plus de courses disputees', 'user': a['user'].username, 'value': f"{a['total_races']} courses", 'color': 'indigo'})

    a = best_by('deaths_sacrifice')
    if a and a['deaths_sacrifice'] > 0: awards.append({'emoji': '🗡️', 'title': 'Sans Pitie', 'desc': 'Le plus de cochons sacrifies', 'user': a['user'].username, 'value': f"{a['deaths_sacrifice']} sacrifice(s)", 'color': 'rose'})

    a = best_by('deaths_blessure')
    if a and a['deaths_blessure'] > 0: awards.append({'emoji': '🩹', 'title': 'Le Negligent', 'desc': 'Le plus de morts par blessure non soignee', 'user': a['user'].username, 'value': f"{a['deaths_blessure']} victime(s)", 'color': 'orange'})

    a = best_by('total_spent_on_food')
    if a and a['total_spent_on_food'] > 0: awards.append({'emoji': '🌽', 'title': 'Le Nourricier', 'desc': 'Le plus depense en nourriture', 'user': a['user'].username, 'value': f"{a['total_spent_on_food']:.0f} 🪙", 'color': 'lime'})

    a = best_by('legendary_dead')
    if a and a['legendary_dead'] > 0: awards.append({'emoji': '⚱️', 'title': 'Le Sacrilege', 'desc': 'Le plus de legendaires perdus', 'user': a['user'].username, 'value': f"{a['legendary_dead']} legendaire(s)", 'color': 'fuchsia'})

    a = best_by('total_xp')
    if a and a['total_xp'] > 0: awards.append({'emoji': '⭐', 'title': "L'Eleveur Supreme", 'desc': 'Le plus d\'XP accumulee', 'user': a['user'].username, 'value': f"{a['total_xp']} XP", 'color': 'violet'})

    a = best_by('max_level')
    if a and a['max_level'] > 1: awards.append({'emoji': '🔝', 'title': 'Le Maitre', 'desc': 'Cochon au plus haut niveau', 'user': a['user'].username, 'value': f"Niv. {a['max_level']}", 'color': 'teal'})

    a = best_by('total_earned')
    if a and a['total_earned'] > 0: awards.append({'emoji': '💸', 'title': 'La Machine à 🪙', 'desc': 'Le plus de BitGroins gagnes au total', 'user': a['user'].username, 'value': f"{a['total_earned']:.0f} 🪙", 'color': 'emerald'})

    a = best_by('deaths_vieillesse')
    if a and a['deaths_vieillesse'] > 0: awards.append({'emoji': '🧓', 'title': 'Eleveur Patient', 'desc': 'Le plus de cochons morts de vieillesse', 'user': a['user'].username, 'value': f"{a['deaths_vieillesse']} retraite(s)", 'color': 'sky'})

    # Le Looser: worst win rate with at least some races
    losers = [r for r in rankings if r['total_races'] >= 5]
    if losers:
        loser = min(losers, key=lambda r: r['win_rate'])
        if loser['win_rate'] < 30:
            awards.append({'emoji': '🐌', 'title': 'Le Looser Officiel', 'desc': 'Pire taux de victoire (5+ courses)', 'user': loser['user'].username, 'value': f"{loser['win_rate']}%", 'color': 'slate'})

    # Le Survivant: most races with no deaths
    survivors = [r for r in rankings if r['total_races'] >= 10 and r['dead_count'] == 0]
    if survivors:
        survivor = max(survivors, key=lambda r: r['total_races'])
        awards.append({'emoji': '🛡️', 'title': 'Le Survivant', 'desc': 'Le plus de courses sans aucune perte', 'user': survivor['user'].username, 'value': f"{survivor['total_races']} courses, 0 mort", 'color': 'emerald'})

    return render_template('classement.html', user=user, rankings=rankings, chart_data=chart_data, awards=awards, active_page='classement')


@main_bp.route('/legendes-pop')
def legendes_pop():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])

    pop_pigs = [
        {"name": "Porky Pig", "emoji": "🎩", "desc": "Le pionnier. A transformé un bégaiement en une carrière légendaire.", "category": "Stars du Marché"},
        {"name": "Miss Piggy", "emoji": "🎀", "desc": "Influenceuse avant Instagram. Mélange unique de glamour et de violence passive-agressive.", "category": "Stars du Marché"},
        {"name": "Peppa Pig", "emoji": "☔", "desc": "CEO d\u2019un empire mondial basé sur des grognements et des flaques de boue.", "category": "Stars du Marché"},
        {"name": "Porcinet", "emoji": "🧣", "desc": "12 kg de stress, mais validé émotionnellement par toute une génération.", "category": "Stars du Marché"},
        {"name": "Napoléon", "emoji": "👑", "desc": "Commence comme cochon, finit comme manager toxique (La Ferme des Animaux).", "category": "Niveau Dangereux"},
        {"name": "Porco Rosso", "emoji": "🛩️", "desc": "Pilote, philosophe, cochon. Trois problèmes complexes en un seul groin.", "category": "Niveau Dangereux"},
        {"name": "Cochons (Pink Floyd)", "emoji": "🎸", "desc": "Métaphore officielle des élites. Entrée validée par guitare électrique.", "category": "Niveau Dangereux"},
        {"name": "Tête de cochon", "emoji": "💀", "desc": "Quand un cochon mort devient plus charismatique que les humains (Sa Majesté des Mouches).", "category": "Niveau Dangereux"},
        {"name": "Cochon Minecraft", "emoji": "🧊", "desc": "Moyen de transport discutable. Existe principalement pour être transformé en côtelette.", "category": "Quotidien Suspect"},
        {"name": "Cochons Verts", "emoji": "🤢", "desc": "Ingénieurs en structures inefficaces (Angry Birds).", "category": "Quotidien Suspect"},
        {"name": "Hog Rider", "emoji": "🔨", "desc": "Un homme qui crie sur un cochon. Personne ne remet ça en question.", "category": "Quotidien Suspect"},
        {"name": "Hamm / Bayonne", "emoji": "🪙", "desc": "Tirelire cynique de Toy Story. Le seul qui comprend réellement l\u2019économie.", "category": "Quotidien Suspect"},
        {"name": "Nif-Nif, Naf-Naf & Nouf-Nouf", "emoji": "🏠", "desc": "Trois approches du BTP. Une seule résiste réellement au souffle du loup.", "category": "Patrimoine"},
        {"name": "Babe", "emoji": "🐑", "desc": "Le seul cochon avec un plan de carrière et une reconversion réussie.", "category": "Patrimoine"},
        {"name": "Wilbur", "emoji": "🕸️", "desc": "Sauvé par une araignée (Charlotte) meilleure en communication de crise que lui.", "category": "Patrimoine"},
        {"name": "Peter Pig", "emoji": "⚓", "desc": "Preuve que même chez Disney, certains cochons n\u2019ont pas percé.", "category": "Patrimoine"},
        {"name": "Petunia Pig", "emoji": "👒", "desc": "Love interest officielle. Un potentiel inexploité par les studios.", "category": "Secondaires"},
        {"name": "Piggy (Merrie Melodies)", "emoji": "🤡", "desc": "Version bêta de Porky Pig. A servi de crash-test pour l\u2019humour.", "category": "Secondaires"},
        {"name": "Arnold Ziffel", "emoji": "📺", "desc": "Cochon traité comme un humain complet. Personne ne pose de questions.", "category": "Secondaires"},
        {"name": "Pumbaa", "emoji": "🐗", "desc": "Techniquement un phacochère. Accepté dans la base pour raisons administratives.", "category": "Secondaires"},
    ]
    return render_template('legendes_pop.html', user=user, pop_pigs=pop_pigs)
