from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit
import os

from extensions import db, APP_TIMEZONE
from helpers import run_race_if_needed, ensure_next_race, resolve_auctions, check_vet_deadlines, resolve_market_history

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
