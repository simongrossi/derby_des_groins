from flask import render_template, redirect, url_for, request
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from extensions import db
from helpers.auth import admin_required
from helpers.config import get_config
from models import User, Race, Pig, Bet, AuthEventLog
from routes.admin import admin_bp


@admin_bp.route('/admin')
@admin_required
def admin(user):
    """Redirige vers le dashboard."""
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/dashboard')
@admin_required
def admin_dashboard(user):
    stats = {
        'total_users': User.query.count(),
        'alive_pigs': Pig.query.filter_by(is_alive=True).count(),
        'finished_races': Race.query.filter_by(status='finished').count(),
        'injured_pigs': Pig.query.filter_by(is_alive=True, is_injured=True).count(),
        'total_balance': db.session.query(db.func.coalesce(db.func.sum(User.balance), 0)).scalar(),
        'avg_balance': db.session.query(db.func.coalesce(db.func.avg(User.balance), 0)).scalar(),
        'pending_bets': Bet.query.filter_by(status='pending').count(),
        'admin_count': User.query.filter_by(is_admin=True).count(),
    }
    recent_races = Race.query.filter_by(status='finished').order_by(Race.finished_at.desc()).limit(8).all()
    current_timezone = get_config('timezone', 'Europe/Paris')

    return render_template('admin_dashboard.html',
        user=user, admin_tab='dashboard', stats=stats, recent_races=recent_races, current_timezone=current_timezone)


@admin_bp.route('/admin/auth-logs')
@admin_required
def admin_auth_logs(user):
    page = max(1, request.args.get('page', default=1, type=int) or 1)
    event_type = (request.args.get('event_type', '') or '').strip()
    success_filter = (request.args.get('success', '') or '').strip()
    username = (request.args.get('username', '') or '').strip()
    ip_address = (request.args.get('ip', '') or '').strip()

    query = AuthEventLog.query.options(joinedload(AuthEventLog.user))
    if event_type:
        query = query.filter(AuthEventLog.event_type == event_type)
    if success_filter == '1':
        query = query.filter(AuthEventLog.is_success.is_(True))
    elif success_filter == '0':
        query = query.filter(AuthEventLog.is_success.is_(False))
    if username:
        query = query.filter(
            or_(
                AuthEventLog.username_attempt.ilike(f"%{username}%"),
                AuthEventLog.user.has(User.username.ilike(f"%{username}%")),
            )
        )
    if ip_address:
        query = query.filter(AuthEventLog.ip_address.ilike(f"%{ip_address}%"))

    pagination = query.order_by(AuthEventLog.occurred_at.desc(), AuthEventLog.id.desc()).paginate(
        page=page,
        per_page=100,
        error_out=False,
    )
    event_types = [row[0] for row in db.session.query(AuthEventLog.event_type).distinct().order_by(AuthEventLog.event_type).all()]

    return render_template(
        'admin_auth_logs.html',
        user=user,
        admin_tab='auth_logs',
        pagination=pagination,
        auth_logs=pagination.items,
        filters={
            'event_type': event_type,
            'success': success_filter,
            'username': username,
            'ip': ip_address,
        },
        event_types=event_types,
    )
