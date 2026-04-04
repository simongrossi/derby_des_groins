import json

from exceptions import ValidationError
from extensions import db
from helpers.config import invalidate_config_cache, set_config
from models import GameConfig


def _parse_int_field(form_data, key, default_value, minimum=1):
    try:
        return max(minimum, int(float(form_data.get(key, default_value))))
    except (TypeError, ValueError):
        return int(default_value)


def _parse_float_field(form_data, key, default_value):
    try:
        return float(form_data.get(key, default_value))
    except (TypeError, ValueError):
        return float(default_value)


def save_admin_pig_settings(form_data, pig_settings):
    pig_payload = {
        'pig_max_slots': str(_parse_int_field(form_data, 'pig_max_slots', pig_settings.max_slots)),
        'pig_retirement_min_wins': str(
            _parse_int_field(
                form_data,
                'pig_retirement_min_wins',
                pig_settings.retirement_min_wins,
            )
        ),
        'pig_weight_default_kg': str(
            _parse_float_field(form_data, 'pig_weight_default_kg', pig_settings.weight_default_kg)
        ),
        'pig_weight_min_kg': str(
            _parse_float_field(form_data, 'pig_weight_min_kg', pig_settings.weight_min_kg)
        ),
        'pig_weight_max_kg': str(
            _parse_float_field(form_data, 'pig_weight_max_kg', pig_settings.weight_max_kg)
        ),
        'pig_weight_malus_ratio': str(
            _parse_float_field(form_data, 'pig_weight_malus_ratio', pig_settings.weight_malus_ratio)
        ),
        'pig_weight_malus_max': str(
            _parse_float_field(form_data, 'pig_weight_malus_max', pig_settings.weight_malus_max)
        ),
        'pig_injury_min_risk': str(
            _parse_float_field(form_data, 'pig_injury_min_risk', pig_settings.injury_min_risk)
        ),
        'pig_injury_max_risk': str(
            _parse_float_field(form_data, 'pig_injury_max_risk', pig_settings.injury_max_risk)
        ),
        'pig_vet_response_minutes': str(
            _parse_int_field(
                form_data,
                'pig_vet_response_minutes',
                pig_settings.vet_response_minutes,
            )
        ),
    }
    existing_entries = {
        entry.key: entry
        for entry in GameConfig.query.filter(GameConfig.key.in_(list(pig_payload.keys()))).all()
    }
    for key, value in pig_payload.items():
        entry = existing_entries.get(key)
        if entry:
            entry.value = value
        else:
            db.session.add(GameConfig(key=key, value=value))

    db.session.commit()
    invalidate_config_cache()


def save_race_engine_settings_json(raw_json):
    try:
        json.loads(raw_json)
    except (ValueError, TypeError) as exc:
        raise ValidationError(f"JSON invalide : {exc}") from exc

    set_config('race_engine_config', raw_json)


def save_bourse_settings(form_data, default_surcharge_factor=0.05, default_movement_divisor=10):
    try:
        surcharge_factor = float(form_data.get('bourse_surcharge_factor', default_surcharge_factor))
        movement_divisor = max(
            1,
            int(float(form_data.get('bourse_movement_divisor', default_movement_divisor))),
        )
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Valeur invalide : {exc}") from exc

    set_config('bourse_surcharge_factor', str(surcharge_factor))
    set_config('bourse_movement_divisor', str(movement_divisor))
    invalidate_config_cache()
