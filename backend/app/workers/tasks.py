import logging

from app.workers import celery_app, worker_loop
from app.db.session import async_session_factory

logger = logging.getLogger(__name__)


@celery_app.task(name="collect_single_channel_stats", bind=True, max_retries=3, default_retry_delay=60)
def collect_single_channel_stats(self, channel_id: int) -> bool:
    """On-demand task: collect stats snapshot for a single channel."""
    from sqlalchemy import select
    from app.models.channel import Channel
    from app.services.stats import collect_snapshot

    async def _run() -> bool:
        async with async_session_factory() as db:
            try:
                result = await db.execute(select(Channel).where(Channel.id == channel_id))
                channel = result.scalar_one_or_none()
                if channel is None:
                    logger.warning("collect_single_channel_stats: channel %d not found", channel_id)
                    return False
                await collect_snapshot(db, channel)
                logger.info("Collected stats snapshot for channel %d", channel_id)
                return True
            finally:
                await db.close()

    try:
        return worker_loop().run_until_complete(_run())
    except Exception as exc:
        logger.exception("collect_single_channel_stats failed for channel %d", channel_id)
        raise self.retry(exc=exc)


@celery_app.task(name="collect_channel_stats", bind=True, max_retries=3, default_retry_delay=60)
def collect_channel_stats(self) -> int:
    """Periodic task: collect stats snapshots for all channels with bot admin access."""
    from app.services.stats import collect_all_snapshots

    async def _run() -> int:
        async with async_session_factory() as db:
            try:
                count = await collect_all_snapshots(db)
                logger.info("Collected %d channel stats snapshots", count)
                return count
            finally:
                await db.close()

    try:
        return worker_loop().run_until_complete(_run())
    except Exception as exc:
        logger.exception("collect_channel_stats failed")
        raise self.retry(exc=exc)
