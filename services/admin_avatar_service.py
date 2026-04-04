import os

from exceptions import ValidationError
from extensions import db
from models import Pig, PigAvatar

AVATAR_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'avatars')
ALLOWED_AVATAR_EXT = {'png', 'svg'}
MAX_AVATAR_SIZE = 256 * 1024


def _validate_avatar_name(name):
    name = (name or '').strip()
    if not name:
        raise ValidationError("Nom d'avatar requis.")
    return name


def _validate_svg_code(svg_code):
    svg_code = (svg_code or '').strip()
    if not svg_code.startswith('<svg') and not svg_code.startswith('<?xml'):
        raise ValidationError("Le code SVG doit commencer par <svg.")
    return svg_code


def _validate_uploaded_avatar_file(upload):
    ext = upload.filename.rsplit('.', 1)[-1].lower() if '.' in upload.filename else ''
    if ext not in ALLOWED_AVATAR_EXT:
        raise ValidationError("Format autorise : PNG ou SVG.")

    data = upload.read()
    if len(data) > MAX_AVATAR_SIZE:
        raise ValidationError("Fichier trop volumineux (max 256 Ko).")
    if ext == 'png' and not data[:4] == b'\x89PNG':
        raise ValidationError("Fichier PNG invalide.")
    if ext == 'svg':
        try:
            decoded = data.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise ValidationError("Fichier SVG invalide.") from exc
        _validate_svg_code(decoded)
    return ext, data


def _write_avatar_file(filename, payload, is_text=False):
    os.makedirs(AVATAR_DIR, exist_ok=True)
    mode = 'w' if is_text else 'wb'
    kwargs = {'encoding': 'utf-8'} if is_text else {}
    with open(os.path.join(AVATAR_DIR, filename), mode, **kwargs) as handle:
        handle.write(payload)


def get_avatar_svg_code(avatar):
    if avatar.format != 'svg':
        return ''
    filepath = os.path.join(AVATAR_DIR, avatar.filename)
    if not os.path.exists(filepath):
        return ''
    with open(filepath, 'r', encoding='utf-8') as handle:
        return handle.read()


def create_avatar(name, svg_code='', upload=None):
    name = _validate_avatar_name(name)
    svg_code = (svg_code or '').strip()

    if svg_code:
        svg_code = _validate_svg_code(svg_code)
        avatar = PigAvatar(name=name, filename='_tmp', format='svg')
        db.session.add(avatar)
        db.session.flush()
        avatar.filename = f'{avatar.id}.svg'
        _write_avatar_file(avatar.filename, svg_code, is_text=True)
        db.session.commit()
        return avatar

    if upload and upload.filename:
        ext, data = _validate_uploaded_avatar_file(upload)
        avatar = PigAvatar(name=name, filename='_tmp', format=ext)
        db.session.add(avatar)
        db.session.flush()
        avatar.filename = f'{avatar.id}.{ext}'
        _write_avatar_file(avatar.filename, data, is_text=False)
        db.session.commit()
        return avatar

    raise ValidationError("Fournir un fichier ou du code SVG.")


def update_avatar(avatar, name='', svg_code='', upload=None):
    name = (name or '').strip()
    if name:
        avatar.name = name

    svg_code = (svg_code or '').strip()
    if svg_code:
        svg_code = _validate_svg_code(svg_code)
        old_filepath = os.path.join(AVATAR_DIR, avatar.filename)
        if os.path.exists(old_filepath):
            os.remove(old_filepath)
        avatar.format = 'svg'
        avatar.filename = f'{avatar.id}.svg'
        _write_avatar_file(avatar.filename, svg_code, is_text=True)
        db.session.commit()
        return avatar

    if upload and upload.filename:
        ext, data = _validate_uploaded_avatar_file(upload)
        old_filepath = os.path.join(AVATAR_DIR, avatar.filename)
        if os.path.exists(old_filepath):
            os.remove(old_filepath)
        avatar.format = ext
        avatar.filename = f'{avatar.id}.{ext}'
        _write_avatar_file(avatar.filename, data, is_text=False)
        db.session.commit()
        return avatar

    db.session.commit()
    return avatar


def delete_avatar(avatar):
    Pig.query.filter_by(avatar_id=avatar.id).update({'avatar_id': None})
    filepath = os.path.join(AVATAR_DIR, avatar.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    name = avatar.name
    db.session.delete(avatar)
    db.session.commit()
    return name
