"""Celery task: verify post retention after the required period."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.workers import celery_app, worker_loop
from app.db.session import async_session_factory

logger = logging.getLogger(__name__)


@celery_app.task(name="verify_post_retention", bind=True, max_retries=3, default_retry_delay=60)
def verify_post_retention(self) -> int:
    """Find deals in RETENTION_CHECK where retention period has elapsed, then verify."""
    from app.models.deal import Deal
    from app.models.deal_posting import DealPosting
    from app.services.posting import verify_retention

    async def _run() -> int:
        count = 0
        now = datetime.now(timezone.utc)
        async with async_session_factory() as db:
            try:
                # Join deals in RETENTION_CHECK with their postings
                result = await db.execute(
                    select(DealPosting)
                    .join(Deal, Deal.id == DealPosting.deal_id)
                    .where(
                        Deal.status == "RETENTION_CHECK",
                        DealPosting.posted_at.isnot(None),
                        DealPosting.verified_at.is_(None),
                    )
                )
                postings = list(result.scalars().all())
                for posting in postings:
                    # Check if retention period has elapsed
                    retention_end = posting.posted_at + timedelta(hours=posting.retention_hours)
                    if now < retention_end:
                        continue
                    try:
                        await verify_retention(db, posting.deal_id)
                        count += 1
                    except Exception:
                        logger.exception("Failed to verify retention for deal %d", posting.deal_id)
                logger.info("Verified retention for %d deals", count)
            finally:
                await db.close()
        return count

    try:
        return worker_loop().run_until_complete(_run())
    except Exception as exc:
        logger.exception("verify_post_retention failed")
        raise self.retry(exc=exc)
