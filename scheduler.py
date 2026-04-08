from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit
import os

from extensions import db, APP_TIMEZONE
from helpers.race import ensure_next_race, run_race_if_needed
from helpers.veterinary import check_vet_deadlines
from services.market_service import resolve_auctions, resolve_market_history
from services.market_service import maybe_trigger_market_event, resolve_due_grain_future_contracts
from services.auth_log_service import purge_old_auth_events
from services.pig_vitals_buffer_service import flush_due_buffered_pig_vitals

scheduler = None


def scheduler_should_start(app):
    return app.config.get('SCHEDULER_ENABLED', True)


def run_scheduler_job(app, job_name, callback):
    with app.app_context():
        try:
            callback()
        except Exception:
            app.logger.exception("Scheduler job failed: %s", job_name)
            db.session.rollback()
        finally:
            db.session.remove()


def start_scheduler(app):
    global scheduler
    if scheduler is not None or not scheduler_should_start(app):
        return

    scheduler = BackgroundScheduler(timezone=APP_TIMEZONE)
    # On reduit a 5 secondes pour une reaction plus rapide au depart des courses
    scheduler.add_job(
        lambda: run_scheduler_job(app, 'race_tick', lambda: (run_race_if_needed(), ensure_next_race())),
        IntervalTrigger(seconds=5, timezone=APP_TIMEZONE),
        id='race-tick',
        replace_existing=True,
        max_instances=1,
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
        lambda: run_scheduler_job(app, 'pig_vitals_flush_tick', flush_due_buffered_pig_vitals),
        IntervalTrigger(seconds=15, timezone=APP_TIMEZONE),
        id='pig-vitals-flush-tick',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        lambda: run_scheduler_job(app, 'grain_future_delivery_tick', resolve_due_grain_future_contracts),
        IntervalTrigger(minutes=15, timezone=APP_TIMEZONE),
        id='grain-future-delivery-tick',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        lambda: run_scheduler_job(app, 'market_event_tick', maybe_trigger_market_event),
        IntervalTrigger(hours=6, timezone=APP_TIMEZONE),
        id='market-event-tick',
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
    app.logger.info("Background scheduler started (race interval: 5s)")


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
