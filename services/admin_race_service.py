import csv
import io
import json
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from exceptions import ValidationError
from extensions import db
from helpers import populate_race_participants, run_race_if_needed
from helpers.config import DEFAULT_RACE_THEMES, get_config, invalidate_config_cache
from models import GameConfig, Race, User
from services.finance_service import credit_user
from services.game_settings_service import get_game_settings
from services.race_service import get_configured_npcs


def _parse_race_npcs_from_lines(lines):
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


def _upsert_configs(values):
    existing_entries = {
        entry.key: entry
        for entry in GameConfig.query.filter(GameConfig.key.in_(list(values.keys()))).all()
    }
    for key, value in values.items():
        serialized = str(value)
        entry = existing_entries.get(key)
        if entry:
            entry.value = serialized
        else:
            db.session.add(GameConfig(key=key, value=serialized))


def _build_race_schedule_from_form(form_data):
    schedule = {}
    for day_index in range(7):
        day_times_raw = form_data.get(f'schedule_{day_index}', '').strip()
        times = [time_value.strip() for time_value in day_times_raw.split(',') if time_value.strip()]
        valid_times = [
            time_value
            for time_value in times
            if re.match(r'^\d{1,2}:\d{2}$', time_value)
            and int(time_value.split(':')[0]) < 24
            and int(time_value.split(':')[1]) < 60
        ]
        schedule[str(day_index)] = sorted(valid_times)
    return schedule


def _build_race_themes_from_form(form_data):
    themes = {}
    for day_index in range(7):
        try:
            multiplier = max(1, int(form_data.get(f'theme_{day_index}_multiplier', '1') or '1'))
        except (TypeError, ValueError):
            multiplier = 1
        themes[str(day_index)] = {
            'emoji': form_data.get(f'theme_{day_index}_emoji', '🥓').strip(),
            'name': form_data.get(f'theme_{day_index}_name', '').strip(),
            'tag': form_data.get(f'theme_{day_index}_tag', '').strip(),
            'description': form_data.get(f'theme_{day_index}_description', '').strip(),
            'accent': form_data.get(f'theme_{day_index}_accent', 'pink').strip(),
            'focus_stat': form_data.get(f'theme_{day_index}_focus_stat', '').strip(),
            'focus_label': form_data.get(f'theme_{day_index}_focus_label', '').strip(),
            'reward_multiplier': multiplier,
            'event_label': form_data.get(f'theme_{day_index}_event_label', '').strip(),
            'planning_hint': form_data.get(f'theme_{day_index}_planning_hint', '').strip(),
        }
    return themes


def _shift_upcoming_races_to_preserve_local_time(old_timezone_name, new_timezone_name):
    try:
        old_timezone = ZoneInfo(old_timezone_name)
        new_timezone = ZoneInfo(new_timezone_name)
    except Exception as exc:
        raise ValidationError("Fuseau horaire invalide. Aucun changement applique.") from exc

    if new_timezone_name == old_timezone_name:
        return False

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

        old_local = scheduled_utc.astimezone(old_timezone)
        preserved_local = datetime(
            old_local.year,
            old_local.month,
            old_local.day,
            old_local.hour,
            old_local.minute,
            old_local.second,
            old_local.microsecond,
            tzinfo=new_timezone,
        )
        race.scheduled_at = preserved_local.astimezone(timezone.utc).replace(tzinfo=None)
    return True


def build_admin_races_page_context():
    settings = get_game_settings()
    upcoming_races = (
        Race.query
        .filter(Race.status.in_(['upcoming', 'open']))
        .order_by(Race.scheduled_at)
        .limit(20)
        .all()
    )
    recent_races = (
        Race.query
        .filter_by(status='finished')
        .order_by(Race.finished_at.desc())
        .limit(10)
        .all()
    )

    raw_themes = get_config('race_themes', '')
    try:
        current_themes = json.loads(raw_themes) if raw_themes else {}
    except (json.JSONDecodeError, TypeError):
        current_themes = {}

    merged_themes = {}
    for day_index in range(7):
        key = str(day_index)
        merged_themes[key] = {**DEFAULT_RACE_THEMES.get(key, {}), **current_themes.get(key, {})}

    configured_npcs = get_configured_npcs()
    race_npcs_text = '\n'.join(
        f"{npc['name']}|{npc.get('emoji', '🐷')}"
        for npc in configured_npcs
    )

    return {
        'upcoming_races': upcoming_races,
        'recent_races': recent_races,
        'config': {
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
    }


def save_admin_races_configuration(form_data):
    old_timezone_name = get_config('timezone', 'Europe/Paris')
    new_timezone_name = (form_data.get('timezone') or '').strip() or old_timezone_name

    timezone_changed = _shift_upcoming_races_to_preserve_local_time(
        old_timezone_name,
        new_timezone_name,
    )

    config_updates = {}
    for key in (
        'race_hour',
        'race_minute',
        'market_hour',
        'market_minute',
        'market_duration',
        'min_real_participants',
        'empty_race_mode',
        'timezone',
    ):
        value = form_data.get(key)
        if value is not None:
            config_updates[key] = value

    market_days = form_data.getlist('market_days')
    if market_days:
        config_updates['market_day'] = ','.join(sorted(market_days, key=int))

    config_updates['race_schedule'] = json.dumps(_build_race_schedule_from_form(form_data))
    config_updates['race_themes'] = json.dumps(
        _build_race_themes_from_form(form_data),
        ensure_ascii=False,
    )

    raw_npcs = form_data.get('race_npcs_text', '')
    npcs = _parse_race_npcs_from_lines(raw_npcs.splitlines())
    config_updates['race_npcs'] = json.dumps(npcs, ensure_ascii=False) if npcs else ''

    _upsert_configs(config_updates)
    db.session.commit()
    invalidate_config_cache()

    messages = []
    if timezone_changed:
        messages.append((
            "Fuseau horaire mis a jour. Les courses a venir ont ete recalees pour garder les memes heures locales.",
            "success",
        ))
        messages.append((
            "Note logs Docker: pour aligner l'heure systeme (TZ), redemarre le conteneur web.",
            "info",
        ))
    messages.append(("Configuration sauvegardee !", "success"))
    return messages


def export_race_npcs_csv_content():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['name', 'emoji'])
    for npc in get_configured_npcs():
        writer.writerow([npc.get('name', ''), npc.get('emoji', '🐷')])
    return output.getvalue()


def parse_race_npcs_csv_content(content):
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames or 'name' not in reader.fieldnames:
        raise ValidationError("CSV invalide: colonne obligatoire 'name' manquante.")

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
        raise ValidationError("Import vide: aucun PNJ valide detecte.")
    return npcs


def import_race_npcs_csv(upload):
    if not upload or not upload.filename:
        raise ValidationError("Aucun fichier CSV selectionne.")

    try:
        content = upload.stream.read().decode('utf-8-sig')
    except Exception as exc:
        raise ValidationError("Impossible de lire le fichier CSV.") from exc

    npcs = parse_race_npcs_csv_content(content)
    _upsert_configs({'race_npcs': json.dumps(npcs, ensure_ascii=False)})
    db.session.commit()
    invalidate_config_cache()
    return len(npcs)


def force_race_now():
    race = Race(scheduled_at=datetime.now(), status='open')
    db.session.add(race)
    db.session.flush()
    populate_race_participants(
        race,
        respect_course_plans=False,
        allow_rebuild_if_bets=True,
        commit=True,
    )
    run_race_if_needed()
    return race


def cancel_race_and_refund_bets(race):
    if race.status == 'finished':
        raise ValidationError("Impossible d'annuler une course terminee.")

    for bet in race.bets:
        if bet.status != 'pending':
            continue
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

    race_id = race.id
    db.session.delete(race)
    db.session.commit()
    return race_id
