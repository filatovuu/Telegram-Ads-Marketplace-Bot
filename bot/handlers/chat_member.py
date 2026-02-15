"""Handler for my_chat_member updates.

When the bot is added as an admin to a channel, Telegram sends a
my_chat_member update. We use this to auto-register the channel in the backend.
When the bot is removed/demoted, we update the bot_is_admin flag.
"""

import logging

import httpx
from aiogram import Router
from aiogram.types import ChatMemberUpdated

from app.config import settings

logger = logging.getLogger(__name__)

router = Router(name="chat_member")


def _is_channel(event: ChatMemberUpdated) -> bool:
    return event.chat.type == "channel"


def _is_admin(event: ChatMemberUpdated) -> bool:
    """Check if the bot currently has admin status (including re-confirmation)."""
    new = event.new_chat_member.status if event.new_chat_member else "left"
    return new in ("administrator", "creator")


def _lost_admin(event: ChatMemberUpdated) -> bool:
    old = event.old_chat_member.status if event.old_chat_member else "left"
    new = event.new_chat_member.status if event.new_chat_member else "left"
    return old in ("administrator", "creator") and new not in ("administrator", "creator")


@router.my_chat_member()
async def on_my_chat_member(event: ChatMemberUpdated) -> None:
    """Handle bot being added/removed as admin in a channel."""
    old_status = event.old_chat_member.status if event.old_chat_member else "left"
    new_status = event.new_chat_member.status if event.new_chat_member else "left"
    logger.info(
        "my_chat_member: chat=%d type=%s old=%s new=%s from_user=%s",
        event.chat.id,
        event.chat.type,
        old_status,
        new_status,
        event.from_user.id if event.from_user else None,
    )

    if not _is_channel(event):
        return

    if _lost_admin(event):
        await _handle_lost_admin(event)
    elif _is_admin(event):
        # Handles both new promotion and re-confirmation (admin → admin)
        await _handle_became_admin(event)


async def _handle_became_admin(event: ChatMemberUpdated) -> None:
    """Bot is admin — register/re-register channel in backend."""
    admin_id = event.from_user.id if event.from_user else None
    if admin_id is None:
        logger.warning("my_chat_member: no from_user, skipping (chat=%d)", event.chat.id)
        return

    payload = {
        "telegram_channel_id": event.chat.id,
        "title": event.chat.title or "",
        "username": event.chat.username,
        "admin_telegram_id": admin_id,
    }

    try:
        async with httpx.AsyncClient(
            base_url=settings.backend_url, timeout=10.0
        ) as client:
            resp = await client.post(
                "/api/internal/bot/register-channel", json=payload
            )
            if resp.status_code in (200, 201):
                logger.info(
                    "Channel registered: %s (chat=%d, admin=%d)",
                    event.chat.title,
                    event.chat.id,
                    admin_id,
                )
            else:
                logger.warning(
                    "Failed to register channel (chat=%d): %s %s",
                    event.chat.id,
                    resp.status_code,
                    resp.text,
                )
    except Exception:
        logger.exception("Error registering channel (chat=%d)", event.chat.id)


async def _handle_lost_admin(event: ChatMemberUpdated) -> None:
    """Bot was removed/demoted — update bot_is_admin flag."""
    payload = {
        "telegram_channel_id": event.chat.id,
        "bot_is_admin": False,
    }

    try:
        async with httpx.AsyncClient(
            base_url=settings.backend_url, timeout=5.0
        ) as client:
            resp = await client.post(
                "/api/internal/bot/update-channel-bot-status", json=payload
            )
            if resp.status_code == 200:
                logger.info(
                    "Channel bot status updated to not-admin: %s (chat=%d)",
                    event.chat.title,
                    event.chat.id,
                )
            else:
                logger.warning(
                    "Failed to update channel bot status (chat=%d): %s",
                    event.chat.id,
                    resp.status_code,
                )
    except Exception:
        logger.exception("Error updating channel bot status (chat=%d)", event.chat.id)
