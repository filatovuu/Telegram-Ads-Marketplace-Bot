import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas import (
    LocaleUpdateRequest,
    RoleSwitchRequest,
    UserResponse,
    WalletDisconnectResponse,
    WalletUpdateRequest,
    _to_friendly,
)
from app.core.deps import get_db
from app.core.security import get_current_user
from app.models.deal import Deal
from app.models.deal_message import DealMessage
from app.models.user import User
from app.services.user import switch_user_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Return the currently authenticated user."""
    return current_user


@router.post("/role", response_model=UserResponse)
async def switch_role(
    body: RoleSwitchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Switch the active role of the current user."""
    return await switch_user_role(db, current_user, body.role)


@router.patch("/locale", response_model=UserResponse)
async def update_locale(
    body: LocaleUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Update the locale (language) for the current user."""
    current_user.locale = body.locale
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.patch("/wallet", response_model=UserResponse)
async def update_wallet(
    body: WalletUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Update the TON wallet address for the current user."""
    new_address = _to_friendly(body.wallet_address)
    old_address = current_user.wallet_address
    wallet_changed = new_address != old_address

    current_user.wallet_address = new_address
    await db.commit()
    await db.refresh(current_user)

    # Auto-retry escrow creation only when the wallet actually changed
    if wallet_changed and current_user.wallet_address:
        try:
            from app.services.escrow_auto import retry_escrow_for_user_deals

            await retry_escrow_for_user_deals(db, current_user.id)
        except Exception:
            logger.exception("Failed to auto-retry escrow for user %s", current_user.id)

    return current_user


# Pre-escrow states where cancel is valid — these deals will be auto-cancelled
CANCELLABLE_STATUSES = [
    "DRAFT",
    "NEGOTIATION",
    "OWNER_ACCEPTED",
    "AWAITING_ESCROW_PAYMENT",
]


@router.delete("/wallet", response_model=WalletDisconnectResponse)
async def disconnect_wallet(
    confirm: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WalletDisconnectResponse:
    """Disconnect wallet; auto-cancel pre-escrow deals owned by this user."""
    result = await db.execute(
        select(func.count())
        .select_from(Deal)
        .where(
            Deal.owner_id == current_user.id,
            Deal.status.in_(CANCELLABLE_STATUSES),
        )
    )
    cancel_count = result.scalar() or 0

    if cancel_count > 0 and not confirm:
        return WalletDisconnectResponse(
            disconnected=False,
            active_deal_count=cancel_count,
            warning=(
                f"You have {cancel_count} active deal(s) that will be cancelled "
                "because escrow requires a connected wallet. "
                "Are you sure you want to disconnect?"
            ),
        )

    # Cancel affected deals
    cancelled = 0
    if cancel_count > 0:
        deals_result = await db.execute(
            select(Deal)
            .where(
                Deal.owner_id == current_user.id,
                Deal.status.in_(CANCELLABLE_STATUSES),
            )
            .options(selectinload(Deal.advertiser), selectinload(Deal.owner))
        )
        deals = list(deals_result.scalars().all())

        now = datetime.now(timezone.utc)
        for deal in deals:
            deal.status = "CANCELLED"
            deal.last_activity_at = now
            db.add(
                DealMessage(
                    deal_id=deal.id,
                    sender_user_id=None,
                    text="Deal cancelled: owner disconnected wallet",
                    message_type="system",
                )
            )
            cancelled += 1

    current_user.wallet_address = None
    await db.commit()

    # Fire-and-forget notifications for cancelled deals
    if cancelled > 0:
        from app.services.notification import notify_deal_status_change

        for deal in deals:
            try:
                await notify_deal_status_change(deal)
            except Exception:
                logger.exception("Failed to notify deal #%s cancellation", deal.id)

    return WalletDisconnectResponse(
        disconnected=True,
        cancelled_deal_count=cancelled,
    )
