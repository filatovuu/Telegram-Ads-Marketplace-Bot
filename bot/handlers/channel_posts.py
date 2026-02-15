"""Handler for channel_post and edited_channel_post updates.

When the bot is an admin of a channel, Telegram sends channel_post updates
for every new message. We store these in the backend for analytics.
"""

import logging
from datetime import datetime, timezone

import httpx
from aiogram import Router
from aiogram.types import Message

from app.config import settings

logger = logging.getLogger(__name__)

router = Router(name="channel_posts")


def _detect_post_type(message: Message) -> tuple[str, bool]:
    """Detect the post type and whether it has media."""
    if message.animation:
        return "animation", True
    if message.video_note:
        return "video_note", True
    if message.video:
        return "video", True
    if message.photo:
        return "photo", True
    if message.voice:
        return "voice", True
    if message.document:
        return "document", True
    if message.sticker:
        return "sticker", True
    if message.poll:
        return "poll", False
    if message.media_group_id:
        return "media_group", True
    return "text", False


def _extract_text(message: Message) -> str | None:
    """Extract text preview from a message (first 500 chars)."""
    text = message.text or message.caption
    if text:
        return text[:500]
    return None


async def _send_to_backend(message: Message, is_edit: bool = False) -> None:
    """Send channel post data to the backend internal API."""
    if not message.chat or not message.chat.id:
        return

    post_type, has_media = _detect_post_type(message)

    raw_edit_date = getattr(message, "edit_date", None)
    raw_date = getattr(message, "date", None)

    # aiogram may return datetime or int (Unix timestamp) depending on field
    def _to_iso(val) -> str | None:
        if val is None:
            return None
        if isinstance(val, datetime):
            return val.isoformat()
        if isinstance(val, (int, float)):
            return datetime.fromtimestamp(val, tz=timezone.utc).isoformat()
        return str(val)

    # aiogram 3.13 does not declare views/forward_count/reactions as model fields;
    # they land in model_extra.
    extras = message.model_extra or {}

    raw_views = extras.get("views")
    views: int | None = int(raw_views) if raw_views is not None else None

    # Reactions: sum total_count across all reaction types
    reactions_count: int | None = None
    reactions_data = extras.get("reactions")
    if reactions_data and isinstance(reactions_data, dict):
        results = reactions_data.get("results", [])
        reactions_count = sum(r.get("total_count", 0) for r in results if isinstance(r, dict))

    fwd_count = extras.get("forward_count")
    forward_count: int | None = int(fwd_count) if fwd_count is not None else None

    payload = {
        "telegram_channel_id": message.chat.id,
        "telegram_message_id": message.message_id,
        "post_type": post_type,
        "views": views,
        "text_preview": _extract_text(message),
        "date": _to_iso(raw_date),
        "edit_date": _to_iso(raw_edit_date),
        "has_media": has_media,
        "media_group_id": getattr(message, "media_group_id", None),
        "reactions_count": reactions_count,
        "forward_count": forward_count,
    }

    try:
        async with httpx.AsyncClient(
            base_url=settings.backend_url, timeout=5.0
        ) as client:
            resp = await client.post("/api/internal/bot/channel-post", json=payload)
            if resp.status_code != 200:
                logger.warning(
                    "Failed to store channel post (msg=%d, chat=%d): %s",
                    message.message_id,
                    message.chat.id,
                    resp.status_code,
                )
    except Exception:
        logger.exception(
            "Error sending channel post to backend (msg=%d, chat=%d)",
            message.message_id,
            message.chat.id,
        )


@router.channel_post()
async def on_channel_post(message: Message) -> None:
    """Capture new channel posts and store them in the backend."""
    try:
        await _send_to_backend(message)
    except Exception:
        logger.exception("Unhandled error in on_channel_post (msg=%d)", message.message_id)


@router.edited_channel_post()
async def on_edited_channel_post(message: Message) -> None:
    """Capture edited channel posts to update views and edit_date."""
    try:
        await _send_to_backend(message, is_edit=True)
    except Exception:
        logger.exception("Unhandled error in on_edited_channel_post (msg=%d)", message.message_id)
