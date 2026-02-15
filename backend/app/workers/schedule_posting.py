"""Celery task: execute scheduled posts that are due."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.workers import celery_app, worker_loop
from app.db.session import async_session_factory

logger = logging.getLogger(__name__)


@celery_app.task(name="execute_scheduled_posts", bind=True, max_retries=3, default_retry_delay=60)
def execute_scheduled_posts(self) -> int:
    """Find deal postings where scheduled_at <= now and posted_at IS NULL, then auto-post."""
    from app.models.deal_posting import DealPosting
    from app.services.posting import auto_post

    async def _run() -> int:
        count = 0
        now = datetime.now(timezone.utc)
        async with async_session_factory() as db:
            try:
                result = await db.execute(
                    select(DealPosting)
                    .where(
                        DealPosting.scheduled_at <= now,
                        DealPosting.posted_at.is_(None),
                    )
                )
                postings = list(result.scalars().all())
                for posting in postings:
                    try:
                        await auto_post(db, posting.deal_id)
                        count += 1
                    except Exception:
                        logger.exception("Failed to auto-post deal %d", posting.deal_id)
                logger.info("Auto-posted %d scheduled deals", count)
            finally:
                await db.close()
        return count

    try:
        return worker_loop().run_until_complete(_run())
    except Exception as exc:
        logger.exception("execute_scheduled_posts failed")
        raise self.retry(exc=exc)
