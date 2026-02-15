import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sqlalchemy import or_

from app.api.schemas import ChannelUpdate, TeamMemberAdd, TeamMemberUpdate
from app.models.channel import Channel
from app.models.channel_team import ChannelTeamMember
from app.models.user import User
from app.services import telegram
from app.services.team_permissions import get_team_membership
from app.services.user import get_user_by_telegram_id

logger = logging.getLogger(__name__)


async def _check_bot_is_admin(chat_id: int | str) -> bool:
    """Check whether our bot is an admin in the channel."""
    try:
        bot = await telegram.get_me()
        member = await telegram.get_chat_member(chat_id, bot["id"])
        return member.get("status") in ("administrator", "creator")
    except ValueError:
        return False


async def create_channel(db: AsyncSession, owner: User, username: str) -> Channel:
    """Add a channel: verify ownership + bot admin via Telegram API, fetch stats, persist."""
    clean_username = username.lstrip("@")
    chat_id = f"@{clean_username}"

    # 0. Owner must have a wallet connected
    if not owner.wallet_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please connect your TON wallet before adding a channel. "
            "Go to Profile → Connect Wallet.",
        )

    # 1. Fetch chat info — check that the channel exists
    try:
        chat = await telegram.get_chat(chat_id)
    except ValueError as exc:
        error_msg = str(exc).lower()
        if "not found" in error_msg or "bad request" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Channel @{clean_username} not found. "
                    "Check the username and make sure the channel is public."
                ),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch channel info: {exc}",
        ) from exc

    # 2. Verify the user is an admin/creator of the channel
    try:
        member = await telegram.get_chat_member(chat_id, owner.telegram_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot verify your admin status in @{clean_username}. "
                "Make sure the channel is public or the bot has access."
            ),
        ) from exc

    if member.get("status") not in ("creator", "administrator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"You are not an admin of @{clean_username}. "
                "You must be the creator or an administrator of the channel to add it."
            ),
        )

    # 3. Verify bot is an admin of the channel
    bot_is_admin = await _check_bot_is_admin(chat_id)
    if not bot_is_admin:
        bot = await telegram.get_me()
        bot_username = bot.get("username", "the bot")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Bot @{bot_username} is not an administrator of @{clean_username}. "
                f"Please add @{bot_username} as an admin to the channel, then try again."
            ),
        )

    # 4. Check if channel is already registered
    existing = await db.execute(
        select(Channel).where(Channel.telegram_channel_id == chat["id"])
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Channel @{clean_username} is already registered in the marketplace. "
                "Each channel can only be added once."
            ),
        )

    # 5. Fetch subscriber count
    try:
        subscribers = await telegram.get_chat_member_count(chat_id)
    except ValueError:
        subscribers = 0

    channel = Channel(
        telegram_channel_id=chat["id"],
        username=chat.get("username"),
        title=chat.get("title", ""),
        description=chat.get("description"),
        invite_link=chat.get("invite_link"),
        subscribers=subscribers,
        avg_views=0,
        language=None,
        is_verified=True,
        bot_is_admin=True,
        owner_id=owner.id,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)

    from app.workers.tasks import collect_single_channel_stats

    collect_single_channel_stats.delay(channel.id)

    return channel


async def create_channel_from_bot_event(
    db: AsyncSession,
    *,
    telegram_channel_id: int,
    title: str,
    username: str | None,
    admin_telegram_id: int,
) -> Channel:
    """Register a channel from a my_chat_member bot event (bot became admin)."""
    owner = await get_user_by_telegram_id(db, admin_telegram_id)
    if owner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin user not found. They need to open the bot first.",
        )

    # Check if channel already registered
    existing = await db.execute(
        select(Channel).where(Channel.telegram_channel_id == telegram_channel_id)
    )
    channel = existing.scalar_one_or_none()

    if channel is not None:
        if channel.owner_id == owner.id:
            # Same owner — just re-enable bot_is_admin
            channel.bot_is_admin = True
            await db.commit()
            await db.refresh(channel)
            return channel
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Channel is already registered by another owner.",
        )

    # Fetch additional info via Bot API
    chat_id = f"@{username}" if username else telegram_channel_id
    description = None
    invite_link = None
    subscribers = 0
    try:
        chat = await telegram.get_chat(chat_id)
        description = chat.get("description")
        invite_link = chat.get("invite_link")
    except ValueError:
        pass
    try:
        subscribers = await telegram.get_chat_member_count(chat_id)
    except ValueError:
        pass

    channel = Channel(
        telegram_channel_id=telegram_channel_id,
        username=username,
        title=title,
        description=description,
        invite_link=invite_link,
        subscribers=subscribers,
        avg_views=0,
        language=None,
        is_verified=True,
        bot_is_admin=True,
        owner_id=owner.id,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)

    from app.workers.tasks import collect_single_channel_stats

    collect_single_channel_stats.delay(channel.id)

    return channel


async def update_bot_admin_status(
    db: AsyncSession, *, telegram_channel_id: int, bot_is_admin: bool
) -> None:
    """Update bot_is_admin flag when bot is added/removed from a channel."""
    result = await db.execute(
        select(Channel).where(Channel.telegram_channel_id == telegram_channel_id)
    )
    channel = result.scalar_one_or_none()
    if channel is None:
        return  # Channel not registered — ignore
    channel.bot_is_admin = bot_is_admin
    await db.commit()


async def get_channels_by_owner(
    db: AsyncSession,
    user_id: int,
    offset: int = 0,
    limit: int = 50,
) -> list[Channel]:
    """Return channels where the user is owner OR team member."""
    result = await db.execute(
        select(Channel)
        .outerjoin(
            ChannelTeamMember,
            (ChannelTeamMember.channel_id == Channel.id)
            & (ChannelTeamMember.user_id == user_id),
        )
        .where(or_(Channel.owner_id == user_id, ChannelTeamMember.user_id == user_id))
        .order_by(Channel.id)
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().unique().all())


async def get_channel(
    db: AsyncSession,
    channel_id: int,
    user_id: int,
    *,
    owner_only: bool = False,
) -> Channel:
    """Fetch a channel by ID. Access granted to owner or team members.

    If owner_only=True, only the channel owner can access (for destructive ops).
    """
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found"
        )

    if channel.owner_id == user_id:
        return channel

    if owner_only:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found"
        )

    member = await get_team_membership(db, channel_id, user_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found"
        )

    return channel


async def update_channel(
    db: AsyncSession, channel: Channel, data: ChannelUpdate
) -> Channel:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(channel, field, value)
    await db.commit()
    await db.refresh(channel)
    return channel


async def count_active_deals_for_channel(
    db: AsyncSession,
    channel_id: int,
) -> int:
    """Count non-terminal deals linked to this channel's listings."""
    from app.models.deal import Deal
    from app.models.listing import Listing
    from app.services.deal_state_machine import TERMINAL_STATUSES
    from sqlalchemy import func

    result = await db.execute(
        select(func.count(Deal.id))
        .join(Listing, Deal.listing_id == Listing.id)
        .where(
            Listing.channel_id == channel_id,
            Deal.status.notin_([s.value for s in TERMINAL_STATUSES]),
        )
    )
    return result.scalar_one()


async def delete_channel_with_deals(
    db: AsyncSession,
    channel: Channel,
) -> int:
    """Cancel/refund all active deals for this channel, then delete the channel.

    Returns the number of deals that were cancelled or refunded.
    """
    from app.models.deal import Deal
    from app.models.listing import Listing
    from app.services.deal import system_transition_deal
    from app.services.deal_state_machine import (
        DealStatus,
        TERMINAL_STATUSES,
    )

    # Pre-escrow statuses → cancel
    PRE_ESCROW = {
        DealStatus.DRAFT,
        DealStatus.NEGOTIATION,
        DealStatus.OWNER_ACCEPTED,
        DealStatus.AWAITING_ESCROW_PAYMENT,
    }
    # Post-escrow statuses → refund (directly)
    POST_ESCROW_REFUND = {
        DealStatus.ESCROW_FUNDED,
        DealStatus.CREATIVE_PENDING_OWNER,
        DealStatus.CREATIVE_SUBMITTED,
        DealStatus.CREATIVE_CHANGES_REQUESTED,
        DealStatus.CREATIVE_APPROVED,
        DealStatus.SCHEDULED,
        DealStatus.RETENTION_CHECK,
    }

    result = await db.execute(
        select(Deal)
        .join(Listing, Deal.listing_id == Listing.id)
        .where(
            Listing.channel_id == channel.id,
            Deal.status.notin_([s.value for s in TERMINAL_STATUSES]),
        )
    )
    active_deals = list(result.scalars().all())

    handled = 0
    for deal in active_deals:
        try:
            deal_status = DealStatus(deal.status)
        except ValueError:
            continue

        try:
            if deal_status in PRE_ESCROW:
                await system_transition_deal(db, deal.id, "cancel")
                handled += 1
            elif deal_status == DealStatus.POSTED:
                # Two-step: start_retention → refund
                await system_transition_deal(db, deal.id, "start_retention")
                await system_transition_deal(db, deal.id, "refund")
                handled += 1
            elif deal_status in POST_ESCROW_REFUND:
                await system_transition_deal(db, deal.id, "refund")
                handled += 1
        except Exception:
            logger.exception(
                "Failed to transition deal %d during channel deletion", deal.id
            )

    await db.delete(channel)
    await db.commit()
    return handled


async def delete_channel(db: AsyncSession, channel: Channel) -> None:
    await db.delete(channel)
    await db.commit()


async def refresh_channel_stats(db: AsyncSession, channel: Channel) -> Channel:
    """Re-fetch channel stats from Telegram and check bot admin status."""
    chat_id = (
        f"@{channel.username}" if channel.username else channel.telegram_channel_id
    )

    try:
        chat = await telegram.get_chat(chat_id)
        channel.title = chat.get("title", channel.title)
        channel.description = chat.get("description")
        channel.invite_link = chat.get("invite_link")
    except ValueError:
        pass

    try:
        channel.subscribers = await telegram.get_chat_member_count(chat_id)
    except ValueError:
        pass

    # Re-check bot admin status
    channel.bot_is_admin = await _check_bot_is_admin(chat_id)

    await db.commit()
    await db.refresh(channel)
    return channel


# ---------------------------------------------------------------------------
# Team management
# ---------------------------------------------------------------------------


async def get_team_members(
    db: AsyncSession, channel_id: int
) -> list[ChannelTeamMember]:
    result = await db.execute(
        select(ChannelTeamMember)
        .where(ChannelTeamMember.channel_id == channel_id)
        .options(selectinload(ChannelTeamMember.user))
    )
    return list(result.scalars().all())


async def add_team_member(
    db: AsyncSession, channel: Channel, data: TeamMemberAdd
) -> ChannelTeamMember:
    # Find user by username
    user = await _find_user_by_username(db, data.username)

    # Check duplicate
    existing = await db.execute(
        select(ChannelTeamMember).where(
            ChannelTeamMember.channel_id == channel.id,
            ChannelTeamMember.user_id == user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"@{data.username.lstrip('@')} is already a team member of this channel.",
        )

    # Viewers cannot have elevated permissions
    is_viewer = data.role == "viewer"

    # can_payout requires Telegram admin rights in the channel
    can_payout = False if is_viewer else data.can_payout
    if can_payout:
        from app.services.team_permissions import check_telegram_admin_cached

        is_tg_admin = await check_telegram_admin_cached(
            channel.telegram_channel_id, user.telegram_id
        )
        if not is_tg_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Manage payouts requires Telegram admin rights in the channel.",
            )

    member = ChannelTeamMember(
        channel_id=channel.id,
        user_id=user.id,
        role=data.role,
        can_accept_deals=False if is_viewer else data.can_accept_deals,
        can_post=False if is_viewer else data.can_post,
        can_payout=can_payout,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member, attribute_names=["user"])

    from app.services.audit import log_audit

    await log_audit(
        db,
        action="team_add",
        entity_type="channel_team",
        entity_id=member.id,
        user_id=channel.owner_id,
        details={"username": data.username, "role": data.role},
    )

    return member


async def remove_team_member(
    db: AsyncSession, channel: Channel, member_id: int
) -> None:
    result = await db.execute(
        select(ChannelTeamMember).where(
            ChannelTeamMember.id == member_id,
            ChannelTeamMember.channel_id == channel.id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found",
        )

    from app.services.audit import log_audit

    await log_audit(
        db,
        action="team_remove",
        entity_type="channel_team",
        entity_id=member_id,
        user_id=channel.owner_id,
        details={"removed_user_id": member.user_id},
    )

    await db.delete(member)
    await db.commit()


async def update_team_member(
    db: AsyncSession,
    channel: Channel,
    member_id: int,
    data: TeamMemberUpdate,
) -> ChannelTeamMember:
    """Update a team member's role and/or permissions. Owner only."""
    result = await db.execute(
        select(ChannelTeamMember)
        .where(
            ChannelTeamMember.id == member_id,
            ChannelTeamMember.channel_id == channel.id,
        )
        .options(selectinload(ChannelTeamMember.user))
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found"
        )

    updates = data.model_dump(exclude_unset=True)

    # If changing role to viewer, clear all permission bools
    if updates.get("role") == "viewer":
        member.can_accept_deals = False
        member.can_post = False
        member.can_payout = False

    # can_payout requires Telegram admin rights in the channel
    if updates.get("can_payout"):
        from app.services.team_permissions import check_telegram_admin_cached

        is_tg_admin = await check_telegram_admin_cached(
            channel.telegram_channel_id, member.user.telegram_id
        )
        if not is_tg_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Manage payouts requires Telegram admin rights in the channel.",
            )

    for field, value in updates.items():
        setattr(member, field, value)

    await db.commit()
    await db.refresh(member, attribute_names=["user"])

    from app.services.audit import log_audit

    await log_audit(
        db,
        action="team_update",
        entity_type="channel_team",
        entity_id=member_id,
        user_id=channel.owner_id,
        details=updates,
    )

    return member


async def _find_user_by_username(db: AsyncSession, username: str) -> User:
    """Find a user by their Telegram username (stored in DB)."""
    clean = username.lstrip("@")
    result = await db.execute(select(User).where(User.username == clean))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"User @{clean} not found. "
                "They need to open the bot first by sending /start."
            ),
        )
    return user
