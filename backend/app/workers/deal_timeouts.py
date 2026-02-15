"""Celery tasks for deal timeout handling.

- expire_inactive_deals: transitions stale deals to EXPIRED
- refund_overdue_deals: transitions overdue post-escrow deals to REFUNDED
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import settings
from app.workers import celery_app, worker_loop
from app.db.session import async_session_factory
from app.models.deal_posting import DealPosting

logger = logging.getLogger(__name__)


# Statuses eligible for expiration (pre-escrow only)
_EXPIRE_STATUSES = [
    "NEGOTIATION",
    "OWNER_ACCEPTED",
    "AWAITING_ESCROW_PAYMENT",
]

# Statuses eligible for refund timeout (post-escrow)
_REFUND_STATUSES = [
    "CREATIVE_PENDING_OWNER",
    "CREATIVE_SUBMITTED",
    "CREATIVE_CHANGES_REQUESTED",
    "CREATIVE_APPROVED",
    "SCHEDULED",
]


@celery_app.task(
    name="expire_inactive_deals", bind=True, max_retries=3, default_retry_delay=60
)
def expire_inactive_deals(self) -> int:
    """Find deals inactive for deal_expire_hours in negotiation/waiting states and expire them."""
    from app.services.deal import get_deals_for_timeout, system_transition_deal

    async def _run() -> int:
        count = 0
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=settings.deal_expire_hours
        )
        async with async_session_factory() as db:
            try:
                deals = await get_deals_for_timeout(db, cutoff, _EXPIRE_STATUSES)
                for deal in deals:
                    try:
                        await system_transition_deal(db, deal.id, "expire")
                        count += 1
                    except Exception:
                        logger.exception("Failed to expire deal %d", deal.id)
                logger.info("Expired %d inactive deals", count)
            finally:
                await db.close()
        return count

    try:
        return worker_loop().run_until_complete(_run())
    except Exception as exc:
        logger.exception("expire_inactive_deals failed")
        raise self.retry(exc=exc)


async def _get_posting(db, deal_id: int) -> DealPosting | None:
    """Fetch the DealPosting row for a deal, if any."""
    result = await db.execute(select(DealPosting).where(DealPosting.deal_id == deal_id))
    return result.scalar_one_or_none()


@celery_app.task(
    name="refund_overdue_deals", bind=True, max_retries=3, default_retry_delay=60
)
def refund_overdue_deals(self) -> int:
    """Find post-escrow deals past refund timeout and refund them."""
    from app.services.deal import get_deals_for_timeout, system_transition_deal
    from app.workers.escrow_operations import trigger_escrow_refund

    async def _run() -> int:
        count = 0
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=settings.deal_refund_hours)
        async with async_session_factory() as db:
            try:
                deals = await get_deals_for_timeout(db, cutoff, _REFUND_STATUSES)
                for deal in deals:
                    try:
                        # SCHEDULED deals: skip if the post is still due in the future
                        if deal.status == "SCHEDULED":
                            posting = await _get_posting(db, deal.id)
                            if (
                                posting
                                and posting.scheduled_at
                                and posting.scheduled_at > now
                            ):
                                continue

                        await system_transition_deal(db, deal.id, "refund")
                        trigger_escrow_refund.delay(deal.id)
                        count += 1
                    except Exception:
                        logger.exception("Failed to refund deal %d", deal.id)
                logger.info("Refunded %d overdue deals", count)
            finally:
                await db.close()
        return count

    try:
        return worker_loop().run_until_complete(_run())
    except Exception as exc:
        logger.exception("refund_overdue_deals failed")
        raise self.retry(exc=exc)
