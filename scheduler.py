from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit
import os

from extensions import db, APP_TIMEZONE
from helpers import run_race_if_needed, ensure_next_race, resolve_auctions, check_vet_deadlines, resolve_market_history
from services.auth_log_service import purge_old_auth_events

scheduler = None


def scheduler_should_start(app):
    return app.config.get('SCHEDULER_ENABLED', True)


def run_scheduler_job(app, job_name, callback):
    with app.app_context():
        try:
            callback()
            db.session.commit() # S'assurer que tout est committé à la fin du job
        except Exception:
            app.logger.exception("Scheduler job failed: %s", job_name)
            db.session.rollback() # Rollback en cas d'erreur
        finally:
            db.session.remove() # Toujours nettoyer la session


def start_scheduler(app):
    global scheduler
    if scheduler is not None or not scheduler_should_start(app):
        return

    scheduler = BackgroundScheduler(timezone=APP_TIMEZONE)
    # Augmenter l'intervalle et max_instances pour race_tick
    scheduler.add_job(
        lambda: run_scheduler_job(app, 'race_tick', lambda: (run_race_if_needed(), ensure_next_race())),
        IntervalTrigger(seconds=10, timezone=APP_TIMEZONE), # Intervalle augmenté à 10 secondes
        id='race-tick',
        replace_existing=True,
        max_instances=2, # Permettre 2 instances pour plus de souplesse
        coalesce=True,
    )
    scheduler.add_job(
        lambda: run_scheduler_job(app, 'auction_tick', resolve_auctions),
        IntervalTrigger(minutes=1, timezone=APP_TIMEZONE),
        id='auction-tick',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        lambda: run_scheduler_job(app, 'vet_tick', check_vet_deadlines),
        IntervalTrigger(seconds=15, timezone=APP_TIMEZONE),
        id='vet-tick',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        lambda: run_scheduler_job(app, 'market_history_tick', resolve_market_history),
        IntervalTrigger(minutes=10, timezone=APP_TIMEZONE),
        id='market-history-tick',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        lambda: run_scheduler_job(
            app,
            'auth_log_purge',
            lambda: purge_old_auth_events(app.config.get('AUTH_LOG_RETENTION_DAYS', 180)),
        ),
        IntervalTrigger(hours=24, timezone=APP_TIMEZONE),
        id='auth-log-purge',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown(wait=False) if scheduler and scheduler.running else None)
    app.logger.info("Background scheduler started (race interval: 10s)")


def stop_scheduler():
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
    scheduler = None


def should_autostart_scheduler(app):
    if not app.config.get('SCHEDULER_ENABLED', True):
        return False
    if os.environ.get('DERBY_FORCE_SCHEDULER') == '1':
        return True
    if app.debug:
        return os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    return True
