"""Service layer for deal amendment proposals."""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deal_amendment import DealAmendment
from app.models.user import User
from app.services.deal import get_deal, _actor_for_user


async def create_amendment(
    db: AsyncSession,
    deal_id: int,
    user: User,
    proposed_price=None,
    proposed_publish_date=None,
    proposed_description=None,
) -> DealAmendment:
    """Owner proposes changes — only in NEGOTIATION, one pending at a time."""
    deal = await get_deal(db, deal_id, user.id)
    actor = await _actor_for_user(db, deal, user.id)

    if actor != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the channel owner or team managers can propose amendments",
        )

    if deal.status != "NEGOTIATION":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Amendments can only be proposed during negotiation",
        )

    # Check no pending amendment already exists
    existing = await db.execute(
        select(DealAmendment).where(
            DealAmendment.deal_id == deal_id, DealAmendment.status == "pending"
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="There is already a pending amendment for this deal",
        )

    if (
        proposed_price is None
        and proposed_publish_date is None
        and proposed_description is None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one proposed change is required",
        )

    amendment = DealAmendment(
        deal_id=deal_id,
        proposed_by_user_id=user.id,
        proposed_price=proposed_price,
        proposed_publish_date=proposed_publish_date,
        proposed_description=proposed_description,
        status="pending",
    )
    db.add(amendment)

    deal.last_activity_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(amendment)

    from app.services.notification import notify_amendment_proposed

    await notify_amendment_proposed(deal, amendment)

    return amendment


async def resolve_amendment(
    db: AsyncSession,
    deal_id: int,
    amendment_id: int,
    user: User,
    action: str,
) -> DealAmendment:
    """Advertiser accepts or rejects an amendment."""
    deal = await get_deal(db, deal_id, user.id)
    actor = await _actor_for_user(db, deal, user.id)

    if actor != "advertiser":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the advertiser can accept or reject amendments",
        )

    result = await db.execute(
        select(DealAmendment).where(
            DealAmendment.id == amendment_id,
            DealAmendment.deal_id == deal_id,
            DealAmendment.status == "pending",
        )
    )
    amendment = result.scalar_one_or_none()
    if not amendment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending amendment not found",
        )

    if action == "accept":
        amendment.status = "accepted"
        # Apply proposed changes to the deal
        if amendment.proposed_price is not None:
            deal.price = amendment.proposed_price
        if amendment.proposed_publish_date is not None:
            deal.publish_date = amendment.proposed_publish_date
        if amendment.proposed_description is not None:
            deal.description = amendment.proposed_description
    elif action == "reject":
        amendment.status = "rejected"
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid action, must be 'accept' or 'reject'",
        )

    deal.last_activity_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(amendment)

    from app.services.notification import notify_amendment_resolved

    await notify_amendment_resolved(deal, amendment)

    return amendment
