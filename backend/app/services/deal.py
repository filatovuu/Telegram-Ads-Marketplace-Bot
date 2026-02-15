from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas import DealCreate, DealUpdate, OwnerDealCreate
from app.models.campaign import Campaign
from app.models.channel import Channel
from app.models.deal import Deal
from app.models.deal_amendment import DealAmendment
from app.models.deal_message import DealMessage
from app.models.listing import Listing
from app.models.user import User
from app.services.deal_state_machine import (
    DealStatus,
    InvalidTransitionError,
    MESSAGING_STATUSES,
    get_available_actions,
    validate_transition,
)


async def create_deal_from_listing(
    db: AsyncSession, advertiser: User, data: DealCreate
) -> Deal:
    # Verify listing exists & is_active
    result = await db.execute(
        select(Listing)
        .where(Listing.id == data.listing_id, Listing.is_active == True)  # noqa: E712
        .options(selectinload(Listing.channel))
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found or not active",
        )

    owner_id = listing.channel.owner_id

    now = datetime.now(timezone.utc)
    deal = Deal(
        listing_id=data.listing_id,
        advertiser_id=advertiser.id,
        owner_id=owner_id,
        status="DRAFT",
        price=data.price,
        currency=data.currency,
        brief=data.brief,
        publish_from=data.publish_from,
        publish_to=data.publish_to,
        last_activity_at=now,
    )
    db.add(deal)
    await db.commit()
    await db.refresh(deal)
    return deal


async def create_deal_from_campaign(
    db: AsyncSession, owner: User, data: OwnerDealCreate
) -> Deal:
    # Verify campaign exists & is_active
    result = await db.execute(
        select(Campaign).where(
            Campaign.id == data.campaign_id,
            Campaign.is_active == True,  # noqa: E712
        )
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found or not active",
        )

    # Verify listing exists, is_active, and belongs to the owner
    result = await db.execute(
        select(Listing)
        .where(Listing.id == data.listing_id, Listing.is_active == True)  # noqa: E712
        .options(selectinload(Listing.channel))
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found or not active",
        )
    if listing.channel.owner_id != owner.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This listing does not belong to you",
        )

    # Validate price is within campaign budget range
    if data.price < campaign.budget_min or data.price > campaign.budget_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Price must be between {campaign.budget_min} and {campaign.budget_max}",
        )

    now = datetime.now(timezone.utc)
    deal = Deal(
        listing_id=data.listing_id,
        campaign_id=data.campaign_id,
        advertiser_id=campaign.advertiser_id,
        owner_id=owner.id,
        status="NEGOTIATION",
        price=data.price,
        currency=data.currency,
        brief=data.brief,
        publish_from=data.publish_from,
        publish_to=data.publish_to,
        last_activity_at=now,
    )
    db.add(deal)
    await db.flush()

    sys_msg = DealMessage(
        deal_id=deal.id,
        sender_user_id=None,
        text="Deal proposed by owner — awaiting advertiser approval",
        message_type="system",
    )
    db.add(sys_msg)
    await db.commit()
    await db.refresh(deal)

    # Notify advertiser about the proposal
    from app.services.notification import notify_deal_proposal

    await notify_deal_proposal(deal)

    return deal


async def get_deals_by_user(
    db: AsyncSession,
    user_id: int,
    role: str = "advertiser",
    offset: int = 0,
    limit: int = 50,
) -> list[Deal]:
    if role == "owner":
        from app.models.channel_team import ChannelTeamMember

        # Channel IDs the user has access to (owner or team member)
        team_channel_ids = select(ChannelTeamMember.channel_id).where(
            ChannelTeamMember.user_id == user_id
        )
        owned_channel_ids = select(Channel.id).where(Channel.owner_id == user_id)
        accessible_channel_ids = team_channel_ids.union(owned_channel_ids)

        condition = and_(
            or_(
                Deal.owner_id == user_id,
                Deal.listing_id.in_(
                    select(Listing.id).where(
                        Listing.channel_id.in_(accessible_channel_ids)
                    )
                ),
            ),
            or_(
                Deal.status != "DRAFT",
                Deal.campaign_id.isnot(None),
            ),
        )
    else:
        # Hide DRAFT deals created by owner (from campaign) until sent
        condition = and_(
            Deal.advertiser_id == user_id,
            or_(
                Deal.status != "DRAFT",
                Deal.campaign_id.is_(None),
            ),
        )

    result = await db.execute(
        select(Deal)
        .where(condition)
        .order_by(Deal.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_deal(db: AsyncSession, deal_id: int, user_id: int) -> Deal:
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found"
        )
    # Hide DRAFT deals from the counter-party who hasn't seen them yet
    if deal.status == "DRAFT":
        # Owner-created DRAFT (campaign_id set) → hide from advertiser
        if deal.advertiser_id == user_id and deal.campaign_id is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found"
            )
        # Advertiser-created DRAFT (campaign_id NULL) → hide from owner
        if deal.owner_id == user_id and deal.campaign_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found"
            )
    if deal.advertiser_id != user_id and deal.owner_id != user_id:
        # Check team membership
        if deal.listing_id:
            from app.services.team_permissions import get_team_membership

            listing_result = await db.execute(
                select(Listing).where(Listing.id == deal.listing_id)
            )
            listing = listing_result.scalar_one_or_none()
            if listing:
                member = await get_team_membership(db, listing.channel_id, user_id)
                if member is not None:
                    return deal
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a participant in this deal",
        )
    return deal


async def _actor_for_user(db: AsyncSession, deal: Deal, user_id: int) -> str:
    """Determine the actor role of a user in a deal.

    Team members of the deal's channel are mapped to 'owner' actor.
    """
    if user_id == deal.advertiser_id:
        return "advertiser"
    if user_id == deal.owner_id:
        return "owner"

    # Check if user is a team member of the deal's channel
    if deal.listing_id:
        from app.services.team_permissions import get_team_membership

        listing_result = await db.execute(
            select(Listing).where(Listing.id == deal.listing_id)
        )
        listing = listing_result.scalar_one_or_none()
        if listing:
            member = await get_team_membership(db, listing.channel_id, user_id)
            if member is not None:
                return "owner"  # Team members act under OWNER actor in state machine

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You are not a participant in this deal",
    )


# Actions that require specific permission flags for team members
_ACTION_PERMISSIONS: dict[str, str] = {
    "accept": "can_accept_deals",
    "cancel": "can_accept_deals",
    "submit_creative": "can_post",
    "schedule": "can_post",
    "mark_posted": "can_post",
}


async def _check_team_permission_for_action(
    db: AsyncSession,
    deal: Deal,
    user: User,
    action: str,
) -> None:
    """Verify team member has required permission for this deal action.

    Also re-checks Telegram admin status for state-changing actions.
    """
    from app.services.team_permissions import (
        check_telegram_admin_cached,
        get_team_membership,
        has_permission,
    )

    # Actual owner bypasses all team permission checks
    if user.id == deal.owner_id:
        return

    listing_result = await db.execute(
        select(Listing).where(Listing.id == deal.listing_id)
    )
    listing = listing_result.scalar_one_or_none()
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="No channel access"
        )

    member = await get_team_membership(db, listing.channel_id, user.id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a team member"
        )

    role = member.role

    # Viewer cannot perform any actions
    if role == "viewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewers cannot perform deal actions",
        )

    # Check specific permission flag if action requires one
    required = _ACTION_PERMISSIONS.get(action)
    if required and not has_permission(role, member, required):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have the '{required}' permission for this action",
        )

    # Re-check Telegram admin status for all state-changing actions
    channel_result = await db.execute(
        select(Channel).where(Channel.id == listing.channel_id)
    )
    channel = channel_result.scalar_one_or_none()
    if channel:
        is_admin = await check_telegram_admin_cached(
            channel.telegram_channel_id, user.telegram_id
        )
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are no longer an admin of this channel in Telegram.",
            )


async def update_deal_brief(
    db: AsyncSession,
    deal_id: int,
    user: User,
    data: DealUpdate,
) -> Deal:
    """Update brief fields on a DRAFT deal (advertiser only)."""
    deal = await get_deal(db, deal_id, user.id)

    if deal.status != "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Brief can only be edited in DRAFT status",
        )
    if deal.advertiser_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the advertiser can edit the brief",
        )

    if data.brief is not None:
        deal.brief = data.brief
    if data.publish_from is not None:
        deal.publish_from = data.publish_from
    if data.publish_to is not None:
        deal.publish_to = data.publish_to

    deal.last_activity_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(deal)
    return deal


async def transition_deal(
    db: AsyncSession,
    deal_id: int,
    action: str,
    user: User,
) -> Deal:
    """Validate transition, update status + last_activity_at, add system message."""
    deal = await get_deal(db, deal_id, user.id)
    actor = await _actor_for_user(db, deal, user.id)

    # Permission gate for team members
    if user.id != deal.owner_id and user.id != deal.advertiser_id:
        await _check_team_permission_for_action(db, deal, user, action)

    # Owner must have wallet connected for payout-related actions only
    _WALLET_REQUIRED_ACTIONS = ("release", "refund")
    if (
        actor == "owner"
        and action in _WALLET_REQUIRED_ACTIONS
        and not user.wallet_address
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please connect your TON wallet to proceed. "
            "Go to Profile → Connect Wallet.",
        )

    # Creator cannot accept their own deal
    if action == "accept" and deal.status == "NEGOTIATION":
        is_creator = (deal.campaign_id is not None and actor == "owner") or (
            deal.campaign_id is None and actor == "advertiser"
        )
        if is_creator:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot accept your own proposal",
            )

    # Enforce brief required before sending to owner
    if action == "send" and not deal.brief:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Brief is required before sending the deal",
        )

    old_status = deal.status

    try:
        new_status = validate_transition(deal.status, action, actor)
    except InvalidTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    now = datetime.now(timezone.utc)
    deal.status = new_status.value
    deal.last_activity_at = now

    # Add system message about the transition
    sys_msg = DealMessage(
        deal_id=deal.id,
        sender_user_id=None,
        text=f"Status changed to {new_status.value} by {actor}",
        message_type="system",
    )
    db.add(sys_msg)

    # Audit log for significant transitions
    if action in ("cancel", "release", "refund"):
        from app.services.audit import log_audit

        await log_audit(
            db,
            action=f"deal_{action}",
            entity_type="deal",
            entity_id=deal.id,
            user_id=user.id,
            details={"from_status": deal.status, "to_status": new_status.value},
        )

    await db.commit()
    await db.refresh(deal)

    # Skip notification if the deal was in DRAFT — the other party doesn't know about it yet
    # Exception: the "send" action is when the advertiser explicitly sends the deal to the owner
    # For AWAITING_ESCROW_PAYMENT: don't send the generic "deposit now" message;
    # escrow_auto will send the right notification depending on wallet readiness.
    if old_status != "DRAFT" or action == "send":
        if new_status != DealStatus.AWAITING_ESCROW_PAYMENT:
            from app.services.notification import notify_deal_status_change

            await notify_deal_status_change(deal)

    # Auto-create escrow if both wallets are available
    if new_status == DealStatus.AWAITING_ESCROW_PAYMENT:
        from app.services.escrow_auto import try_auto_create_escrow

        await try_auto_create_escrow(db, deal)

    return deal


async def system_transition_deal(
    db: AsyncSession,
    deal_id: int,
    action: str,
    *,
    silent: bool = False,
) -> Deal:
    """System-initiated transition — no user auth required (for Celery tasks).

    Args:
        silent: If True, skip sending the generic status change notification.
                Used when the caller sends a custom notification instead.
    """
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found"
        )

    try:
        new_status = validate_transition(deal.status, action, "system")
    except InvalidTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    now = datetime.now(timezone.utc)
    deal.status = new_status.value
    deal.last_activity_at = now

    sys_msg = DealMessage(
        deal_id=deal.id,
        sender_user_id=None,
        text=f"Status changed to {new_status.value} by system",
        message_type="system",
    )
    db.add(sys_msg)

    await db.commit()
    await db.refresh(deal)

    if not silent:
        from app.services.notification import notify_deal_status_change

        await notify_deal_status_change(deal)

    # Auto-trigger: ESCROW_FUNDED → request_creative
    if new_status == DealStatus.ESCROW_FUNDED:
        deal = await system_transition_deal(db, deal_id, "request_creative")

    return deal


async def add_deal_message(
    db: AsyncSession,
    deal_id: int,
    user: User,
    text: str,
    media_items: list[dict] | None = None,
) -> DealMessage:
    """Add a text message to a deal — only during negotiation phases."""
    deal = await get_deal(db, deal_id, user.id)

    try:
        current_status = DealStatus(deal.status)
    except ValueError:
        current_status = None

    if current_status not in MESSAGING_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Messages are not allowed in this deal status",
        )

    now = datetime.now(timezone.utc)
    deal.last_activity_at = now

    msg = DealMessage(
        deal_id=deal.id,
        sender_user_id=user.id,
        text=text,
        message_type="text",
        media_items=media_items or None,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    # Fire-and-forget notification to the other party
    from app.services.notification import notify_deal_message

    recipient_id = (
        deal.owner_id if user.id == deal.advertiser_id else deal.advertiser_id
    )
    await notify_deal_message(deal, user, recipient_id, text, media_items=media_items)

    return msg


async def get_deal_messages(
    db: AsyncSession,
    deal_id: int,
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[DealMessage]:
    """Return messages for a deal (access-checked)."""
    await get_deal(db, deal_id, user_id)  # ownership check

    result = await db.execute(
        select(DealMessage)
        .where(DealMessage.deal_id == deal_id)
        .order_by(DealMessage.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_pending_amendment(
    db: AsyncSession,
    deal_id: int,
) -> DealAmendment | None:
    """Return the pending amendment for a deal, if any."""
    result = await db.execute(
        select(DealAmendment)
        .where(DealAmendment.deal_id == deal_id, DealAmendment.status == "pending")
        .order_by(DealAmendment.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_deal_detail(
    db: AsyncSession,
    deal_id: int,
    user_id: int,
) -> dict:
    """Return deal + messages + available_actions + pending_amendment + escrow for the frontend."""
    deal = await get_deal(db, deal_id, user_id)
    actor = await _actor_for_user(db, deal, user_id)
    actions = get_available_actions(deal.status, actor)

    # Hide "accept" from the deal creator (only counter-party can accept)
    if deal.status == "NEGOTIATION" and "accept" in actions:
        is_creator = (deal.campaign_id is not None and actor == "owner") or (
            deal.campaign_id is None and actor == "advertiser"
        )
        if is_creator:
            actions = [a for a in actions if a != "accept"]

    messages_result = await db.execute(
        select(DealMessage)
        .where(DealMessage.deal_id == deal_id)
        .order_by(DealMessage.created_at.asc())
        .limit(100)
    )
    messages = list(messages_result.scalars().all())

    pending_amendment = await get_pending_amendment(db, deal_id)

    # Fetch escrow if exists
    from app.models.escrow import Escrow

    escrow_result = await db.execute(select(Escrow).where(Escrow.deal_id == deal_id))
    escrow = escrow_result.scalar_one_or_none()

    # Fetch current creative and history
    from app.services.creative import get_current_creative, get_creative_history

    current_creative = await get_current_creative(db, deal_id)
    creative_history = await get_creative_history(db, deal_id)

    # Fetch posting record
    from app.services.posting import get_posting

    posting = await get_posting(db, deal_id)

    # Compute can_manage_wallet flag
    can_manage_wallet = False
    if actor == "owner":
        if user_id == deal.owner_id:
            can_manage_wallet = True
        elif deal.listing_id:
            from app.services.team_permissions import (
                get_team_membership,
                has_permission,
            )

            listing_result = await db.execute(
                select(Listing).where(Listing.id == deal.listing_id)
            )
            listing = listing_result.scalar_one_or_none()
            if listing:
                member = await get_team_membership(db, listing.channel_id, user_id)
                if member and member.role != "viewer":
                    can_manage_wallet = has_permission(
                        member.role, member, "can_payout"
                    )

    return {
        "deal": deal,
        "messages": messages,
        "available_actions": actions,
        "can_manage_wallet": can_manage_wallet,
        "pending_amendment": pending_amendment,
        "escrow": escrow,
        "current_creative": current_creative,
        "creative_history": creative_history,
        "posting": posting,
    }


async def get_deals_for_timeout(
    db: AsyncSession,
    before: datetime,
    statuses: list[str],
) -> list[Deal]:
    """Return deals in given statuses with last_activity_at older than `before`."""
    result = await db.execute(
        select(Deal).where(Deal.status.in_(statuses), Deal.last_activity_at < before)
    )
    return list(result.scalars().all())
