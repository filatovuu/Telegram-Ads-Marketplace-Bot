"""Team permission checks — central authorization for channel team members."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set, make_cache_key
from app.models.channel import Channel
from app.models.channel_team import ChannelTeamMember
from app.services import telegram

logger = logging.getLogger(__name__)


async def get_team_membership(
    db: AsyncSession, channel_id: int, user_id: int
) -> ChannelTeamMember | None:
    """Return team membership for a user in a channel, or None."""
    result = await db.execute(
        select(ChannelTeamMember).where(
            ChannelTeamMember.channel_id == channel_id,
            ChannelTeamMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_user_role_for_channel(
    db: AsyncSession, channel: Channel, user_id: int
) -> tuple[str | None, ChannelTeamMember | None]:
    """Return (role, membership) for a user on a channel.

    Returns:
        ("owner", None)        — the channel owner
        ("manager", member)    — a team member with role=manager
        ("viewer", member)     — a team member with role=viewer
        (None, None)           — no access
    """
    if channel.owner_id == user_id:
        return "owner", None
    member = await get_team_membership(db, channel.id, user_id)
    if member is None:
        return None, None
    return member.role, member


def has_permission(
    role: str, member: ChannelTeamMember | None, permission: str
) -> bool:
    """Check if a role+member has a specific permission.

    Owner has all permissions unconditionally.
    Manager checks the boolean flag on the member record.
    Viewer always returns False.
    """
    if role == "owner":
        return True
    if role == "viewer" or member is None:
        return False
    # role == "manager"
    return bool(getattr(member, permission, False))


async def check_telegram_admin_cached(
    telegram_channel_id: int, user_telegram_id: int
) -> bool:
    """Check if a user is a Telegram admin in a channel, cached for 60s in Redis."""
    cache_key = make_cache_key(
        "tg_admin", str(telegram_channel_id), str(user_telegram_id)
    )
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached == "1"

    try:
        member = await telegram.get_chat_member(telegram_channel_id, user_telegram_id)
        is_admin = member.get("status") in ("creator", "administrator")
    except Exception:
        logger.warning(
            "Telegram admin check failed for user %d in channel %d",
            user_telegram_id,
            telegram_channel_id,
        )
        is_admin = False

    await cache_set(cache_key, "1" if is_admin else "0", ttl=60)
    return is_admin
