from flask import Blueprint, render_template, request, redirect, url_for, session, flash, make_response
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import csv
import io
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
from helpers.auth import admin_required
from services.economy_service import (
    build_admin_progression_context,
    build_admin_economy_context,
    build_day_reward_multipliers_from_form,
    build_economy_settings_from_form,
    build_progression_settings_from_form,
    build_progression_simulation_inputs_from_form,
    build_simulation_inputs_from_form,
    get_economy_settings,
    get_progression_settings,
    save_day_reward_multipliers,
    save_economy_settings,
    save_progression_settings,
)
from services.game_settings_service import get_game_settings
from services.race_service import get_configured_npcs

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

def _parse_race_npcs_from_lines(lines):
    """Normalise une liste de lignes 'Nom|Emoji' en liste de dicts."""
    npcs = []
    seen = set()
    for raw_line in lines:
        line = (raw_line or '').strip()
        if not line:
            continue
        if '|' in line:
            name_part, emoji_part = line.split('|', 1)
            name = name_part.strip()
            emoji = emoji_part.strip() or '🐷'
        else:
            name = line
            emoji = '🐷'
        if not name or name in seen:
            continue
        seen.add(name)
        npcs.append({'name': name, 'emoji': emoji})
    return npcs

# ══════════════════════════════════════════════════════════════════════════════
# Dashboard
# ══════════════════════════════════════════════════════════════════════════════

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

    return render_template('admin_dashboard.html',
        user=user, admin_tab='dashboard', stats=stats, recent_races=recent_races)


@admin_bp.route('/admin/economy', methods=['GET', 'POST'])
@admin_required
def admin_economy(user):
    current_settings = get_economy_settings()
    if request.method == 'POST':
        settings = build_economy_settings_from_form(request.form, current_settings=current_settings)
        reward_multiplier_overrides = build_day_reward_multipliers_from_form(request.form)
        preview_context = build_admin_economy_context(
            settings=settings,
            reward_multiplier_overrides=reward_multiplier_overrides,
        )
        simulation_inputs = build_simulation_inputs_from_form(
            request.form,
            preview_context['snapshot'],
            settings=settings,
        )
        if request.form.get('action') == 'save':
            save_economy_settings(settings)
            save_day_reward_multipliers(reward_multiplier_overrides)
            flash("Configuration economique sauvegardee.", "success")
            current_settings = settings
        context = build_admin_economy_context(
            settings=(current_settings if request.form.get('action') == 'save' else settings),
            simulation_inputs=simulation_inputs,
            reward_multiplier_overrides=(None if request.form.get('action') == 'save' else reward_multiplier_overrides),
        )
    else:
        context = build_admin_economy_context(settings=current_settings)

    return render_template(
        'admin_economy.html',
        user=user,
        admin_tab='economy',
        admin_page='economy',
        **context,
    )


@admin_bp.route('/admin/progression', methods=['GET', 'POST'])
@admin_required
def admin_progression(user):
    current_settings = get_progression_settings()
    if request.method == 'POST':
        settings = build_progression_settings_from_form(request.form, current_settings=current_settings)
        preview_context = build_admin_progression_context(settings=settings)
        simulation_inputs = build_progression_simulation_inputs_from_form(
            request.form,
            preview_context['snapshot'],
            settings=settings,
        )
        if request.form.get('action') == 'save':
            save_progression_settings(settings)
            flash("Configuration de progression sauvegardee.", "success")
            current_settings = settings
        context = build_admin_progression_context(
            settings=(current_settings if request.form.get('action') == 'save' else settings),
            simulation_inputs=simulation_inputs,
        )
    else:
        context = build_admin_progression_context(settings=current_settings)

    return render_template(
        'admin_economy.html',
        user=user,
        admin_tab='progression',
        admin_page='progression',
        **context,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Courses
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/races')
@admin_required
def admin_races(user):
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

    configured_npcs = get_configured_npcs()
    race_npcs_text = '\n'.join(f"{npc['name']}|{npc.get('emoji', '🐷')}" for npc in configured_npcs)

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
            'race_npcs_text': race_npcs_text,
        },
        jours=JOURS_FR)


@admin_bp.route('/admin/save', methods=['POST'])
@admin_required
def admin_save(user):
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
    # PNJ de remplissage des courses : une ligne par PNJ, format "Nom|🐷"
    raw_npcs = request.form.get('race_npcs_text', '')
    npcs = _parse_race_npcs_from_lines(raw_npcs.splitlines())
    if npcs:
        set_config('race_npcs', json.dumps(npcs, ensure_ascii=False))
    else:
        set_config('race_npcs', '')

    flash("Configuration sauvegardee !", "success")
    return redirect(url_for('admin.admin_races'))


@admin_bp.route('/admin/races/npcs/export')
@admin_required
def admin_export_race_npcs_csv(user):
    """Exporte les PNJ de remplissage en CSV (name,emoji)."""
    npcs = get_configured_npcs()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['name', 'emoji'])
    for npc in npcs:
        writer.writerow([npc.get('name', ''), npc.get('emoji', '🐷')])

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = 'attachment; filename=race_npcs.csv'
    return response


@admin_bp.route('/admin/races/npcs/import', methods=['POST'])
@admin_required
def admin_import_race_npcs_csv(user):
    """Importe les PNJ de remplissage depuis un CSV (name,emoji)."""
    upload = request.files.get('race_npcs_csv')
    if not upload or not upload.filename:
        flash("Aucun fichier CSV selectionne.", "warning")
        return redirect(url_for('admin.admin_races'))

    try:
        content = upload.stream.read().decode('utf-8-sig')
    except Exception:
        flash("Impossible de lire le fichier CSV.", "error")
        return redirect(url_for('admin.admin_races'))

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames or 'name' not in reader.fieldnames:
        flash("CSV invalide: colonne obligatoire 'name' manquante.", "error")
        return redirect(url_for('admin.admin_races'))

    lines = []
    for row in reader:
        if not row:
            continue
        name = (row.get('name') or '').strip()
        emoji = (row.get('emoji') or '').strip()
        if not name:
            continue
        lines.append(f"{name}|{emoji}" if emoji else name)

    npcs = _parse_race_npcs_from_lines(lines)
    if not npcs:
        flash("Import vide: aucun PNJ valide detecte.", "warning")
        return redirect(url_for('admin.admin_races'))

    set_config('race_npcs', json.dumps(npcs, ensure_ascii=False))
    flash(f"Import CSV reussi: {len(npcs)} PNJ enregistres.", "success")
    return redirect(url_for('admin.admin_races'))


@admin_bp.route('/admin/force-race', methods=['POST'])
@admin_required
def admin_force_race(user):
    race = Race(scheduled_at=datetime.now(), status='open')
    db.session.add(race)
    db.session.flush()
    populate_race_participants(race, respect_course_plans=False, allow_rebuild_if_bets=True, commit=True)
    run_race_if_needed()
    flash("🏁 Course forcee ! Resultats disponibles.", "success")
    return redirect(url_for('admin.admin_races'))


@admin_bp.route('/admin/races/<int:race_id>/cancel', methods=['POST'])
@admin_required
def admin_cancel_race(user, race_id):
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
@admin_required
def admin_pigs(user):
    pigs = Pig.query.order_by(Pig.is_alive.desc(), Pig.name.asc()).all()
    return render_template('admin_pigs.html', user=user, admin_tab='pigs', pigs=pigs)


@admin_bp.route('/admin/pigs/<int:pig_id>/toggle-life', methods=['POST'])
@admin_required
def admin_toggle_pig_life(user, pig_id):
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
@admin_required
def admin_heal_pig(user, pig_id):
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
@admin_required
def admin_events(user):
    return render_template('admin_events.html', user=user, admin_tab='events')


@admin_bp.route('/admin/events/trigger', methods=['POST'])
@admin_required
def admin_trigger_event(user):
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
@admin_required
def admin_users(user):
    users = User.query.order_by(User.username.asc()).all()
    magic_links = session.pop('_admin_magic_links', None)
    return render_template('admin_users.html',
        user=user, admin_tab='users', users=users, magic_links=magic_links)


@admin_bp.route('/admin/users/<int:user_id>/toggle-admin', methods=['POST'])
@admin_required
def admin_toggle_user_admin(user, user_id):
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
@admin_required
def admin_reset_password(user):
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
@admin_required
def admin_magic_link(user, user_id):
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
@admin_required
def admin_adjust_balance(user):
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
@admin_required
def admin_notifications(user):
    smtp = _get_smtp_config()
    return render_template('admin_notifications.html',
        user=user, admin_tab='notifications', smtp=smtp)


@admin_bp.route('/admin/notifications/save', methods=['POST'])
@admin_required
def admin_save_smtp(user):
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
@admin_required
def admin_test_smtp(user):
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
@admin_required
def admin_data(user):
    cereals = CerealItem.query.order_by(CerealItem.sort_order, CerealItem.id).all()
    trainings = TrainingItem.query.order_by(TrainingItem.sort_order, TrainingItem.id).all()
    lessons = SchoolLessonItem.query.order_by(SchoolLessonItem.sort_order, SchoolLessonItem.id).all()
    return render_template('admin_data.html',
        user=user, admin_tab='data', cereals=cereals, trainings=trainings, lessons=lessons,
        stat_names=STAT_NAMES)


# ── Cereales ──────────────────────────────────────────────────────────────────

@admin_bp.route('/admin/data/cereal/<int:item_id>', methods=['GET'])
@admin_required
def admin_cereal_edit(user, item_id):
    item = CerealItem.query.get_or_404(item_id)
    return render_template('admin_data_form.html',
        user=user, admin_tab='data', mode='edit', item_type='cereal', item=item, stat_names=STAT_NAMES)


@admin_bp.route('/admin/data/cereal/new', methods=['GET'])
@admin_required
def admin_cereal_new(user):
    return render_template('admin_data_form.html',
        user=user, admin_tab='data', mode='new', item_type='cereal', item=None, stat_names=STAT_NAMES)


@admin_bp.route('/admin/data/cereal/save', methods=['POST'])
@admin_required
def admin_cereal_save(user):
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
@admin_required
def admin_cereal_delete(user, item_id):
    item = CerealItem.query.get_or_404(item_id)
    name = item.name
    db.session.delete(item)
    db.session.commit()
    flash(f"Cereale '{name}' supprimee.", "success")
    return redirect(url_for('admin.admin_data'))


@admin_bp.route('/admin/data/cereal/<int:item_id>/toggle', methods=['POST'])
@admin_required
def admin_cereal_toggle(user, item_id):
    item = CerealItem.query.get_or_404(item_id)
    item.is_active = not item.is_active
    db.session.commit()
    state = 'activee' if item.is_active else 'desactivee'
    flash(f"{item.emoji} {item.name} {state}.", "success")
    return redirect(url_for('admin.admin_data'))


# ── Entrainements ─────────────────────────────────────────────────────────────

@admin_bp.route('/admin/data/training/<int:item_id>', methods=['GET'])
@admin_required
def admin_training_edit(user, item_id):
    item = TrainingItem.query.get_or_404(item_id)
    return render_template('admin_data_form.html',
        user=user, admin_tab='data', mode='edit', item_type='training', item=item, stat_names=STAT_NAMES)


@admin_bp.route('/admin/data/training/new', methods=['GET'])
@admin_required
def admin_training_new(user):
    return render_template('admin_data_form.html',
        user=user, admin_tab='data', mode='new', item_type='training', item=None, stat_names=STAT_NAMES)


@admin_bp.route('/admin/data/training/save', methods=['POST'])
@admin_required
def admin_training_save(user):
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
@admin_required
def admin_training_delete(user, item_id):
    item = TrainingItem.query.get_or_404(item_id)
    name = item.name
    db.session.delete(item)
    db.session.commit()
    flash(f"Entrainement '{name}' supprime.", "success")
    return redirect(url_for('admin.admin_data'))


@admin_bp.route('/admin/data/training/<int:item_id>/toggle', methods=['POST'])
@admin_required
def admin_training_toggle(user, item_id):
    item = TrainingItem.query.get_or_404(item_id)
    item.is_active = not item.is_active
    db.session.commit()
    state = 'active' if item.is_active else 'desactive'
    flash(f"{item.emoji} {item.name} {state}.", "success")
    return redirect(url_for('admin.admin_data'))


# ── Lecons d'ecole ────────────────────────────────────────────────────────────

@admin_bp.route('/admin/data/lesson/<int:item_id>', methods=['GET'])
@admin_required
def admin_lesson_edit(user, item_id):
    item = SchoolLessonItem.query.get_or_404(item_id)
    return render_template('admin_data_form.html',
        user=user, admin_tab='data', mode='edit', item_type='lesson', item=item, stat_names=STAT_NAMES)


@admin_bp.route('/admin/data/lesson/new', methods=['GET'])
@admin_required
def admin_lesson_new(user):
    return render_template('admin_data_form.html',
        user=user, admin_tab='data', mode='new', item_type='lesson', item=None, stat_names=STAT_NAMES)


@admin_bp.route('/admin/data/lesson/save', methods=['POST'])
@admin_required
def admin_lesson_save(user):
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
@admin_required
def admin_avatars(user):
    avatars = PigAvatar.query.order_by(PigAvatar.name).all()
    return render_template('admin_avatars.html', user=user, admin_tab='avatars', avatars=avatars)


@admin_bp.route('/admin/avatars/upload', methods=['POST'])
@admin_required
def admin_avatar_upload(user):
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
@admin_required
def admin_avatar_edit(user, avatar_id):
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
@admin_required
def admin_avatar_delete(user, avatar_id):
    avatar = PigAvatar.query.get_or_404(avatar_id)
    Pig.query.filter_by(avatar_id=avatar.id).update({'avatar_id': None})
    filepath = os.path.join(AVATAR_DIR, avatar.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    db.session.delete(avatar)
    db.session.commit()
    flash(f"Avatar '{avatar.name}' supprime.", "success")
    return redirect(url_for('admin.admin_avatars'))
