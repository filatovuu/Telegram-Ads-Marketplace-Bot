"""Celery tasks to monitor on-chain escrow state changes."""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import async_session_factory
from app.workers import celery_app, worker_loop

logger = logging.getLogger(__name__)


@celery_app.task(name="monitor_escrow_deposits", bind=True, max_retries=3, default_retry_delay=60)
def monitor_escrow_deposits(self):
    """Poll escrows in 'init' state — verify deposit on-chain, transition to ESCROW_FUNDED."""
    try:
        worker_loop().run_until_complete(_monitor_deposits())
    except Exception as exc:
        logger.exception("monitor_escrow_deposits failed")
        raise self.retry(exc=exc)


@celery_app.task(name="monitor_escrow_completions", bind=True, max_retries=3, default_retry_delay=60)
def monitor_escrow_completions(self):
    """Poll escrows in 'funded'/'refund_sent'/'release_sent' — detect and verify on-chain completions."""
    try:
        worker_loop().run_until_complete(_monitor_completions())
    except Exception as exc:
        logger.exception("monitor_escrow_completions failed")
        raise self.retry(exc=exc)


async def _monitor_deposits():
    from app.models.escrow import Escrow
    from app.services import deal as deal_svc
    from app.services.ton.escrow_service import EscrowService

    svc = EscrowService()

    async with async_session_factory() as db:
        try:
            result = await db.execute(
                select(Escrow).where(Escrow.on_chain_state == "init")
            )
            active = list(result.scalars().all())

            if not active:
                return

            logger.info("Monitoring %d escrows for deposits", len(active))

            for i, escrow in enumerate(active):
                if i > 0:
                    await asyncio.sleep(2)  # rate-limit: Toncenter free tier ~1 req/s
                try:
                    verified = await svc.verify_deposit(db, escrow)
                    if verified:
                        logger.info(
                            "Deposit verified for deal %s — transitioning to ESCROW_FUNDED",
                            escrow.deal_id,
                        )
                        try:
                            await deal_svc.system_transition_deal(
                                db, escrow.deal_id, "confirm_escrow"
                            )
                        except Exception:
                            logger.exception(
                                "Failed to transition deal %s to ESCROW_FUNDED",
                                escrow.deal_id,
                            )
                except Exception:
                    logger.exception(
                        "Error monitoring deposit for deal %s", escrow.deal_id
                    )
        finally:
            await db.close()


async def _monitor_completions():
    from app.models.deal import Deal
    from app.models.escrow import Escrow
    from app.services.notification import notify_escrow_confirmed
    from app.services.ton.escrow_service import CHAIN_STATE_MAP, EscrowService

    svc = EscrowService()

    async with async_session_factory() as db:
        try:
            # Monitor funded escrows (safety net) AND sent transactions awaiting confirmation
            result = await db.execute(
                select(Escrow).where(
                    Escrow.on_chain_state.in_(["funded", "refund_sent", "release_sent"])
                )
            )
            escrows = list(result.scalars().all())

            if not escrows:
                return

            logger.info("Monitoring %d escrows for completions", len(escrows))

            for i, escrow in enumerate(escrows):
                if not escrow.contract_address or escrow.contract_address.startswith("pending-"):
                    continue
                if i > 0:
                    await asyncio.sleep(2)  # rate-limit
                try:
                    confirmed_state = None

                    if escrow.on_chain_state in ("refund_sent", "release_sent"):
                        # Verify sent transaction on-chain
                        confirmed_state = await svc.verify_sent_transaction(escrow)
                    else:
                        # Safety net for "funded" — detect external release/refund
                        state = await svc.get_on_chain_state(escrow.contract_address)
                        if state is not None and state > 1:
                            confirmed_state = CHAIN_STATE_MAP.get(state, "released")

                    if confirmed_state:
                        now = datetime.now(timezone.utc)
                        escrow.on_chain_state = confirmed_state
                        if confirmed_state == "released":
                            escrow.released_at = now
                        elif confirmed_state == "refunded":
                            escrow.refunded_at = now
                        await db.commit()
                        logger.info(
                            "Escrow deal %s confirmed as %s on-chain",
                            escrow.deal_id, confirmed_state,
                        )

                        # Send completion notification to advertiser/owner
                        try:
                            deal_result = await db.execute(
                                select(Deal).where(Deal.id == escrow.deal_id)
                            )
                            deal = deal_result.scalar_one_or_none()
                            if deal:
                                await notify_escrow_confirmed(
                                    deal, confirmed_state, float(escrow.amount),
                                )
                        except Exception:
                            logger.exception(
                                "Failed to send completion notification for deal %s",
                                escrow.deal_id,
                            )

                except Exception:
                    logger.exception(
                        "Error monitoring completion for deal %s", escrow.deal_id
                    )
        finally:
            await db.close()
