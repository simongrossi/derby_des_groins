from datetime import datetime
import json
import re
import unicodedata

from exceptions import ValidationError
from extensions import db
from models import CerealItem, HangmanWordItem, SchoolLessonItem, TrainingItem

STAT_NAMES = ('vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral')


def _parse_int(value, field_label, default=0):
    raw_value = default if value in (None, '') else value
    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Valeur invalide pour {field_label}.") from exc


def _parse_float(value, field_label, default=0.0):
    raw_value = default if value in (None, '') else value
    try:
        return float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Valeur invalide pour {field_label}.") from exc


def _parse_optional_datetime(value, field_label):
    raw_value = (value or '').strip()
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Date invalide pour {field_label}.") from exc


def _apply_stat_fields(item, form_data):
    for stat_name in STAT_NAMES:
        setattr(
            item,
            f'stat_{stat_name}',
            _parse_float(form_data.get(f'stat_{stat_name}', 0), f"stat {stat_name}", 0),
        )


def save_cereal_item(form_data, item=None):
    item = item or CerealItem(key=(form_data.get('key', '') or '').strip().lower())
    if item.id is None:
        db.session.add(item)

    item.name = (form_data.get('name', '') or '').strip()
    item.emoji = (form_data.get('emoji', '🌾') or '🌾').strip()
    item.cost = _parse_float(form_data.get('cost', 5), 'cout', 5)
    item.description = (form_data.get('description', '') or '').strip()
    item.hunger_restore = _parse_float(form_data.get('hunger_restore', 0), 'faim rendue', 0)
    item.energy_restore = _parse_float(form_data.get('energy_restore', 0), 'energie rendue', 0)
    item.weight_delta = _parse_float(form_data.get('weight_delta', 0), 'poids', 0)
    item.valeur_fourragere = _parse_float(form_data.get('valeur_fourragere', 100), 'valeur fourragere', 100)
    item.is_active = 'is_active' in form_data
    item.sort_order = _parse_int(form_data.get('sort_order', 0), 'ordre', 0)
    item.available_from = _parse_optional_datetime(form_data.get('available_from', ''), 'disponibilite debut')
    item.available_until = _parse_optional_datetime(form_data.get('available_until', ''), 'disponibilite fin')
    _apply_stat_fields(item, form_data)

    db.session.commit()
    return item


def delete_cereal_item(item):
    name = item.name
    db.session.delete(item)
    db.session.commit()
    return name


def toggle_cereal_item(item):
    item.is_active = not item.is_active
    db.session.commit()
    return item.is_active


def save_training_item(form_data, item=None):
    item = item or TrainingItem(key=(form_data.get('key', '') or '').strip().lower())
    if item.id is None:
        db.session.add(item)

    item.name = (form_data.get('name', '') or '').strip()
    item.emoji = (form_data.get('emoji', '💪') or '💪').strip()
    item.description = (form_data.get('description', '') or '').strip()
    item.energy_cost = _parse_int(form_data.get('energy_cost', 25), 'cout energie', 25)
    item.hunger_cost = _parse_int(form_data.get('hunger_cost', 10), 'cout faim', 10)
    item.weight_delta = _parse_float(form_data.get('weight_delta', 0), 'variation de poids', 0)
    item.min_happiness = _parse_int(form_data.get('min_happiness', 20), 'bonheur minimum', 20)
    item.happiness_bonus = _parse_int(form_data.get('happiness_bonus', 0), 'bonus bonheur', 0)
    item.is_active = 'is_active' in form_data
    item.sort_order = _parse_int(form_data.get('sort_order', 0), 'ordre', 0)
    item.available_from = _parse_optional_datetime(form_data.get('available_from', ''), 'disponibilite debut')
    item.available_until = _parse_optional_datetime(form_data.get('available_until', ''), 'disponibilite fin')
    _apply_stat_fields(item, form_data)

    db.session.commit()
    return item


def delete_training_item(item):
    name = item.name
    db.session.delete(item)
    db.session.commit()
    return name


def toggle_training_item(item):
    item.is_active = not item.is_active
    db.session.commit()
    return item.is_active


def save_lesson_item(form_data, item=None):
    item = item or SchoolLessonItem(key=(form_data.get('key', '') or '').strip().lower())
    if item.id is None:
        db.session.add(item)

    item.name = (form_data.get('name', '') or '').strip()
    item.emoji = (form_data.get('emoji', '📚') or '📚').strip()
    item.description = (form_data.get('description', '') or '').strip()
    item.question = (form_data.get('question', '') or '').strip()
    item.xp = _parse_int(form_data.get('xp', 20), 'xp', 20)
    item.wrong_xp = _parse_int(form_data.get('wrong_xp', 5), 'mauvais xp', 5)
    item.energy_cost = _parse_int(form_data.get('energy_cost', 10), 'cout energie', 10)
    item.hunger_cost = _parse_int(form_data.get('hunger_cost', 4), 'cout faim', 4)
    item.min_happiness = _parse_int(form_data.get('min_happiness', 15), 'bonheur minimum', 15)
    item.happiness_bonus = _parse_int(form_data.get('happiness_bonus', 5), 'bonus bonheur', 5)
    item.wrong_happiness_penalty = _parse_int(
        form_data.get('wrong_happiness_penalty', 5),
        'penalite bonheur',
        5,
    )
    item.is_active = 'is_active' in form_data
    item.sort_order = _parse_int(form_data.get('sort_order', 0), 'ordre', 0)
    item.available_from = _parse_optional_datetime(form_data.get('available_from', ''), 'disponibilite debut')
    item.available_until = _parse_optional_datetime(form_data.get('available_until', ''), 'disponibilite fin')
    _apply_stat_fields(item, form_data)

    answers = []
    for index in range(4):
        text = (form_data.get(f'answer_{index}_text', '') or '').strip()
        if not text:
            continue
        answers.append({
            'text': text,
            'correct': f'answer_{index}_correct' in form_data,
            'feedback': (form_data.get(f'answer_{index}_feedback', '') or '').strip(),
        })
    item.answers_json = json.dumps(answers, ensure_ascii=False)

    db.session.commit()
    return item


def delete_lesson_item(item):
    name = item.name
    db.session.delete(item)
    db.session.commit()
    return name


def toggle_lesson_item(item):
    item.is_active = not item.is_active
    db.session.commit()
    return item.is_active


def normalize_hangman_word(raw_word):
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


def save_hangman_word(form_data, item=None):
    word = normalize_hangman_word(form_data.get('word', ''))
    if not word:
        raise ValidationError(
            "Le mot doit contenir uniquement des lettres et des espaces (accents autorises)."
        )

    item = item or HangmanWordItem()
    duplicate = HangmanWordItem.query.filter(
        HangmanWordItem.word == word,
        HangmanWordItem.id != item.id,
    ).first()
    if duplicate:
        raise ValidationError(f"Le mot '{word}' existe deja.")

    item.word = word
    item.sort_order = _parse_int(form_data.get('sort_order', 0), 'ordre', 0)
    item.is_active = 'is_active' in form_data
    if item.id is None:
        db.session.add(item)

    db.session.commit()
    return item


def replace_hangman_words_from_text(raw_text):
    lines = (raw_text or '').splitlines()
    normalized_words = []
    seen = set()
    invalid_lines = []

    for index, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            continue
        normalized = normalize_hangman_word(raw_line)
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
        raise ValidationError(
            f"Lignes invalides dans la liste de mots: {preview}. Utilise uniquement des lettres et des espaces."
        )

    if not normalized_words:
        raise ValidationError("La liste de mots est vide. Colle au moins une ligne.")

    HangmanWordItem.query.delete()
    for index, word in enumerate(normalized_words):
        db.session.add(HangmanWordItem(word=word, is_active=True, sort_order=index))
    db.session.commit()
    return len(normalized_words)


def delete_hangman_word(item):
    word = item.word
    db.session.delete(item)
    db.session.commit()
    return word


def toggle_hangman_word(item):
    item.is_active = not item.is_active
    db.session.commit()
    return item.is_active
