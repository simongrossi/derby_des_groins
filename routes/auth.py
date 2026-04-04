from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import math

from extensions import db, limiter
from exceptions import BusinessRuleError, UserNotFoundError, ValidationError
from models import User, Pig, Bet, Auction, Trophy
from helpers import get_market_unlock_progress, get_market_lock_reason
from services.economy_service import get_configured_bet_types
from services.auth_log_service import log_auth_event
from services.auth_service import (
    authenticate_user,
    change_user_password,
    consume_magic_login_token,
    register_user,
    resolve_safe_next_url,
)
from services.pig_service import get_active_listing_count

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def register():
    if request.method == 'POST':
        try:
            user = register_user(
                request.form.get('username', ''),
                request.form.get('password', ''),
            )
        except BusinessRuleError as exc:
            return render_template('auth.html', error=str(exc), mode='register')
        session['user_id'] = user.id
        return redirect(url_for('pig.mon_cochon'))
    return render_template('auth.html', mode='register')


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if request.method == 'POST':
        try:
            user = authenticate_user(
                request.form.get('username', ''),
                request.form.get('password', ''),
            )
        except BusinessRuleError as exc:
            return render_template('auth.html', error=str(exc), mode='login')
        session['user_id'] = user.id
        next_url = resolve_safe_next_url(request.args.get('next') or request.form.get('next'))
        if next_url:
            return redirect(next_url)
        return redirect(url_for('main.index'))
    return render_template('auth.html', mode='login')


@auth_bp.route('/auth/magic/<token>')
def magic_login(token):
    """Connexion via lien magique genere par l'admin."""
    try:
        user = consume_magic_login_token(token)
    except UserNotFoundError as exc:
        flash(str(exc), "error")
        return redirect(url_for('auth.login'))
    except BusinessRuleError as exc:
        flash(str(exc), "error")
        return redirect(url_for('auth.login'))

    session['user_id'] = user.id
    flash(f"Bienvenue {user.username} ! Connecte via lien magique.", "success")
    return redirect(url_for('main.index'))


@auth_bp.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id:
        log_auth_event(
            event_type='logout',
            is_success=True,
            user_id=user_id,
        )
        db.session.commit()
    session.pop('user_id', None)
    return redirect(url_for('main.index'))


@auth_bp.route('/profil', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
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
        try:
            change_user_password(user, current_password, new_password, confirm_password)
            flash("Mot de passe mis à jour avec succès.", "success")
        except ValidationError as exc:
            message = str(exc)
            category = 'error'
            if 'au moins' in message or 'différent' in message or 'Remplis' in message:
                category = 'warning'
            flash(message, category)
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
        bet_types=get_configured_bet_types(),
        market_unlocked=market_unlocked,
        market_progress_races=market_progress_races,
        market_hours_left=market_hours_left,
        market_lock_reason=get_market_lock_reason(user),
        active_listing_count=get_active_listing_count(user),
        active_listing_ids=active_listing_ids,
        memorial_trophies=memorial_trophies,
    )
