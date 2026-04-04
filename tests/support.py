from app import create_app
from extensions import db
from helpers import init_default_config
from helpers.config import invalidate_config_cache
from models import User


def build_test_app():
    app = create_app('testing')
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    return app


def reset_database(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        invalidate_config_cache()
        init_default_config()


def ensure_user(app, username='Simon', password_hash='x', **kwargs):
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(username=username, password_hash=password_hash, **kwargs)
            db.session.add(user)
            db.session.commit()
        return int(user.id)
