"""Health check endpoint for load balancers and monitoring."""

from flask import Blueprint, jsonify
from extensions import db

health_bp = Blueprint('health', __name__)


@health_bp.route('/health')
def health():
    checks = {'status': 'ok'}
    try:
        db.session.execute(db.text('SELECT 1'))
        checks['database'] = 'ok'
    except Exception as e:
        checks['database'] = 'error'
        checks['status'] = 'degraded'

    from flask import current_app
    checks['scheduler'] = 'enabled' if current_app.config.get('SCHEDULER_ENABLED') else 'disabled'

    status_code = 200 if checks['status'] == 'ok' else 503
    return jsonify(checks), status_code
