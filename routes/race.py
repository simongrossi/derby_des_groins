from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from config.game_rules import RACE_PLANNING_RULES
from exceptions import BusinessRuleError
from extensions import limiter
from models import User
from services.bet_service import place_bet_for_user
from services.race_page_service import (
    build_betting_page_context,
    build_courses_page_context,
)
from services.race_service import (
    RacePlanningError,
    plan_pig_for_race,
)

race_bp = Blueprint('race', __name__)


@race_bp.route('/courses')
def courses():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('auth.login'))

    return render_template('courses.html', **build_courses_page_context(user))


@race_bp.route('/paris')
def paris():
    """Page dédiée aux paris — cotes, formulaire de pari, historique."""
    return render_template(
        'paris.html',
        **build_betting_page_context(
            session.get('user_id'),
            request.args.get('race_id', type=int),
            request.args.get('slot'),
        ),
    )


@race_bp.route('/courses/plan', methods=['POST'])
@limiter.limit("10 per minute")
def plan_course():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('auth.login'))

    pig_id = request.form.get('pig_id', type=int)
    scheduled_at_raw = (request.form.get('scheduled_at') or '').strip()
    strategy_profile = {
        'phase_1': request.form.get(
            'strategy_phase_1',
            RACE_PLANNING_RULES.default_strategy_phase_1,
            type=int,
        ),
        'phase_2': request.form.get(
            'strategy_phase_2',
            RACE_PLANNING_RULES.default_strategy_phase_2,
            type=int,
        ),
        'phase_3': request.form.get(
            'strategy_phase_3',
            RACE_PLANNING_RULES.default_strategy_phase_3,
            type=int,
        ),
    }

    try:
        action = plan_pig_for_race(user.id, pig_id, scheduled_at_raw, strategy_profile)
    except RacePlanningError as exc:
        category = 'error' if 'invalide' in str(exc).lower() or 'introuvable' in str(exc).lower() else 'warning'
        flash(str(exc), category)
        return redirect(url_for('race.courses'))

    if action.action == 'removed':
        flash(f"📅 {action.pig_name} est retire du planning du {action.scheduled_at.strftime('%d/%m %H:%M')}.", "success")
    else:
        flash(f"📅 {action.pig_name} est maintenant planifie pour la course du {action.scheduled_at.strftime('%d/%m %H:%M')}.", "success")
    return redirect(url_for('race.courses'))


@race_bp.route('/bet', methods=['POST'])
@limiter.limit("10 per minute")
def place_bet():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    try:
        result = place_bet_for_user(
            session['user_id'],
            request.form.get('race_id', type=int),
            request.form.get('bet_type', 'win'),
            request.form.get('selection_order', ''),
            request.form.get('amount', type=float),
        )
        flash(result['message'], result.get('category', 'success'))
    except BusinessRuleError as exc:
        flash(str(exc), "error")
    return redirect(url_for('race.paris'))
