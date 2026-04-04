from flask import Blueprint, render_template, request, redirect, url_for, session, flash, make_response
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta, timezone
import csv
import io
import json
import logging
import os
import re
import secrets
import unicodedata
from zoneinfo import ZoneInfo
from sqlalchemy import or_

from exceptions import InsufficientFundsError
from extensions import db
from models import User, Race, Pig, Bet, BalanceTransaction, CerealItem, TrainingItem, SchoolLessonItem, HangmanWordItem, PigAvatar, AuthEventLog
from sqlalchemy.orm import joinedload
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
    get_configured_bet_types,
    get_economy_settings,
    get_progression_settings,
    save_day_reward_multipliers,
    save_economy_settings,
    save_progression_settings,
)
from services.finance_service import credit_user, debit_user
from services.finance_service import (
    adjust_user_balance,
    build_finance_settings_from_form,
    get_finance_settings,
    save_finance_settings,
)
from services.pig_service import get_pig_settings
from services.race_engine_service import (
    get_race_engine_settings,
    reset_race_engine_settings,
    save_race_engine_settings,
    RaceEngineSettings,
)
from services.game_settings_service import get_game_settings
from services.race_service import attach_bet_outcome_snapshots, get_configured_npcs

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


def _normalize_hangman_word(raw_word):
    normalized = unicodedata.normalize('NFD', (raw_word or '').strip().upper())
    normalized = ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    if not normalized or len(normalized) > 80:
        return None
    if not any(ch.isalpha() for ch in normalized):
        return None
    if any((not ch.isalpha()) and ch != ' ' for ch in normalized):
        return None
    return normalized


def _get_bet_payout_balance_delta(bet):
    amount = (
        db.session.query(db.func.coalesce(db.func.sum(BalanceTransaction.amount), 0.0))
        .filter(
            BalanceTransaction.user_id == bet.user_id,
            BalanceTransaction.reference_type == 'bet',
            BalanceTransaction.reference_id == bet.id,
            BalanceTransaction.reason_code.in_([
                'bet_payout',
                'bet_payout_adjustment',
                'bet_payout_reversal',
            ]),
        )
        .scalar()
    )
    return round(float(amount or 0.0), 2)


def _reconcile_bet_record(bet):
    snapshot = getattr(bet, 'outcome_snapshot', None)
    if snapshot is None:
        attach_bet_outcome_snapshots([bet])
        snapshot = getattr(bet, 'outcome_snapshot', None)
    if snapshot is None or snapshot.actual_status is None:
        return False, "Course non terminee: aucun recalcul possible."

    expected_winnings = round(bet.amount * bet.odds_at_bet, 2) if snapshot.actual_status == 'won' else 0.0
    current_payout_delta = _get_bet_payout_balance_delta(bet)
    payout_delta = round(expected_winnings - current_payout_delta, 2)

    if payout_delta > 0:
        adjust_user_balance(
            bet.user_id,
            payout_delta,
            reason_code='bet_payout_adjustment',
            reason_label='Correction gain de pari',
            details=f"Correction admin du ticket #{bet.id} sur la course #{bet.race_id}.",
            reference_type='bet',
            reference_id=bet.id,
        )
    elif payout_delta < 0:
        adjust_user_balance(
            bet.user_id,
            payout_delta,
            reason_code='bet_payout_reversal',
            reason_label='Correction pari',
            details=f"Annulation du trop-percu sur le ticket #{bet.id} de la course #{bet.race_id}.",
            reference_type='bet',
            reference_id=bet.id,
        )

    bet.status = snapshot.actual_status
    bet.winnings = expected_winnings
    return True, snapshot.actual_status

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


@admin_bp.route('/admin/balance', methods=['GET', 'POST'])
@admin_required
def admin_balance(user):
    finance = get_finance_settings()
    pig = get_pig_settings()
    engine = get_race_engine_settings()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'save_finance':
            finance = build_finance_settings_from_form(request.form, current_settings=finance)
            save_finance_settings(finance)
            flash("Paramètres financiers sauvegardés.", "success")

        elif action == 'save_pig':
            from helpers.config import invalidate_config_cache

            def _fi(k, d):
                try:
                    return max(1, int(float(request.form.get(k, d))))
                except (TypeError, ValueError):
                    return int(d)

            def _ff(k, d):
                try:
                    return float(request.form.get(k, d))
                except (TypeError, ValueError):
                    return float(d)

            pig_payload = {
                'pig_max_slots': str(_fi('pig_max_slots', pig.max_slots)),
                'pig_retirement_min_wins': str(_fi('pig_retirement_min_wins', pig.retirement_min_wins)),
                'pig_weight_default_kg': str(_ff('pig_weight_default_kg', pig.weight_default_kg)),
                'pig_weight_min_kg': str(_ff('pig_weight_min_kg', pig.weight_min_kg)),
                'pig_weight_max_kg': str(_ff('pig_weight_max_kg', pig.weight_max_kg)),
                'pig_weight_malus_ratio': str(_ff('pig_weight_malus_ratio', pig.weight_malus_ratio)),
                'pig_weight_malus_max': str(_ff('pig_weight_malus_max', pig.weight_malus_max)),
                'pig_injury_min_risk': str(_ff('pig_injury_min_risk', pig.injury_min_risk)),
                'pig_injury_max_risk': str(_ff('pig_injury_max_risk', pig.injury_max_risk)),
                'pig_vet_response_minutes': str(_fi('pig_vet_response_minutes', pig.vet_response_minutes)),
            }
            existing = {
                e.key: e
                for e in GameConfig.query.filter(GameConfig.key.in_(list(pig_payload.keys()))).all()
            }
            for k, v in pig_payload.items():
                entry = existing.get(k)
                if entry:
                    entry.value = v
                else:
                    db.session.add(GameConfig(key=k, value=v))
            db.session.commit()
            invalidate_config_cache()
            pig = get_pig_settings()
            flash("Paramètres cochons sauvegardés.", "success")

        elif action == 'save_engine':
            raw_json = request.form.get('race_engine_json', '')
            try:
                json.loads(raw_json)  # Valide le JSON
                from helpers.config import set_config
                set_config('race_engine_config', raw_json)
                engine = get_race_engine_settings()
                flash("Moteur de course sauvegardé.", "success")
            except (ValueError, TypeError) as e:
                flash(f"JSON invalide : {e}", "error")

        elif action == 'reset_engine':
            reset_race_engine_settings()
            engine = get_race_engine_settings()
            flash("Moteur de course réinitialisé aux valeurs par défaut.", "success")

        elif action == 'save_bourse':
            from helpers.config import set_config, invalidate_config_cache
            try:
                sf = float(request.form.get('bourse_surcharge_factor', 0.05))
                md = max(1, int(float(request.form.get('bourse_movement_divisor', 10))))
                set_config('bourse_surcharge_factor', str(sf))
                set_config('bourse_movement_divisor', str(md))
                invalidate_config_cache()
                flash("Paramètres bourse sauvegardés.", "success")
            except (TypeError, ValueError) as e:
                flash(f"Valeur invalide : {e}", "error")

        # Reload after save
        finance = get_finance_settings()
        pig = get_pig_settings()
        engine = get_race_engine_settings()

    from helpers.config import get_config
    from data import BOURSE_SURCHARGE_FACTOR, BOURSE_MOVEMENT_DIVISOR, TAX_EXEMPT_REASON_CODES, CASINO_REASON_CODES
    return render_template(
        'admin_balance.html',
        user=user,
        admin_tab='balance',
        finance=finance,
        pig=pig,
        engine_json=engine.to_json(),
        bourse_surcharge_factor=float(get_config('bourse_surcharge_factor', str(BOURSE_SURCHARGE_FACTOR))),
        bourse_movement_divisor=int(float(get_config('bourse_movement_divisor', str(BOURSE_MOVEMENT_DIVISOR)))),
        tax_exempt_codes=sorted(TAX_EXEMPT_REASON_CODES),
        casino_reason_codes=sorted(CASINO_REASON_CODES),
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
            'timezone': get_config('timezone', 'Europe/Paris'),
            'race_schedule': settings.race_schedule,
            'schedule_dict': settings.schedule_dict,
            'race_themes': merged_themes,
            'race_npcs_text': race_npcs_text,
        },
        jours=JOURS_FR)


@admin_bp.route('/admin/save', methods=['POST'])
@admin_required
def admin_save(user):
    old_timezone = get_config('timezone', 'Europe/Paris')
    keys = [
        'race_hour', 'race_minute', 'market_hour',
        'market_minute', 'market_duration', 'min_real_participants', 'empty_race_mode', 'timezone'
    ]
    for key in keys:
        val = request.form.get(key)
        if val is not None:
            set_config(key, val)

    new_timezone = (request.form.get('timezone') or '').strip()
    if new_timezone:
        try:
            old_tz = ZoneInfo(old_timezone)
            new_tz = ZoneInfo(new_timezone)
        except Exception:
            flash("Fuseau horaire invalide. Aucun changement applique.", "error")
            return redirect(url_for('admin.admin_races'))

        if new_timezone != old_timezone:
            upcoming_races = Race.query.filter(
                Race.status.in_(['upcoming', 'open']),
                Race.scheduled_at.isnot(None),
            ).all()
            for race in upcoming_races:
                scheduled_utc = race.scheduled_at
                if scheduled_utc.tzinfo is None:
                    scheduled_utc = scheduled_utc.replace(tzinfo=timezone.utc)
                else:
                    scheduled_utc = scheduled_utc.astimezone(timezone.utc)

                old_local = scheduled_utc.astimezone(old_tz)
                preserved_local = datetime(
                    old_local.year, old_local.month, old_local.day,
                    old_local.hour, old_local.minute, old_local.second, old_local.microsecond,
                    tzinfo=new_tz,
                )
                race.scheduled_at = preserved_local.astimezone(timezone.utc).replace(tzinfo=None)

            db.session.commit()
            set_config('timezone', new_timezone)
            flash("Fuseau horaire mis a jour. Les courses a venir ont ete recalees pour garder les memes heures locales.", "success")
            flash("Note logs Docker: pour aligner l'heure systeme (TZ), redemarre le conteneur web.", "info")
        else:
            set_config('timezone', new_timezone)

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
                credit_user(
                    bet_user,
                    bet.amount,
                    reason_code='bet_refund',
                    reason_label='Remboursement (Course annulee)',
                    reference_type='race',
                    reference_id=race.id,
                    commit=False,
                )
            bet.status = 'cancelled'

    db.session.delete(race)
    db.session.commit()
    flash(f"Course #{race_id} annulee et paris rembourses.", "success")
    return redirect(url_for('admin.admin_races'))


# ══════════════════════════════════════════════════════════════════════════════
# Paris
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/bets')
@admin_required
def admin_bets(user):
    status_filter = (request.args.get('status') or '').strip()
    race_id_filter = request.args.get('race_id', type=int)
    username_filter = (request.args.get('username') or '').strip()
    mismatch_only = request.args.get('mismatch') == '1'

    query = Bet.query.join(User, User.id == Bet.user_id).join(Race, Race.id == Bet.race_id)
    if status_filter:
        query = query.filter(Bet.status == status_filter)
    if race_id_filter:
        query = query.filter(Bet.race_id == race_id_filter)
    if username_filter:
        query = query.filter(User.username.ilike(f"%{username_filter}%"))

    bets = (
        query
        .order_by(Bet.placed_at.desc(), Bet.id.desc())
        .limit(150)
        .all()
    )
    attach_bet_outcome_snapshots(bets)

    if mismatch_only:
        bets = [bet for bet in bets if not bet.outcome_snapshot.is_consistent]

    mismatch_count = sum(1 for bet in bets if not bet.outcome_snapshot.is_consistent)
    finished_count = sum(1 for bet in bets if bet.outcome_snapshot.race_finished)

    return render_template(
        'admin_bets.html',
        user=user,
        admin_tab='bets',
        bets=bets,
        bet_types=get_configured_bet_types(),
        filters={
            'status': status_filter,
            'race_id': race_id_filter or '',
            'username': username_filter,
            'mismatch': mismatch_only,
        },
        stats={
            'visible': len(bets),
            'finished': finished_count,
            'mismatch': mismatch_count,
        },
    )


@admin_bp.route('/admin/bets/reconcile', methods=['POST'])
@admin_required
def admin_reconcile_bets(user):
    bets = (
        Bet.query
        .join(Race, Race.id == Bet.race_id)
        .filter(Race.status == 'finished')
        .order_by(Bet.id.asc())
        .all()
    )
    attach_bet_outcome_snapshots(bets)

    updated = 0
    for bet in bets:
        if bet.outcome_snapshot.is_consistent:
            continue
        did_update, _ = _reconcile_bet_record(bet)
        if did_update:
            updated += 1

    db.session.commit()
    flash(f"{updated} ticket(s) ont ete recalcules et corriges.", "success")
    return redirect(url_for('admin.admin_bets'))


@admin_bp.route('/admin/bets/<int:bet_id>/reconcile', methods=['POST'])
@admin_required
def admin_reconcile_bet(user, bet_id):
    bet = Bet.query.get_or_404(bet_id)
    attach_bet_outcome_snapshots([bet])
    did_update, result = _reconcile_bet_record(bet)
    if not did_update:
        flash(result, "warning")
        return redirect(url_for('admin.admin_bets'))

    db.session.commit()
    flash(f"Ticket #{bet.id} recalcule: statut final {result}.", "success")
    return redirect(url_for('admin.admin_bets'))


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
            credit_user(
                u,
                50.0,
                reason_code='admin_gift',
                reason_label='Cadeau Admin',
                reference_type='user',
                reference_id=user.id,
                commit=False,
            )
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
        credit_user(
            target,
            amount,
            reason_code='admin_adjust',
            reason_label=reason,
            reference_type='user',
            reference_id=user.id,
            commit=False,
        )
        flash(f"💰 +{amount:.0f} 🪙 credites a {target.username}.", "success")
    else:
        try:
            debit_user(
                target,
                abs(amount),
                reason_code='admin_adjust',
                reason_label=reason,
                reference_type='user',
                reference_id=user.id,
                commit=False,
            )
        except InsufficientFundsError:
            flash(f"{target.username} n'a pas assez de BitGroins pour ce debit.", "error")
            return redirect(url_for('admin.admin_users'))
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
# Truffes
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/truffes', methods=['GET', 'POST'])
@admin_required
def admin_truffes(user):
    if request.method == 'POST':
        daily_limit = request.form.get('truffe_daily_limit', '1')
        replay_cost = request.form.get('truffe_replay_cost', '2')
        set_config('truffe_daily_limit', daily_limit)
        set_config('truffe_replay_cost', replay_cost)
        flash("Configuration des truffes sauvegardee !", "success")
        return redirect(url_for('admin.admin_truffes'))

    config = {
        'daily_limit': get_config('truffe_daily_limit', '1'),
        'replay_cost': get_config('truffe_replay_cost', '2'),
    }
    return render_template('admin_truffes.html', user=user, admin_tab='truffes', config=config)


# ══════════════════════════════════════════════════════════════════════════════
# Donnees de jeu (CRUD cereales, entrainements, lecons, mots du pendu)
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/data')
@admin_required
def admin_data(user):
    cereals = CerealItem.query.order_by(CerealItem.sort_order, CerealItem.id).all()
    trainings = TrainingItem.query.order_by(TrainingItem.sort_order, TrainingItem.id).all()
    lessons = SchoolLessonItem.query.order_by(SchoolLessonItem.sort_order, SchoolLessonItem.id).all()
    hangman_words = HangmanWordItem.query.order_by(HangmanWordItem.sort_order, HangmanWordItem.id).all()
    hangman_words_text = '\n'.join(word.word for word in hangman_words)
    return render_template('admin_data.html',
        user=user, admin_tab='data', cereals=cereals, trainings=trainings, lessons=lessons,
        hangman_words=hangman_words, hangman_words_text=hangman_words_text,
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
@admin_required
def admin_lesson_delete(user, item_id):
    item = SchoolLessonItem.query.get_or_404(item_id)
    name = item.name
    db.session.delete(item)
    db.session.commit()
    flash(f"Lecon '{name}' supprimee.", "success")
    return redirect(url_for('admin.admin_data'))


@admin_bp.route('/admin/data/lesson/<int:item_id>/toggle', methods=['POST'])
@admin_required
def admin_lesson_toggle(user, item_id):
    item = SchoolLessonItem.query.get_or_404(item_id)
    item.is_active = not item.is_active
    db.session.commit()
    state = 'activee' if item.is_active else 'desactivee'
    flash(f"{item.emoji} {item.name} {state}.", "success")
    return redirect(url_for('admin.admin_data'))


# ── Mots du Cochon Pendu ────────────────────────────────────────────────────

@admin_bp.route('/admin/data/hangman-word/<int:item_id>', methods=['GET'])
@admin_required
def admin_hangman_word_edit(user, item_id):
    item = HangmanWordItem.query.get_or_404(item_id)
    return render_template(
        'admin_data_form.html',
        user=user,
        admin_tab='data',
        mode='edit',
        item_type='hangman_word',
        item=item,
        stat_names=STAT_NAMES,
    )


@admin_bp.route('/admin/data/hangman-word/new', methods=['GET'])
@admin_required
def admin_hangman_word_new(user):
    return render_template(
        'admin_data_form.html',
        user=user,
        admin_tab='data',
        mode='new',
        item_type='hangman_word',
        item=None,
        stat_names=STAT_NAMES,
    )


@admin_bp.route('/admin/data/hangman-word/save', methods=['POST'])
@admin_required
def admin_hangman_word_save(user):
    item_id = request.form.get('item_id', type=int)
    redirect_target = (
        url_for('admin.admin_hangman_word_edit', item_id=item_id)
        if item_id else
        url_for('admin.admin_hangman_word_new')
    )

    word = _normalize_hangman_word(request.form.get('word', ''))
    if not word:
        flash("Le mot doit contenir uniquement des lettres et des espaces (accents autorises).", "warning")
        return redirect(redirect_target)

    if item_id:
        item = HangmanWordItem.query.get_or_404(item_id)
    else:
        item = HangmanWordItem()

    duplicate = HangmanWordItem.query.filter(
        HangmanWordItem.word == word,
        HangmanWordItem.id != item.id,
    ).first()
    if duplicate:
        flash(f"Le mot '{word}' existe deja.", "error")
        return redirect(redirect_target)

    item.word = word
    item.sort_order = request.form.get('sort_order', type=int) or 0
    item.is_active = 'is_active' in request.form
    if not item_id:
        db.session.add(item)

    db.session.commit()
    flash(f"Mot '{item.word}' sauvegarde !", "success")
    return redirect(url_for('admin.admin_data') + '#hangman-words')


@admin_bp.route('/admin/data/hangman-words/bulk-save', methods=['POST'])
@admin_required
def admin_hangman_words_bulk_save(user):
    raw_text = request.form.get('words_text', '')
    lines = raw_text.splitlines()
    normalized_words = []
    seen = set()
    invalid_lines = []

    for index, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            continue
        normalized = _normalize_hangman_word(raw_line)
        if not normalized:
            invalid_lines.append(index)
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        normalized_words.append(normalized)

    if invalid_lines:
        preview = ', '.join(str(line_no) for line_no in invalid_lines[:5])
        if len(invalid_lines) > 5:
            preview += ', ...'
        flash(f"Lignes invalides dans la liste de mots: {preview}. Utilise uniquement des lettres et des espaces.", "warning")
        return redirect(url_for('admin.admin_data') + '#hangman-words')

    if not normalized_words:
        flash("La liste de mots est vide. Colle au moins une ligne.", "warning")
        return redirect(url_for('admin.admin_data') + '#hangman-words')

    HangmanWordItem.query.delete()
    for index, word in enumerate(normalized_words):
        db.session.add(HangmanWordItem(word=word, is_active=True, sort_order=index))
    db.session.commit()

    flash(f"Liste du Cochon Pendu remplacee ({len(normalized_words)} mots/expressions).", "success")
    return redirect(url_for('admin.admin_data') + '#hangman-words')


@admin_bp.route('/admin/data/hangman-word/<int:item_id>/delete', methods=['POST'])
@admin_required
def admin_hangman_word_delete(user, item_id):
    item = HangmanWordItem.query.get_or_404(item_id)
    word = item.word
    db.session.delete(item)
    db.session.commit()
    flash(f"Mot '{word}' supprime.", "success")
    return redirect(url_for('admin.admin_data') + '#hangman-words')


@admin_bp.route('/admin/data/hangman-word/<int:item_id>/toggle', methods=['POST'])
@admin_required
def admin_hangman_word_toggle(user, item_id):
    item = HangmanWordItem.query.get_or_404(item_id)
    item.is_active = not item.is_active
    db.session.commit()
    state = 'active' if item.is_active else 'desactive'
    flash(f"Mot '{item.word}' {state}.", "success")
    return redirect(url_for('admin.admin_data') + '#hangman-words')


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
