"""Celery tasks to trigger escrow operations (refund/release) in background."""

import logging

from app.db.session import async_session_factory
from app.workers import celery_app, worker_loop

logger = logging.getLogger(__name__)


@celery_app.task(name="trigger_escrow_refund", bind=True, max_retries=3, default_retry_delay=60)
def trigger_escrow_refund(self, deal_id: int):
    """Background task to trigger escrow refund on blockchain."""
    try:
        worker_loop().run_until_complete(_trigger_refund(deal_id))
    except Exception as exc:
        logger.exception("trigger_escrow_refund failed for deal %d", deal_id)
        raise self.retry(exc=exc)


@celery_app.task(name="trigger_escrow_release", bind=True, max_retries=3, default_retry_delay=60)
def trigger_escrow_release(self, deal_id: int):
    """Background task to trigger escrow release on blockchain."""
    try:
        worker_loop().run_until_complete(_trigger_release(deal_id))
    except Exception as exc:
        logger.exception("trigger_escrow_release failed for deal %d", deal_id)
        raise self.retry(exc=exc)


async def _trigger_refund(deal_id: int):
    from app.services.ton.escrow_service import EscrowService

    svc = EscrowService()
    async with async_session_factory() as db:
        try:
            escrow = await svc.get_escrow_for_deal(db, deal_id)
            if not escrow:
                logger.warning("No escrow record for deal %d, skipping refund", deal_id)
                return
            result = await svc.trigger_refund(db, escrow)
            if result:
                logger.info("Escrow refund triggered successfully for deal %d", deal_id)
            else:
                logger.warning("Escrow refund trigger returned False for deal %d", deal_id)
        finally:
            await db.close()


async def _trigger_release(deal_id: int):
    from app.services.ton.escrow_service import EscrowService

    svc = EscrowService()
    async with async_session_factory() as db:
        try:
            escrow = await svc.get_escrow_for_deal(db, deal_id)
            if not escrow:
                logger.warning("No escrow record for deal %d, skipping release", deal_id)
                return
            result = await svc.trigger_release(db, escrow)
            if result:
                logger.info("Escrow release triggered successfully for deal %d", deal_id)
            else:
                logger.warning("Escrow release trigger returned False for deal %d", deal_id)
        finally:
            await db.close()
