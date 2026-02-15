"""Auto-create escrow when both wallets are known and owner has confirmed.

Called after:
  - deal accept transition (NEGOTIATION → AWAITING_ESCROW_PAYMENT)
  - wallet update (profile or per-deal)
  - wallet confirmation (owner explicitly confirms payout address)
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.deal import Deal
from app.models.deal_message import DealMessage
from app.models.escrow import Escrow

logger = logging.getLogger(__name__)


def _resolve_owner_wallet(deal: Deal) -> str | None:
    """Resolve owner wallet: per-deal override > profile wallet."""
    if deal.owner_wallet_address:
        return deal.owner_wallet_address
    if deal.owner and deal.owner.wallet_address:
        return deal.owner.wallet_address
    return None


def _resolve_advertiser_wallet(deal: Deal) -> str | None:
    """Resolve advertiser wallet from profile."""
    if deal.advertiser and deal.advertiser.wallet_address:
        return deal.advertiser.wallet_address
    return None


async def try_auto_create_escrow(db: AsyncSession, deal: Deal) -> bool:
    """Attempt to auto-create escrow for a deal in AWAITING_ESCROW_PAYMENT.

    Returns True if escrow was created (or already exists), False if missing
    wallets or owner has not confirmed their payout wallet.
    """
    if deal.status != "AWAITING_ESCROW_PAYMENT":
        return False

    # Check if escrow already exists
    result = await db.execute(select(Escrow).where(Escrow.deal_id == deal.id))
    if result.scalar_one_or_none():
        return True

    advertiser_wallet = _resolve_advertiser_wallet(deal)
    owner_wallet = _resolve_owner_wallet(deal)

    # Owner must explicitly confirm their payout wallet for this deal
    if not deal.owner_wallet_confirmed:
        if not deal.wallet_notification_sent:
            if not owner_wallet:
                from app.services.notification import notify_wallet_needed

                await notify_wallet_needed(deal, "owner")
            else:
                from app.services.notification import notify_wallet_confirmation_needed

                await notify_wallet_confirmation_needed(deal)
            if not advertiser_wallet:
                from app.services.notification import notify_wallet_needed

                await notify_wallet_needed(deal, "advertiser")
            else:
                from app.services.notification import notify_escrow_pending

                await notify_escrow_pending(deal)
            deal.wallet_notification_sent = True
            await db.commit()
        return False

    if not advertiser_wallet or not owner_wallet:
        if not deal.wallet_notification_sent:
            from app.services.notification import notify_wallet_needed

            if not advertiser_wallet:
                await notify_wallet_needed(deal, "advertiser")
            if not owner_wallet:
                await notify_wallet_needed(deal, "owner")
            deal.wallet_notification_sent = True
            await db.commit()
        return False

    # Both wallets present + owner confirmed — create escrow
    from app.services.ton.escrow_service import EscrowService

    escrow_service = EscrowService()

    try:
        await escrow_service.create_escrow_for_deal(
            db,
            deal,
            advertiser_wallet,
            owner_wallet,
        )
    except ValueError:
        logger.exception("Auto-create escrow failed for deal %s", deal.id)
        return False

    deal.last_activity_at = datetime.now(timezone.utc)
    sys_msg = DealMessage(
        deal_id=deal.id,
        sender_user_id=None,
        text=f"Escrow contract created. Deposit within {settings.deal_expire_hours}h or the deal will expire.",
        message_type="system",
    )
    db.add(sys_msg)
    await db.commit()
    await db.refresh(deal)

    from app.services.notification import notify_escrow_auto_created

    await notify_escrow_auto_created(deal)

    logger.info("Auto-created escrow for deal %s", deal.id)
    return True


async def retry_escrow_for_user_deals(db: AsyncSession, user_id: int) -> int:
    """After a wallet update, check all AWAITING_ESCROW_PAYMENT deals
    where this user is a participant and no escrow exists yet.

    Returns the count of escrows created.
    """
    subq = select(Escrow.deal_id)
    result = await db.execute(
        select(Deal)
        .where(
            Deal.status == "AWAITING_ESCROW_PAYMENT",
            Deal.id.not_in(subq),
            (Deal.advertiser_id == user_id) | (Deal.owner_id == user_id),
        )
        .options(selectinload(Deal.advertiser), selectinload(Deal.owner))
    )
    deals = list(result.scalars().all())

    created = 0
    for deal in deals:
        # Wallet actually changed — reset flag so new notification can fire
        if deal.wallet_notification_sent:
            deal.wallet_notification_sent = False
            await db.commit()
        if await try_auto_create_escrow(db, deal):
            created += 1

    return created
