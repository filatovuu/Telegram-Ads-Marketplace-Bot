"""Creative version management — submit, approve, request changes, history."""

import logging

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.creative import CreativeVersion
from app.models.user import User
from app.services.deal import (
    get_deal,
    transition_deal,
    _actor_for_user,
    _check_team_permission_for_action,
)

logger = logging.getLogger(__name__)


async def submit_creative(
    db: AsyncSession,
    deal_id: int,
    user: User,
    text: str,
    entities_json: str | None = None,
    media_items: list[dict] | None = None,
) -> CreativeVersion:
    """Owner submits a creative version for advertiser review."""
    deal = await get_deal(db, deal_id, user.id)

    if deal.status not in ("CREATIVE_PENDING_OWNER", "CREATIVE_CHANGES_REQUESTED"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot submit creative in status {deal.status}",
        )

    actor = await _actor_for_user(db, deal, user.id)
    if actor != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the channel owner or team managers can submit creatives",
        )

    # Team member permission check
    if user.id != deal.owner_id:
        await _check_team_permission_for_action(db, deal, user, "submit_creative")

    # Mark previous versions as not current
    prev_result = await db.execute(
        select(CreativeVersion).where(
            CreativeVersion.deal_id == deal_id, CreativeVersion.is_current == True
        )  # noqa: E712
    )
    for prev in prev_result.scalars().all():
        prev.is_current = False

    # Get next version number
    max_version_result = await db.execute(
        select(func.coalesce(func.max(CreativeVersion.version), 0)).where(
            CreativeVersion.deal_id == deal_id
        )
    )
    next_version = max_version_result.scalar() + 1

    creative = CreativeVersion(
        deal_id=deal_id,
        version=next_version,
        text=text,
        entities_json=entities_json,
        media_items=media_items or None,
        status="submitted",
        is_current=True,
    )
    db.add(creative)

    # Transition deal: submit_creative
    deal = await transition_deal(db, deal_id, "submit_creative", user)

    await db.refresh(creative)

    # Send the creative content to the advertiser's bot chat
    from app.services.notification import notify_creative_submitted

    await notify_creative_submitted(deal, creative)

    return creative


async def approve_creative(
    db: AsyncSession,
    deal_id: int,
    user: User,
) -> CreativeVersion:
    """Advertiser approves the current creative version."""
    deal = await get_deal(db, deal_id, user.id)

    if deal.status != "CREATIVE_SUBMITTED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot approve creative in status {deal.status}",
        )

    actor = await _actor_for_user(db, deal, user.id)
    if actor != "advertiser":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the advertiser can approve creatives",
        )

    creative = await get_current_creative(db, deal_id)
    if not creative:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No current creative version found",
        )

    creative.status = "approved"

    # Transition deal: approve_creative
    deal = await transition_deal(db, deal_id, "approve_creative", user)

    await db.refresh(creative)
    return creative


async def request_changes(
    db: AsyncSession,
    deal_id: int,
    user: User,
    feedback: str,
) -> CreativeVersion:
    """Advertiser requests changes to the current creative version."""
    deal = await get_deal(db, deal_id, user.id)

    if deal.status != "CREATIVE_SUBMITTED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot request changes in status {deal.status}",
        )

    actor = await _actor_for_user(db, deal, user.id)
    if actor != "advertiser":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the advertiser can request changes",
        )

    creative = await get_current_creative(db, deal_id)
    if not creative:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No current creative version found",
        )

    creative.status = "changes_requested"
    creative.feedback = feedback

    # Transition deal: request_changes
    deal = await transition_deal(db, deal_id, "request_changes", user)

    await db.refresh(creative)

    # Send the feedback to the owner's bot chat
    from app.services.notification import notify_creative_changes_requested

    await notify_creative_changes_requested(deal, creative)

    return creative


async def get_current_creative(
    db: AsyncSession,
    deal_id: int,
) -> CreativeVersion | None:
    """Return the current (latest active) creative version for a deal."""
    result = await db.execute(
        select(CreativeVersion)
        .where(CreativeVersion.deal_id == deal_id, CreativeVersion.is_current == True)  # noqa: E712
        .order_by(CreativeVersion.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_creative_history(
    db: AsyncSession,
    deal_id: int,
) -> list[CreativeVersion]:
    """Return all creative versions for a deal, ordered by version desc."""
    result = await db.execute(
        select(CreativeVersion)
        .where(CreativeVersion.deal_id == deal_id)
        .order_by(CreativeVersion.version.desc())
    )
    return list(result.scalars().all())
