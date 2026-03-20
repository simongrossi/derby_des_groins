from flask import Blueprint, render_template, redirect, url_for, session
from datetime import datetime

from extensions import db
from models import User, Pig, Race, Participant, Bet, BalanceTransaction, CoursePlan
from data import BET_TYPES, WEEKLY_BACON_TICKETS
from helpers import (
    ensure_next_race, get_user_active_pigs, update_pig_state, calculate_pig_power,
    get_weight_profile, get_pig_dashboard_status, build_course_schedule,
    get_user_weekly_bet_count, get_course_theme, get_prix_moyen_groin,
    is_market_open, get_next_market_time, get_race_history_entries,
)

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
            pigs = Pig.query.filter_by(user_id=user.id, is_alive=True).all()
            for pig in pigs:
                update_pig_state(pig)
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
            'text': f"{latest_big_win.reason_label}: {latest_big_win.amount:.0f} BG.",
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
        total_wins = db.session.query(db.func.sum(Pig.races_won)).filter(Pig.user_id == u.id).scalar() or 0
        total_races = db.session.query(db.func.sum(Pig.races_entered)).filter(Pig.user_id == u.id).scalar() or 0
        dead_pigs_count = Pig.query.filter_by(user_id=u.id, is_alive=False).count()
        win_rate = (total_wins / total_races * 100) if total_races > 0 else 0

        trophies = []
        if u.balance >= 500: trophies.append({'n': 'Crésus', 'e': '💰', 'd': 'Avoir plus de 500 BG'})
        if total_wins >= 10: trophies.append({'n': 'Légende', 'e': '🏆', 'd': '10 victoires au total'})
        if dead_pigs_count >= 5: trophies.append({'n': 'Boucher', 'e': '🔪', 'd': '5 cochons à l\'abattoir'})
        if total_races >= 50: trophies.append({'n': 'Vétéran', 'e': '🎖️', 'd': '50 courses disputées'})

        rankings.append({
            'user': u,
            'total_wins': total_wins,
            'total_races': total_races,
            'win_rate': round(win_rate, 1),
            'dead_count': dead_pigs_count,
            'trophies': trophies,
            'score': round(u.balance + (total_wins * 50), 2)
        })

    rankings.sort(key=lambda x: x['score'], reverse=True)

    top_5 = rankings[:5]
    chart_data = {
        'labels': [r['user'].username for r in top_5],
        'balances': [r['user'].balance for r in top_5],
        'wins': [r['total_wins'] for r in top_5]
    }

    return render_template('classement.html', user=user, rankings=rankings, chart_data=chart_data)


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
