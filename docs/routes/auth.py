from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import random
import math

from extensions import db
from models import User, Pig, Bet, Auction, Trophy
from data import PIG_ORIGINS, BET_TYPES, RARITIES
from helpers import get_market_unlock_progress, get_market_lock_reason
from services.finance_service import record_balance_transaction
from services.pig_service import apply_origin_bonus, generate_weight_kg_for_profile, get_active_listing_count, build_unique_pig_name

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            return render_template('auth.html', error="Remplis tous les champs !", mode='register')
        if len(username) < 3:
            return render_template('auth.html', error="Pseudo trop court (min 3 caractères)", mode='register')
        if User.query.filter_by(username=username).first():
            return render_template('auth.html', error="Ce pseudo est déjà pris !", mode='register')
        user = User(username=username, password_hash=generate_password_hash(password), balance=100.0)
        db.session.add(user)
        db.session.flush()
        record_balance_transaction(
            user_id=user.id,
            amount=100.0,
            balance_before=0.0,
            balance_after=100.0,
            reason_code='welcome_bonus',
            reason_label="Bonus d'inscription",
            details="Capital de depart offert a la creation du compte.",
            reference_type='user',
            reference_id=user.id,
        )
        origin = random.choice(PIG_ORIGINS)
        pig = Pig(user_id=user.id, name=build_unique_pig_name(f"Cochon de {username}", fallback_prefix='Cochon'), emoji='🐷',
                  origin_country=origin['country'], origin_flag=origin['flag'])
        apply_origin_bonus(pig, origin)
        pig.weight_kg = generate_weight_kg_for_profile(pig)
        db.session.add(pig)
        db.session.commit()
        session['user_id'] = user.id
        return redirect(url_for('pig.mon_cochon'))
    return render_template('auth.html', mode='register')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            return render_template('auth.html', error="Identifiants incorrects !", mode='login')
        session['user_id'] = user.id
        next_url = request.args.get('next') or request.form.get('next')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect(url_for('main.index'))
    return render_template('auth.html', mode='login')


@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('main.index'))


@auth_bp.route('/profil', methods=['GET', 'POST'])
def profil():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        current_password = request.form.get('current_password', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not current_password or not new_password or not confirm_password:
            flash("Remplis tous les champs pour changer ton mot de passe.", "warning")
        elif not check_password_hash(user.password_hash, current_password):
            flash("Ton mot de passe actuel est incorrect.", "error")
        elif len(new_password) < 6:
            flash("Ton nouveau mot de passe doit faire au moins 6 caractères.", "warning")
        elif current_password == new_password:
            flash("Choisis un mot de passe différent de l'actuel.", "warning")
        elif new_password != confirm_password:
            flash("La confirmation du nouveau mot de passe ne correspond pas.", "error")
        else:
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash("Mot de passe mis à jour avec succès.", "success")
        return redirect(url_for('auth.profil'))

    pigs = Pig.query.filter_by(user_id=user.id).order_by(Pig.created_at.desc()).all()
    bets = Bet.query.filter_by(user_id=user.id).order_by(Bet.placed_at.desc()).all()
    active_listings = Auction.query.filter_by(seller_id=user.id, status='active').all()
    active_listing_ids = {listing.source_pig_id for listing in active_listings if listing.source_pig_id}

    active_pigs = [pig for pig in pigs if pig.is_alive]
    retired_pigs = [pig for pig in pigs if not pig.is_alive and pig.id not in active_listing_ids]
    total_races = sum((pig.races_entered or 0) for pig in pigs)
    total_wins = sum((pig.races_won or 0) for pig in pigs)
    total_school_sessions = sum((pig.school_sessions_completed or 0) for pig in pigs)
    legendary_pigs = sum(1 for pig in pigs if pig.rarity == 'legendaire')
    best_pig = max(pigs, key=lambda pig: ((pig.races_won or 0), (pig.level or 0), (pig.xp or 0)), default=None)

    won_bets = [bet for bet in bets if bet.status == 'won']
    lost_bets = [bet for bet in bets if bet.status == 'lost']
    pending_bets = [bet for bet in bets if bet.status == 'pending']
    settled_bets = won_bets + lost_bets

    total_staked = round(sum((bet.amount or 0.0) for bet in bets), 2)
    total_winnings = round(sum((bet.winnings or 0.0) for bet in won_bets), 2)
    total_profit = round(total_winnings - sum((bet.amount or 0.0) for bet in settled_bets), 2)
    race_win_rate = round((total_wins / total_races) * 100, 1) if total_races else 0.0
    bet_win_rate = round((len(won_bets) / len(settled_bets)) * 100, 1) if settled_bets else 0.0

    market_unlocked, market_progress_races, account_age_hours = get_market_unlock_progress(user)
    memorial_trophies = Trophy.query.filter_by(user_id=user.id).order_by(Trophy.earned_at.desc(), Trophy.id.desc()).all()
    market_hours_left = max(0, int(math.ceil(24 - account_age_hours)))

    return render_template(
        'profil.html',
        user=user,
        pigs=pigs,
        active_pigs=active_pigs,
        retired_pigs=retired_pigs,
        best_pig=best_pig,
        total_races=total_races,
        total_wins=total_wins,
        total_school_sessions=total_school_sessions,
        legendary_pigs=legendary_pigs,
        race_win_rate=race_win_rate,
        bets=bets,
        won_bets=won_bets,
        lost_bets=lost_bets,
        pending_bets=pending_bets,
        total_staked=total_staked,
        total_winnings=total_winnings,
        total_profit=total_profit,
        bet_win_rate=bet_win_rate,
        bet_types=BET_TYPES,
        market_unlocked=market_unlocked,
        market_progress_races=market_progress_races,
        market_hours_left=market_hours_left,
        market_lock_reason=get_market_lock_reason(user),
        active_listing_count=get_active_listing_count(user),
        active_listing_ids=active_listing_ids,
        memorial_trophies=memorial_trophies,
    )
