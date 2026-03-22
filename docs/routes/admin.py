from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime
import json

from extensions import db
from models import User, Race, Pig, CerealItem, TrainingItem, SchoolLessonItem
from data import JOURS_FR
from helpers import (
    set_config, populate_race_participants, run_race_if_needed,
    get_all_cereals_dict, get_all_trainings_dict, get_all_school_lessons_dict,
)
from services.game_settings_service import get_game_settings

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('auth.login', next=request.path))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        flash("Accès réservé aux administrateurs.", "error")
        return redirect(url_for('main.index'))

    users = User.query.order_by(User.username.asc()).all()
    pigs = Pig.query.order_by(Pig.is_alive.desc(), Pig.name.asc()).all()
    upcoming_races = Race.query.filter(Race.status.in_(['upcoming', 'open'])).order_by(Race.scheduled_at).limit(20).all()
    next_race = Race.query.filter(Race.status == 'open').order_by(Race.scheduled_at).first()
    recent_races = Race.query.filter_by(status='finished').order_by(Race.finished_at.desc()).limit(10).all()

    settings = get_game_settings()
    return render_template('admin.html',
        user=user, users=users, pigs=pigs, upcoming_races=upcoming_races,
        next_race=next_race, recent_races=recent_races,
        config={
            'race_hour': settings.race_hour,
            'race_minute': settings.race_minute,
            'market_day': settings.market_day,
            'market_hour': settings.market_hour,
            'market_minute': settings.market_minute,
            'market_duration': settings.market_duration,
            'min_real_participants': settings.min_real_participants,
            'empty_race_mode': settings.empty_race_mode,
        },
        jours=JOURS_FR
    )


@admin_bp.route('/admin/save', methods=['POST'])
def admin_save():
    if 'user_id' not in session:
        return redirect(url_for('auth.login', next=request.path))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('main.index'))

    keys = [
        'race_hour', 'race_minute', 'market_day', 'market_hour',
        'market_minute', 'market_duration', 'min_real_participants', 'empty_race_mode'
    ]
    for key in keys:
        val = request.form.get(key)
        if val is not None:
            set_config(key, val)

    flash("Configuration sauvegardée !", "success")
    return redirect(url_for('admin.admin'))


@admin_bp.route('/admin/force-race', methods=['POST'])
def admin_force_race():
    if 'user_id' not in session:
        return redirect(url_for('auth.login', next=request.path))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('main.index'))

    race = Race(scheduled_at=datetime.now(), status='open')
    db.session.add(race)
    db.session.flush()
    populate_race_participants(race, respect_course_plans=False, allow_rebuild_if_bets=True, commit=True)
    run_race_if_needed()
    flash("🏁 Course forcée ! Résultats disponibles.", "success")
    return redirect(url_for('admin.admin'))


@admin_bp.route('/admin/pigs/<int:pig_id>/toggle-life', methods=['POST'])
def admin_toggle_pig_life(pig_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login', next=request.path))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('main.index'))

    pig = Pig.query.get_or_404(pig_id)
    pig.is_alive = not pig.is_alive
    if pig.is_alive:
        pig.death_date = None
        pig.death_cause = None
        pig.charcuterie_type = None
        pig.charcuterie_emoji = None
        pig.epitaph = None
    else:
        pig.death_date = datetime.utcnow()
        pig.death_cause = pig.death_cause or 'admin'
    db.session.commit()
    flash(f"Statut mis à jour pour {pig.name}.", 'success')
    return redirect(url_for('admin.admin'))


@admin_bp.route('/admin/races/<int:race_id>/cancel', methods=['POST'])
def admin_cancel_race(race_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login', next=request.path))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('main.index'))

    race = Race.query.get_or_404(race_id)
    if race.status == 'finished':
        flash("Impossible d'annuler une course terminée.", "error")
        return redirect(url_for('admin.admin'))

    # Refund bets if any
    for bet in race.bets:
        if bet.status == 'pending':
            bet_user = User.query.get(bet.user_id)
            if bet_user:
                bet_user.earn(bet.amount, reason_code='bet_refund', reason_label='Remboursement (Course annulée)', reference_type='race', reference_id=race.id)
            bet.status = 'cancelled'

    db.session.delete(race)
    db.session.commit()
    flash(f"Course #{race_id} annulée et paris remboursés.", "success")
    return redirect(url_for('admin.admin'))


@admin_bp.route('/admin/events/trigger', methods=['POST'])
def admin_trigger_event():
    if 'user_id' not in session:
        return redirect(url_for('auth.login', next=request.path))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('main.index'))

    event_type = request.form.get('event_type')
    if event_type == 'food_drop':
        all_pigs = Pig.query.filter_by(is_alive=True).all()
        for p in all_pigs:
            p.energy = min(100, (p.energy or 0) + 30)
            p.hunger = min(100, (p.hunger or 0) + 30)
        db.session.commit()
        flash("📦 Distribution de nourriture effectuée ! +30 Énergie/Faim pour tous les groins.", "success")
    elif event_type == 'vet_visit':
        injured_pigs = Pig.query.filter_by(is_alive=True, is_injured=True).all()
        for p in injured_pigs:
            p.heal()
        db.session.commit()
        flash(f"🏥 Visite vétérinaire ! {len(injured_pigs)} groins soignés.", "success")
    elif event_type == 'bonus_bg':
        all_users = User.query.all()
        for u in all_users:
            u.earn(50.0, reason_code='admin_gift', reason_label='Cadeau Admin', reference_type='user', reference_id=user.id)
        db.session.commit()
        flash("💰 Bonus de 50 🪙 BitGroins accordé à tous les joueurs !", "success")
    else:
        flash("Événement inconnu.", "error")

    return redirect(url_for('admin.admin'))


# ══════════════════════════════════════════════════════════════════════════════
# Admin — Données de jeu (CRUD céréales, entraînements, leçons)
# ══════════════════════════════════════════════════════════════════════════════

def _require_admin():
    """Vérifie que l'utilisateur est admin. Retourne (user, redirect) — si redirect != None, renvoyer."""
    if 'user_id' not in session:
        return None, redirect(url_for('auth.login', next=request.path))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        flash("Accès réservé aux administrateurs.", "error")
        return None, redirect(url_for('main.index'))
    return user, None


STAT_NAMES = ('vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral')


@admin_bp.route('/admin/data')
def admin_data():
    user, redir = _require_admin()
    if redir:
        return redir
    cereals = CerealItem.query.order_by(CerealItem.sort_order, CerealItem.id).all()
    trainings = TrainingItem.query.order_by(TrainingItem.sort_order, TrainingItem.id).all()
    lessons = SchoolLessonItem.query.order_by(SchoolLessonItem.sort_order, SchoolLessonItem.id).all()
    return render_template('admin_data.html',
        user=user, cereals=cereals, trainings=trainings, lessons=lessons,
        stat_names=STAT_NAMES)


# ── Céréales ──────────────────────────────────────────────────────────────────

@admin_bp.route('/admin/data/cereal/<int:item_id>', methods=['GET'])
def admin_cereal_edit(item_id):
    user, redir = _require_admin()
    if redir:
        return redir
    item = CerealItem.query.get_or_404(item_id)
    return render_template('admin_data_form.html',
        user=user, mode='edit', item_type='cereal', item=item, stat_names=STAT_NAMES)


@admin_bp.route('/admin/data/cereal/new', methods=['GET'])
def admin_cereal_new():
    user, redir = _require_admin()
    if redir:
        return redir
    return render_template('admin_data_form.html',
        user=user, mode='new', item_type='cereal', item=None, stat_names=STAT_NAMES)


@admin_bp.route('/admin/data/cereal/save', methods=['POST'])
def admin_cereal_save():
    user, redir = _require_admin()
    if redir:
        return redir
    item_id = request.form.get('item_id', type=int)
    if item_id:
        item = CerealItem.query.get_or_404(item_id)
    else:
        item = CerealItem(key=request.form.get('key', '').strip().lower())
        db.session.add(item)

    item.name = request.form.get('name', '').strip()
    item.emoji = request.form.get('emoji', '🌾').strip()
    item.cost = float(request.form.get('cost', 5))
    item.description = request.form.get('description', '').strip()
    item.hunger_restore = float(request.form.get('hunger_restore', 0))
    item.energy_restore = float(request.form.get('energy_restore', 0))
    item.weight_delta = float(request.form.get('weight_delta', 0))
    item.valeur_fourragere = float(request.form.get('valeur_fourragere', 100))
    item.is_active = 'is_active' in request.form
    item.sort_order = int(request.form.get('sort_order', 0))
    for stat in STAT_NAMES:
        setattr(item, f'stat_{stat}', float(request.form.get(f'stat_{stat}', 0)))

    af = request.form.get('available_from', '').strip()
    item.available_from = datetime.fromisoformat(af) if af else None
    au = request.form.get('available_until', '').strip()
    item.available_until = datetime.fromisoformat(au) if au else None

    db.session.commit()
    flash(f"Cereale '{item.name}' sauvegardee !", "success")
    return redirect(url_for('admin.admin_data'))


@admin_bp.route('/admin/data/cereal/<int:item_id>/delete', methods=['POST'])
def admin_cereal_delete(item_id):
    user, redir = _require_admin()
    if redir:
        return redir
    item = CerealItem.query.get_or_404(item_id)
    name = item.name
    db.session.delete(item)
    db.session.commit()
    flash(f"Cereale '{name}' supprimee.", "success")
    return redirect(url_for('admin.admin_data'))


@admin_bp.route('/admin/data/cereal/<int:item_id>/toggle', methods=['POST'])
def admin_cereal_toggle(item_id):
    user, redir = _require_admin()
    if redir:
        return redir
    item = CerealItem.query.get_or_404(item_id)
    item.is_active = not item.is_active
    db.session.commit()
    state = 'activee' if item.is_active else 'desactivee'
    flash(f"{item.emoji} {item.name} {state}.", "success")
    return redirect(url_for('admin.admin_data'))


# ── Entraînements ─────────────────────────────────────────────────────────────

@admin_bp.route('/admin/data/training/<int:item_id>', methods=['GET'])
def admin_training_edit(item_id):
    user, redir = _require_admin()
    if redir:
        return redir
    item = TrainingItem.query.get_or_404(item_id)
    return render_template('admin_data_form.html',
        user=user, mode='edit', item_type='training', item=item, stat_names=STAT_NAMES)


@admin_bp.route('/admin/data/training/new', methods=['GET'])
def admin_training_new():
    user, redir = _require_admin()
    if redir:
        return redir
    return render_template('admin_data_form.html',
        user=user, mode='new', item_type='training', item=None, stat_names=STAT_NAMES)


@admin_bp.route('/admin/data/training/save', methods=['POST'])
def admin_training_save():
    user, redir = _require_admin()
    if redir:
        return redir
    item_id = request.form.get('item_id', type=int)
    if item_id:
        item = TrainingItem.query.get_or_404(item_id)
    else:
        item = TrainingItem(key=request.form.get('key', '').strip().lower())
        db.session.add(item)

    item.name = request.form.get('name', '').strip()
    item.emoji = request.form.get('emoji', '💪').strip()
    item.description = request.form.get('description', '').strip()
    item.energy_cost = int(request.form.get('energy_cost', 25))
    item.hunger_cost = int(request.form.get('hunger_cost', 10))
    item.weight_delta = float(request.form.get('weight_delta', 0))
    item.min_happiness = int(request.form.get('min_happiness', 20))
    item.happiness_bonus = int(request.form.get('happiness_bonus', 0))
    item.is_active = 'is_active' in request.form
    item.sort_order = int(request.form.get('sort_order', 0))
    for stat in STAT_NAMES:
        setattr(item, f'stat_{stat}', float(request.form.get(f'stat_{stat}', 0)))

    af = request.form.get('available_from', '').strip()
    item.available_from = datetime.fromisoformat(af) if af else None
    au = request.form.get('available_until', '').strip()
    item.available_until = datetime.fromisoformat(au) if au else None

    db.session.commit()
    flash(f"Entrainement '{item.name}' sauvegarde !", "success")
    return redirect(url_for('admin.admin_data'))


@admin_bp.route('/admin/data/training/<int:item_id>/delete', methods=['POST'])
def admin_training_delete(item_id):
    user, redir = _require_admin()
    if redir:
        return redir
    item = TrainingItem.query.get_or_404(item_id)
    name = item.name
    db.session.delete(item)
    db.session.commit()
    flash(f"Entrainement '{name}' supprime.", "success")
    return redirect(url_for('admin.admin_data'))


@admin_bp.route('/admin/data/training/<int:item_id>/toggle', methods=['POST'])
def admin_training_toggle(item_id):
    user, redir = _require_admin()
    if redir:
        return redir
    item = TrainingItem.query.get_or_404(item_id)
    item.is_active = not item.is_active
    db.session.commit()
    state = 'active' if item.is_active else 'desactive'
    flash(f"{item.emoji} {item.name} {state}.", "success")
    return redirect(url_for('admin.admin_data'))


# ── Leçons d'école ────────────────────────────────────────────────────────────

@admin_bp.route('/admin/data/lesson/<int:item_id>', methods=['GET'])
def admin_lesson_edit(item_id):
    user, redir = _require_admin()
    if redir:
        return redir
    item = SchoolLessonItem.query.get_or_404(item_id)
    return render_template('admin_data_form.html',
        user=user, mode='edit', item_type='lesson', item=item, stat_names=STAT_NAMES)


@admin_bp.route('/admin/data/lesson/new', methods=['GET'])
def admin_lesson_new():
    user, redir = _require_admin()
    if redir:
        return redir
    return render_template('admin_data_form.html',
        user=user, mode='new', item_type='lesson', item=None, stat_names=STAT_NAMES)


@admin_bp.route('/admin/data/lesson/save', methods=['POST'])
def admin_lesson_save():
    user, redir = _require_admin()
    if redir:
        return redir
    item_id = request.form.get('item_id', type=int)
    if item_id:
        item = SchoolLessonItem.query.get_or_404(item_id)
    else:
        item = SchoolLessonItem(key=request.form.get('key', '').strip().lower())
        db.session.add(item)

    item.name = request.form.get('name', '').strip()
    item.emoji = request.form.get('emoji', '📚').strip()
    item.description = request.form.get('description', '').strip()
    item.question = request.form.get('question', '').strip()
    item.xp = int(request.form.get('xp', 20))
    item.wrong_xp = int(request.form.get('wrong_xp', 5))
    item.energy_cost = int(request.form.get('energy_cost', 10))
    item.hunger_cost = int(request.form.get('hunger_cost', 4))
    item.min_happiness = int(request.form.get('min_happiness', 15))
    item.happiness_bonus = int(request.form.get('happiness_bonus', 5))
    item.wrong_happiness_penalty = int(request.form.get('wrong_happiness_penalty', 5))
    item.is_active = 'is_active' in request.form
    item.sort_order = int(request.form.get('sort_order', 0))
    for stat in STAT_NAMES:
        setattr(item, f'stat_{stat}', float(request.form.get(f'stat_{stat}', 0)))

    # Réponses : 4 blocs answer_0_text, answer_0_correct, answer_0_feedback...
    answers = []
    for i in range(4):
        text = request.form.get(f'answer_{i}_text', '').strip()
        if not text:
            continue
        answers.append({
            'text': text,
            'correct': f'answer_{i}_correct' in request.form,
            'feedback': request.form.get(f'answer_{i}_feedback', '').strip(),
        })
    item.answers_json = json.dumps(answers, ensure_ascii=False)

    af = request.form.get('available_from', '').strip()
    item.available_from = datetime.fromisoformat(af) if af else None
    au = request.form.get('available_until', '').strip()
    item.available_until = datetime.fromisoformat(au) if au else None

    db.session.commit()
    flash(f"Lecon '{item.name}' sauvegardee !", "success")
    return redirect(url_for('admin.admin_data'))


@admin_bp.route('/admin/data/lesson/<int:item_id>/delete', methods=['POST'])
def admin_lesson_delete(item_id):
    user, redir = _require_admin()
    if redir:
        return redir
    item = SchoolLessonItem.query.get_or_404(item_id)
    name = item.name
    db.session.delete(item)
    db.session.commit()
    flash(f"Lecon '{name}' supprimee.", "success")
    return redirect(url_for('admin.admin_data'))


@admin_bp.route('/admin/data/lesson/<int:item_id>/toggle', methods=['POST'])
def admin_lesson_toggle(item_id):
    user, redir = _require_admin()
    if redir:
        return redir
    item = SchoolLessonItem.query.get_or_404(item_id)
    item.is_active = not item.is_active
    db.session.commit()
    state = 'activee' if item.is_active else 'desactivee'
    flash(f"{item.emoji} {item.name} {state}.", "success")
    return redirect(url_for('admin.admin_data'))
