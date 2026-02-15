import asyncio

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

_loop = None


def worker_loop() -> asyncio.AbstractEventLoop:
    """Return a shared event loop for all Celery worker tasks.

    All async tasks must use the same loop to avoid 'Future attached to
    a different loop' errors caused by the shared asyncpg connection pool.
    """
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
    return _loop

celery_app = Celery(
    "marketplace_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    beat_schedule={
        "collect-channel-stats-every-6h": {
            "task": "collect_channel_stats",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        "expire-inactive-deals-hourly": {
            "task": "expire_inactive_deals",
            "schedule": crontab(minute=0, hour="*"),
        },
        "refund-overdue-deals-hourly": {
            "task": "refund_overdue_deals",
            "schedule": crontab(minute=30, hour="*"),
        },
        "monitor-escrow-deposits-30s": {
            "task": "monitor_escrow_deposits",
            "schedule": 30.0,
        },
        "monitor-escrow-completions-60s": {
            "task": "monitor_escrow_completions",
            "schedule": 60.0,
        },
        "execute-scheduled-posts-60s": {
            "task": "execute_scheduled_posts",
            "schedule": 60.0,
        },
        "verify-post-retention-15m": {
            "task": "verify_post_retention",
            "schedule": crontab(minute="*/15"),
        },
    },
)

# Import tasks so they are registered with the celery app
import app.workers.tasks  # noqa: F401, E402
import app.workers.deal_timeouts  # noqa: F401, E402
import app.workers.monitor_escrow  # noqa: F401, E402
import app.workers.schedule_posting  # noqa: F401, E402
import app.workers.verify_posting  # noqa: F401, E402
import app.workers.escrow_operations  # noqa: F401, E402
