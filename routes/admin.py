from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import json
import logging
import os
import re
import secrets

from extensions import db
from models import User, Race, Pig, Bet, CerealItem, TrainingItem, SchoolLessonItem, PigAvatar
from data import JOURS_FR
from helpers import (
    set_config, get_config, populate_race_participants, run_race_if_needed,
    get_all_cereals_dict, get_all_trainings_dict, get_all_school_lessons_dict,
    invalidate_game_data_cache,
)
from helpers.config import DEFAULT_RACE_THEMES
from services.game_settings_service import get_game_settings

admin_bp = Blueprint('admin', __name__)

STAT_NAMES = ('vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral')


@admin_bp.after_request
def _invalidate_game_data_on_write(response):
    """Invalidate game data cache after any successful POST on /admin/data/*."""
    if (request.method == 'POST'
            and request.path.startswith('/admin/data/')
            and response.status_code in (200, 302)):
        invalidate_game_data_cache()
    return response


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _require_admin():
    """Verifie que l'utilisateur est admin. Retourne (user, redirect)."""
    if 'user_id' not in session:
        return None, redirect(url_for('auth.login', next=request.path))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        flash("Acces reserve aux administrateurs.", "error")
        return None, redirect(url_for('main.index'))
    return user, None


def _get_smtp_config():
    """Charge la config SMTP depuis GameConfig."""
    return {
        'host': get_config('smtp_host', ''),
        'port': get_config('smtp_port', '587'),
        'security': get_config('smtp_security', 'tls'),
        'user': get_config('smtp_user', ''),
        'password': get_config('smtp_password', ''),
        'from_addr': get_config('smtp_from', ''),
        'from_name': get_config('smtp_from_name', 'Derby des Groins'),
        'enabled': get_config('smtp_enabled', '0') == '1',
    }


def _send_email(to_addr, subject, body_html):
    """Envoie un email via la config SMTP. Retourne (success, error_message)."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    cfg = _get_smtp_config()
    if not cfg['enabled']:
        return False, "L'envoi d'emails est desactive."
    if not cfg['host'] or not cfg['from_addr']:
        return False, "Configuration SMTP incomplete."

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{cfg['from_name']} <{cfg['from_addr']}>"
    msg['To'] = to_addr
    msg.attach(MIMEText(body_html, 'html', 'utf-8'))

    try:
        port = int(cfg['port'] or 587)
        if cfg['security'] == 'ssl':
            server = smtplib.SMTP_SSL(cfg['host'], port, timeout=15)
        else:
            server = smtplib.SMTP(cfg['host'], port, timeout=15)
            if cfg['security'] == 'tls':
                server.starttls()

        if cfg['user'] and cfg['password']:
            server.login(cfg['user'], cfg['password'])

        server.sendmail(cfg['from_addr'], [to_addr], msg.as_string())
        server.quit()
        return True, None
    except Exception as e:
        logging.getLogger(__name__).exception("Echec envoi email a %s", to_addr)
        return False, "Erreur lors de l'envoi de l'email. Verifiez la configuration SMTP."


# ══════════════════════════════════════════════════════════════════════════════
# Dashboard
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin')
def admin():
    """Redirige vers le dashboard."""
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/dashboard')
def admin_dashboard():
    user, redir = _require_admin()
    if redir:
        return redir

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

    return render_template('admin_dashboard.html',
        user=user, admin_tab='dashboard', stats=stats, recent_races=recent_races)


# ══════════════════════════════════════════════════════════════════════════════
# Courses
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/races')
def admin_races():
    user, redir = _require_admin()
    if redir:
        return redir

    settings = get_game_settings()
    upcoming_races = Race.query.filter(Race.status.in_(['upcoming', 'open'])).order_by(Race.scheduled_at).limit(20).all()
    recent_races = Race.query.filter_by(status='finished').order_by(Race.finished_at.desc()).limit(10).all()

    # Thèmes : fusionner config DB avec defaults
    raw_themes = get_config('race_themes', '')
    try:
        current_themes = json.loads(raw_themes) if raw_themes else {}
    except (json.JSONDecodeError, TypeError):
        current_themes = {}
    merged_themes = {}
    for d in range(7):
        key = str(d)
        merged_themes[key] = {**DEFAULT_RACE_THEMES.get(key, {}), **current_themes.get(key, {})}

    return render_template('admin_races.html',
        user=user, admin_tab='races',
        upcoming_races=upcoming_races, recent_races=recent_races,
        config={
            'race_hour': settings.race_hour,
            'race_minute': settings.race_minute,
            'market_days': settings.market_days,
            'market_hour': settings.market_hour,
            'market_minute': settings.market_minute,
            'market_duration': settings.market_duration,
            'min_real_participants': settings.min_real_participants,
            'empty_race_mode': settings.empty_race_mode,
            'race_schedule': settings.race_schedule,
            'schedule_dict': settings.schedule_dict,
            'race_themes': merged_themes,
        },
        jours=JOURS_FR)


@admin_bp.route('/admin/save', methods=['POST'])
def admin_save():
    user, redir = _require_admin()
    if redir:
        return redir

    keys = [
        'race_hour', 'race_minute', 'market_hour',
        'market_minute', 'market_duration', 'min_real_participants', 'empty_race_mode'
    ]
    for key in keys:
        val = request.form.get(key)
        if val is not None:
            set_config(key, val)

    # Jours du marché : checkboxes multi-valeurs → "1,3,4"
    market_days = request.form.getlist('market_days')
    if market_days:
        set_config('market_day', ','.join(sorted(market_days, key=int)))

    schedule = {}
    for i in range(7):
        day_times_raw = request.form.get(f'schedule_{i}', '').strip()
        times = [t.strip() for t in day_times_raw.split(',') if t.strip()]
        valid_times = [t for t in times if re.match(r'^\d{1,2}:\d{2}$', t) and int(t.split(':')[0]) < 24 and int(t.split(':')[1]) < 60]
        schedule[str(i)] = sorted(valid_times)

    set_config('race_schedule', json.dumps(schedule))

    # Thèmes de course par jour
    themes = {}
    for i in range(7):
        try:
            multiplier = max(1, int(request.form.get(f'theme_{i}_multiplier', '1') or '1'))
        except (ValueError, TypeError):
            multiplier = 1
        themes[str(i)] = {
            'emoji': request.form.get(f'theme_{i}_emoji', '🥓').strip(),
            'name': request.form.get(f'theme_{i}_name', '').strip(),
            'tag': request.form.get(f'theme_{i}_tag', '').strip(),
            'description': request.form.get(f'theme_{i}_description', '').strip(),
            'accent': request.form.get(f'theme_{i}_accent', 'pink').strip(),
            'focus_stat': request.form.get(f'theme_{i}_focus_stat', '').strip(),
            'focus_label': request.form.get(f'theme_{i}_focus_label', '').strip(),
            'reward_multiplier': multiplier,
            'event_label': request.form.get(f'theme_{i}_event_label', '').strip(),
            'planning_hint': request.form.get(f'theme_{i}_planning_hint', '').strip(),
        }
    set_config('race_themes', json.dumps(themes, ensure_ascii=False))

    flash("Configuration sauvegardee !", "success")
    return redirect(url_for('admin.admin_races'))


@admin_bp.route('/admin/force-race', methods=['POST'])
def admin_force_race():
    user, redir = _require_admin()
    if redir:
        return redir

    race = Race(scheduled_at=datetime.now(), status='open')
    db.session.add(race)
    db.session.flush()
    populate_race_participants(race, respect_course_plans=False, allow_rebuild_if_bets=True, commit=True)
    run_race_if_needed()
    flash("🏁 Course forcee ! Resultats disponibles.", "success")
    return redirect(url_for('admin.admin_races'))


@admin_bp.route('/admin/races/<int:race_id>/cancel', methods=['POST'])
def admin_cancel_race(race_id):
    user, redir = _require_admin()
    if redir:
        return redir

    race = Race.query.get_or_404(race_id)
    if race.status == 'finished':
        flash("Impossible d'annuler une course terminee.", "error")
        return redirect(url_for('admin.admin_races'))

    for bet in race.bets:
        if bet.status == 'pending':
            bet_user = User.query.get(bet.user_id)
            if bet_user:
                bet_user.earn(bet.amount, reason_code='bet_refund',
                              reason_label='Remboursement (Course annulee)',
                              reference_type='race', reference_id=race.id)
            bet.status = 'cancelled'

    db.session.delete(race)
    db.session.commit()
    flash(f"Course #{race_id} annulee et paris rembourses.", "success")
    return redirect(url_for('admin.admin_races'))


# ══════════════════════════════════════════════════════════════════════════════
# Cochons
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/pigs')
def admin_pigs():
    user, redir = _require_admin()
    if redir:
        return redir

    pigs = Pig.query.order_by(Pig.is_alive.desc(), Pig.name.asc()).all()
    return render_template('admin_pigs.html', user=user, admin_tab='pigs', pigs=pigs)


@admin_bp.route('/admin/pigs/<int:pig_id>/toggle-life', methods=['POST'])
def admin_toggle_pig_life(pig_id):
    user, redir = _require_admin()
    if redir:
        return redir

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
    flash(f"Statut mis a jour pour {pig.name}.", 'success')
    return redirect(url_for('admin.admin_pigs'))


@admin_bp.route('/admin/pigs/<int:pig_id>/heal', methods=['POST'])
def admin_heal_pig(pig_id):
    user, redir = _require_admin()
    if redir:
        return redir

    pig = Pig.query.get_or_404(pig_id)
    if pig.is_injured:
        pig.heal()
        db.session.commit()
        flash(f"🏥 {pig.name} a ete soigne !", "success")
    else:
        flash(f"{pig.name} n'est pas blesse.", "warning")
    return redirect(url_for('admin.admin_pigs'))


# ══════════════════════════════════════════════════════════════════════════════
# Evenements
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/events')
def admin_events():
    user, redir = _require_admin()
    if redir:
        return redir
    return render_template('admin_events.html', user=user, admin_tab='events')


@admin_bp.route('/admin/events/trigger', methods=['POST'])
def admin_trigger_event():
    user, redir = _require_admin()
    if redir:
        return redir

    event_type = request.form.get('event_type')
    if event_type == 'food_drop':
        all_pigs = Pig.query.filter_by(is_alive=True).all()
        for p in all_pigs:
            p.energy = min(100, (p.energy or 0) + 30)
            p.hunger = min(100, (p.hunger or 0) + 30)
        db.session.commit()
        flash("📦 Distribution de nourriture ! +30 Energie/Faim pour tous.", "success")
    elif event_type == 'vet_visit':
        injured_pigs = Pig.query.filter_by(is_alive=True, is_injured=True).all()
        for p in injured_pigs:
            p.heal()
        db.session.commit()
        flash(f"🏥 Visite veterinaire ! {len(injured_pigs)} groins soignes.", "success")
    elif event_type == 'bonus_bg':
        all_users = User.query.all()
        for u in all_users:
            u.earn(50.0, reason_code='admin_gift', reason_label='Cadeau Admin',
                   reference_type='user', reference_id=user.id)
        db.session.commit()
        flash("💰 Bonus de 50 🪙 BitGroins accorde a tous !", "success")
    else:
        flash("Evenement inconnu.", "error")

    return redirect(url_for('admin.admin_events'))


# ══════════════════════════════════════════════════════════════════════════════
# Joueurs
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/users')
def admin_users():
    user, redir = _require_admin()
    if redir:
        return redir

    users = User.query.order_by(User.username.asc()).all()
    magic_links = session.pop('_admin_magic_links', None)
    return render_template('admin_users.html',
        user=user, admin_tab='users', users=users, magic_links=magic_links)


@admin_bp.route('/admin/users/<int:user_id>/toggle-admin', methods=['POST'])
def admin_toggle_user_admin(user_id):
    user, redir = _require_admin()
    if redir:
        return redir

    target = User.query.get_or_404(user_id)
    if target.id == user.id:
        flash("Tu ne peux pas modifier tes propres droits admin.", "error")
        return redirect(url_for('admin.admin_users'))

    target.is_admin = not target.is_admin
    db.session.commit()
    state = 'promu administrateur' if target.is_admin else 'retire des administrateurs'
    flash(f"{target.username} a ete {state}.", "success")
    return redirect(url_for('admin.admin_users'))


@admin_bp.route('/admin/users/reset-password', methods=['POST'])
def admin_reset_password():
    user, redir = _require_admin()
    if redir:
        return redir

    user_id = request.form.get('user_id', type=int)
    new_password = request.form.get('new_password', '').strip()

    if not user_id or len(new_password) < 4:
        flash("Mot de passe trop court (min 4 caracteres).", "error")
        return redirect(url_for('admin.admin_users'))

    target = User.query.get_or_404(user_id)
    target.password_hash = generate_password_hash(new_password)
    db.session.commit()
    flash(f"🔑 Mot de passe de {target.username} mis a jour.", "success")
    return redirect(url_for('admin.admin_users'))


@admin_bp.route('/admin/users/<int:user_id>/magic-link', methods=['POST'])
def admin_magic_link(user_id):
    user, redir = _require_admin()
    if redir:
        return redir

    target = User.query.get_or_404(user_id)

    # Generate a secure token
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(hours=24)

    # Store in GameConfig as magic_token_<user_id>
    set_config(f'magic_token_{target.id}', json.dumps({
        'token': token,
        'expires': expires.isoformat(),
        'user_id': target.id,
    }))

    # Build the magic link URL (safe: url_for evite le Host header injection)
    base_url = os.environ.get('BASE_URL', '').rstrip('/')
    if base_url:
        magic_url = f"{base_url}/auth/magic/{token}"
    else:
        magic_url = url_for('auth.magic_login', token=token, _external=True)

    # Store in session for display
    links = session.get('_admin_magic_links', {})
    links[target.id] = magic_url
    session['_admin_magic_links'] = links

    flash(f"🔗 Lien magique genere pour {target.username} (24h).", "success")

    # Try to send by email if SMTP is configured and user has email
    if hasattr(target, 'email') and target.email:
        smtp_cfg = _get_smtp_config()
        if smtp_cfg['enabled']:
            html = f"""
            <h2>🐷 Derby des Groins — Connexion magique</h2>
            <p>Salut <b>{target.username}</b> !</p>
            <p>Clique sur le lien ci-dessous pour te connecter automatiquement :</p>
            <p><a href="{magic_url}" style="background:#6366f1;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold;">Se connecter</a></p>
            <p style="color:#888;font-size:12px;">Ce lien expire dans 24 heures.</p>
            """
            ok, err = _send_email(target.email, 'Ton lien de connexion — Derby des Groins', html)
            if ok:
                flash(f"📧 Email envoye a {target.email}.", "success")
            else:
                flash(f"📧 Echec envoi email : {err}", "warning")

    return redirect(url_for('admin.admin_users'))


@admin_bp.route('/admin/users/adjust-balance', methods=['POST'])
def admin_adjust_balance():
    user, redir = _require_admin()
    if redir:
        return redir

    user_id = request.form.get('user_id', type=int)
    amount = request.form.get('amount', type=float)
    reason = request.form.get('reason', 'Ajustement admin').strip()

    if not user_id or amount is None or amount == 0:
        flash("Montant invalide.", "error")
        return redirect(url_for('admin.admin_users'))

    target = User.query.get_or_404(user_id)

    if amount > 0:
        target.earn(amount, reason_code='admin_adjust', reason_label=reason,
                    reference_type='user', reference_id=user.id)
        flash(f"💰 +{amount:.0f} 🪙 credites a {target.username}.", "success")
    else:
        target.pay(abs(amount), reason_code='admin_adjust', reason_label=reason,
                   reference_type='user', reference_id=user.id)
        flash(f"💸 {amount:.0f} 🪙 debites de {target.username}.", "success")

    db.session.commit()
    return redirect(url_for('admin.admin_users'))


# ══════════════════════════════════════════════════════════════════════════════
# Notifications SMTP
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/notifications')
def admin_notifications():
    user, redir = _require_admin()
    if redir:
        return redir

    smtp = _get_smtp_config()
    return render_template('admin_notifications.html',
        user=user, admin_tab='notifications', smtp=smtp)


@admin_bp.route('/admin/notifications/save', methods=['POST'])
def admin_save_smtp():
    user, redir = _require_admin()
    if redir:
        return redir

    smtp_keys = {
        'smtp_host': request.form.get('smtp_host', '').strip(),
        'smtp_port': request.form.get('smtp_port', '587').strip(),
        'smtp_security': request.form.get('smtp_security', 'tls').strip(),
        'smtp_user': request.form.get('smtp_user', '').strip(),
        'smtp_from': request.form.get('smtp_from', '').strip(),
        'smtp_from_name': request.form.get('smtp_from_name', 'Derby des Groins').strip(),
        'smtp_enabled': '1' if 'smtp_enabled' in request.form else '0',
    }

    # Ne pas ecraser le mot de passe SMTP si le champ est laisse vide
    new_password = request.form.get('smtp_password', '').strip()
    if new_password:
        smtp_keys['smtp_password'] = new_password

    for key, val in smtp_keys.items():
        set_config(key, val)

    flash("📧 Configuration SMTP sauvegardee !", "success")
    return redirect(url_for('admin.admin_notifications'))


@admin_bp.route('/admin/notifications/test', methods=['POST'])
def admin_test_smtp():
    user, redir = _require_admin()
    if redir:
        return redir

    to_addr = request.form.get('test_email', '').strip()
    if not to_addr:
        flash("Adresse email requise.", "error")
        return redirect(url_for('admin.admin_notifications'))

    html = """
    <h2>🐷 Derby des Groins — Test SMTP</h2>
    <p>Si tu lis ce message, la configuration SMTP fonctionne correctement !</p>
    <p style="color:#888;font-size:12px;">Envoye depuis le panneau d'administration.</p>
    """
    ok, err = _send_email(to_addr, 'Test SMTP — Derby des Groins', html)
    if ok:
        flash(f"✅ Email de test envoye a {to_addr} !", "success")
    else:
        flash(f"❌ Echec : {err}", "error")

    return redirect(url_for('admin.admin_notifications'))


# ══════════════════════════════════════════════════════════════════════════════
# Donnees de jeu (CRUD cereales, entrainements, lecons)
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/data')
def admin_data():
    user, redir = _require_admin()
    if redir:
        return redir
    cereals = CerealItem.query.order_by(CerealItem.sort_order, CerealItem.id).all()
    trainings = TrainingItem.query.order_by(TrainingItem.sort_order, TrainingItem.id).all()
    lessons = SchoolLessonItem.query.order_by(SchoolLessonItem.sort_order, SchoolLessonItem.id).all()
    return render_template('admin_data.html',
        user=user, admin_tab='data', cereals=cereals, trainings=trainings, lessons=lessons,
        stat_names=STAT_NAMES)


# ── Cereales ──────────────────────────────────────────────────────────────────

@admin_bp.route('/admin/data/cereal/<int:item_id>', methods=['GET'])
def admin_cereal_edit(item_id):
    user, redir = _require_admin()
    if redir:
        return redir
    item = CerealItem.query.get_or_404(item_id)
    return render_template('admin_data_form.html',
        user=user, admin_tab='data', mode='edit', item_type='cereal', item=item, stat_names=STAT_NAMES)


@admin_bp.route('/admin/data/cereal/new', methods=['GET'])
def admin_cereal_new():
    user, redir = _require_admin()
    if redir:
        return redir
    return render_template('admin_data_form.html',
        user=user, admin_tab='data', mode='new', item_type='cereal', item=None, stat_names=STAT_NAMES)


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


# ── Entrainements ─────────────────────────────────────────────────────────────

@admin_bp.route('/admin/data/training/<int:item_id>', methods=['GET'])
def admin_training_edit(item_id):
    user, redir = _require_admin()
    if redir:
        return redir
    item = TrainingItem.query.get_or_404(item_id)
    return render_template('admin_data_form.html',
        user=user, admin_tab='data', mode='edit', item_type='training', item=item, stat_names=STAT_NAMES)


@admin_bp.route('/admin/data/training/new', methods=['GET'])
def admin_training_new():
    user, redir = _require_admin()
    if redir:
        return redir
    return render_template('admin_data_form.html',
        user=user, admin_tab='data', mode='new', item_type='training', item=None, stat_names=STAT_NAMES)


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


# ── Lecons d'ecole ────────────────────────────────────────────────────────────

@admin_bp.route('/admin/data/lesson/<int:item_id>', methods=['GET'])
def admin_lesson_edit(item_id):
    user, redir = _require_admin()
    if redir:
        return redir
    item = SchoolLessonItem.query.get_or_404(item_id)
    return render_template('admin_data_form.html',
        user=user, admin_tab='data', mode='edit', item_type='lesson', item=item, stat_names=STAT_NAMES)


@admin_bp.route('/admin/data/lesson/new', methods=['GET'])
def admin_lesson_new():
    user, redir = _require_admin()
    if redir:
        return redir
    return render_template('admin_data_form.html',
        user=user, admin_tab='data', mode='new', item_type='lesson', item=None, stat_names=STAT_NAMES)


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


# ══════════════════════════════════════════════════════════════════════════════
# Avatars
# ══════════════════════════════════════════════════════════════════════════════

AVATAR_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'avatars')
ALLOWED_AVATAR_EXT = {'png', 'svg'}
MAX_AVATAR_SIZE = 256 * 1024  # 256 Ko


@admin_bp.route('/admin/avatars')
def admin_avatars():
    user, redir = _require_admin()
    if redir:
        return redir
    avatars = PigAvatar.query.order_by(PigAvatar.name).all()
    return render_template('admin_avatars.html', admin_tab='avatars', avatars=avatars)


@admin_bp.route('/admin/avatars/upload', methods=['POST'])
def admin_avatar_upload():
    user, redir = _require_admin()
    if redir:
        return redir

    name = request.form.get('name', '').strip()
    if not name:
        flash("Nom d'avatar requis.", "error")
        return redirect(url_for('admin.admin_avatars'))

    svg_code = request.form.get('svg_code', '').strip()
    file = request.files.get('avatar_file')

    if svg_code:
        if not svg_code.strip().startswith('<svg') and not svg_code.strip().startswith('<?xml'):
            flash("Le code SVG doit commencer par <svg.", "error")
            return redirect(url_for('admin.admin_avatars'))
        avatar = PigAvatar(name=name, filename='_tmp', format='svg')
        db.session.add(avatar)
        db.session.flush()
        filename = f'{avatar.id}.svg'
        avatar.filename = filename
        os.makedirs(AVATAR_DIR, exist_ok=True)
        with open(os.path.join(AVATAR_DIR, filename), 'w', encoding='utf-8') as f:
            f.write(svg_code)

    elif file and file.filename:
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in ALLOWED_AVATAR_EXT:
            flash("Format autorise : PNG ou SVG.", "error")
            return redirect(url_for('admin.admin_avatars'))
        data = file.read()
        if len(data) > MAX_AVATAR_SIZE:
            flash("Fichier trop volumineux (max 256 Ko).", "error")
            return redirect(url_for('admin.admin_avatars'))
        if ext == 'png' and not data[:4] == b'\x89PNG':
            flash("Fichier PNG invalide.", "error")
            return redirect(url_for('admin.admin_avatars'))
        avatar = PigAvatar(name=name, filename='_tmp', format=ext)
        db.session.add(avatar)
        db.session.flush()
        filename = f'{avatar.id}.{ext}'
        avatar.filename = filename
        os.makedirs(AVATAR_DIR, exist_ok=True)
        with open(os.path.join(AVATAR_DIR, filename), 'wb') as f:
            f.write(data)
    else:
        flash("Fournir un fichier ou du code SVG.", "error")
        return redirect(url_for('admin.admin_avatars'))

    db.session.commit()
    flash(f"Avatar '{name}' ajoute.", "success")
    return redirect(url_for('admin.admin_avatars'))


@admin_bp.route('/admin/avatars/<int:avatar_id>/edit', methods=['GET', 'POST'])
def admin_avatar_edit(avatar_id):
    user, redir = _require_admin()
    if redir:
        return redir
    avatar = PigAvatar.query.get_or_404(avatar_id)

    if request.method == 'GET':
        svg_code = ''
        if avatar.format == 'svg':
            filepath = os.path.join(AVATAR_DIR, avatar.filename)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    svg_code = f.read()
        return render_template('admin_avatar_edit.html', user=user, avatar=avatar, svg_code=svg_code)

    # POST
    name = request.form.get('name', '').strip()
    if name:
        avatar.name = name

    svg_code = request.form.get('svg_code', '').strip()
    file = request.files.get('avatar_file')

    if svg_code:
        if not svg_code.strip().startswith('<svg') and not svg_code.strip().startswith('<?xml'):
            flash("Le code SVG doit commencer par <svg.", "error")
            return redirect(url_for('admin.admin_avatar_edit', avatar_id=avatar.id))
        # Remove old file if format changed
        old_filepath = os.path.join(AVATAR_DIR, avatar.filename)
        if os.path.exists(old_filepath):
            os.remove(old_filepath)
        avatar.format = 'svg'
        avatar.filename = f'{avatar.id}.svg'
        os.makedirs(AVATAR_DIR, exist_ok=True)
        with open(os.path.join(AVATAR_DIR, avatar.filename), 'w', encoding='utf-8') as f:
            f.write(svg_code)
    elif file and file.filename:
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in ALLOWED_AVATAR_EXT:
            flash("Format autorise : PNG ou SVG.", "error")
            return redirect(url_for('admin.admin_avatar_edit', avatar_id=avatar.id))
        data = file.read()
        if len(data) > MAX_AVATAR_SIZE:
            flash("Fichier trop volumineux (max 256 Ko).", "error")
            return redirect(url_for('admin.admin_avatar_edit', avatar_id=avatar.id))
        old_filepath = os.path.join(AVATAR_DIR, avatar.filename)
        if os.path.exists(old_filepath):
            os.remove(old_filepath)
        avatar.format = ext
        avatar.filename = f'{avatar.id}.{ext}'
        os.makedirs(AVATAR_DIR, exist_ok=True)
        with open(os.path.join(AVATAR_DIR, avatar.filename), 'wb') as f:
            f.write(data)

    db.session.commit()
    flash(f"Avatar '{avatar.name}' mis a jour.", "success")
    return redirect(url_for('admin.admin_avatars'))


@admin_bp.route('/admin/avatars/<int:avatar_id>/delete', methods=['POST'])
def admin_avatar_delete(avatar_id):
    user, redir = _require_admin()
    if redir:
        return redir
    avatar = PigAvatar.query.get_or_404(avatar_id)
    Pig.query.filter_by(avatar_id=avatar.id).update({'avatar_id': None})
    filepath = os.path.join(AVATAR_DIR, avatar.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    db.session.delete(avatar)
    db.session.commit()
    flash(f"Avatar '{avatar.name}' supprime.", "success")
    return redirect(url_for('admin.admin_avatars'))
