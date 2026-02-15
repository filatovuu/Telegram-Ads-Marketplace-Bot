"""MTProto client (Pyrogram) for enhanced channel post analytics.

Provides views, forwards, and reactions data that Bot API cannot reliably deliver.
All functions degrade gracefully — if MTProto is not configured or encounters errors,
the system continues with Bot API data only.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.channel import Channel
from app.models.channel_post import ChannelPost
from app.models.post_view_snapshot import PostViewSnapshot

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PostData dataclass
# ---------------------------------------------------------------------------


@dataclass
class PostData:
    telegram_message_id: int
    views: int | None
    forward_count: int | None
    reactions_count: int | None
    date: datetime | None
    edit_date: datetime | None
    text_preview: str | None
    has_media: bool
    post_type: str


# ---------------------------------------------------------------------------
# Singleton client
# ---------------------------------------------------------------------------

_client = None
_client_lock = asyncio.Lock()


async def get_client():
    """Return a connected Pyrogram Client, or None if not configured."""
    global _client

    if not settings.mtproto_configured:
        return None

    async with _client_lock:
        if _client is not None:
            if _client.is_connected:
                return _client
            # Connection lost — reset and reconnect
            _client = None

        from pyrogram import Client

        client = Client(
            name="marketplace_stats",
            api_id=settings.mtproto_api_id,
            api_hash=settings.mtproto_api_hash,
            session_string=settings.mtproto_session_string,
            in_memory=True,
            no_updates=True,
        )
        await client.start()
        logger.info("MTProto client connected")
        _client = client
        return _client


async def stop_client() -> None:
    """Gracefully disconnect the MTProto client."""
    global _client
    if _client is not None:
        try:
            await _client.stop()
            logger.info("MTProto client disconnected")
        except Exception:
            logger.exception("Error stopping MTProto client")
        finally:
            _client = None


# ---------------------------------------------------------------------------
# Extract post data from Pyrogram Message
# ---------------------------------------------------------------------------


def _detect_post_type(msg) -> str:
    """Detect post type from a Pyrogram Message object."""
    if not msg.media:
        return "text"
    try:
        from pyrogram import enums

        media_map = {
            enums.MessageMediaType.PHOTO: "photo",
            enums.MessageMediaType.VIDEO: "video",
            enums.MessageMediaType.DOCUMENT: "document",
            enums.MessageMediaType.AUDIO: "audio",
            enums.MessageMediaType.VOICE: "voice",
            enums.MessageMediaType.VIDEO_NOTE: "video_note",
            enums.MessageMediaType.ANIMATION: "animation",
            enums.MessageMediaType.STICKER: "sticker",
            enums.MessageMediaType.POLL: "poll",
        }
        return media_map.get(msg.media, "other")
    except ImportError:
        # Pyrogram not installed — fall back to string representation
        media_str = str(msg.media).lower()
        for kind in ("photo", "video", "document", "audio", "voice", "animation", "sticker", "poll"):
            if kind in media_str:
                return kind
        return "other"


def _extract_post_data(msg) -> PostData:
    """Map a Pyrogram Message to a PostData dataclass."""
    reactions_count = None
    if msg.reactions and msg.reactions.reactions:
        reactions_count = sum(r.count for r in msg.reactions.reactions)

    text = msg.text or msg.caption or None
    text_preview = text[:500] if text else None

    date = msg.date
    if date and date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)

    edit_date = msg.edit_date
    if edit_date and edit_date.tzinfo is None:
        edit_date = edit_date.replace(tzinfo=timezone.utc)

    return PostData(
        telegram_message_id=msg.id,
        views=msg.views,
        forward_count=msg.forwards,
        reactions_count=reactions_count,
        date=date,
        edit_date=edit_date,
        text_preview=text_preview,
        has_media=msg.media is not None,
        post_type=_detect_post_type(msg),
    )


# ---------------------------------------------------------------------------
# Fetch channel posts via MTProto
# ---------------------------------------------------------------------------


async def fetch_channel_posts(chat_id: int | str, limit: int = 100) -> list[PostData]:
    """Fetch recent posts from a channel using MTProto.

    Returns an empty list on any error (graceful degradation).
    """
    client = await get_client()
    if client is None:
        logger.debug("MTProto not configured, skipping fetch for %s", chat_id)
        return []

    from pyrogram.errors import ChannelPrivate, ChatAdminRequired, FloodWait

    logger.info("MTProto fetching up to %d posts for %s", limit, chat_id)
    try:
        posts: list[PostData] = []
        async for msg in client.get_chat_history(chat_id, limit=limit):
            if msg.empty or msg.service:
                continue
            posts.append(_extract_post_data(msg))
        views_count = sum(1 for p in posts if p.views is not None)
        logger.info("MTProto fetched %d posts (%d with views) for %s", len(posts), views_count, chat_id)
        return posts
    except FloodWait as e:
        logger.warning("MTProto FloodWait: sleeping %d seconds", e.value)
        await asyncio.sleep(e.value)
        # Single retry after flood wait
        try:
            posts = []
            async for msg in client.get_chat_history(chat_id, limit=limit):
                if msg.empty or msg.service:
                    continue
                posts.append(_extract_post_data(msg))
            return posts
        except Exception:
            logger.exception("MTProto retry failed for chat %s", chat_id)
            return []
    except (ChannelPrivate, ChatAdminRequired) as e:
        logger.warning("MTProto access denied for chat %s: %s", chat_id, e)
        return []
    except Exception:
        logger.exception("MTProto fetch failed for chat %s", chat_id)
        return []


# ---------------------------------------------------------------------------
# Read a single message by ID (for retention verification)
# ---------------------------------------------------------------------------


async def get_message(chat_id: int | str, message_id: int) -> PostData | None:
    """Read a single channel message by ID via MTProto.

    Returns PostData if the message exists and is a regular post,
    None if the message was deleted, is inaccessible, or MTProto is not configured.
    """
    client = await get_client()
    if client is None:
        return None

    from pyrogram.errors import ChannelPrivate, ChatAdminRequired, FloodWait

    try:
        msg = await client.get_messages(chat_id, message_id)
        if msg is None or msg.empty:
            return None
        return _extract_post_data(msg)
    except FloodWait as e:
        logger.warning("MTProto FloodWait: sleeping %d seconds", e.value)
        await asyncio.sleep(e.value)
        try:
            msg = await client.get_messages(chat_id, message_id)
            if msg is None or msg.empty:
                return None
            return _extract_post_data(msg)
        except Exception:
            logger.exception("MTProto retry failed for get_message(%s, %s)", chat_id, message_id)
            return None
    except (ChannelPrivate, ChatAdminRequired) as e:
        logger.warning("MTProto access denied for chat %s: %s", chat_id, e)
        return None
    except Exception:
        logger.exception("MTProto get_message failed for chat %s msg %s", chat_id, message_id)
        return None


# ---------------------------------------------------------------------------
# Enrich channel posts in database
# ---------------------------------------------------------------------------


async def enrich_channel_posts(
    db: AsyncSession, channel: Channel, limit: int = 100
) -> int:
    """Fetch posts via MTProto and update/create ChannelPost rows.

    Returns the number of posts enriched. Uses flush() — caller owns the transaction.
    """
    # Use @username for Pyrogram — it can resolve usernames without cached peers.
    # Numeric IDs require the peer to be in the session cache, which is empty
    # for fresh session strings.
    chat_id: int | str = (
        f"@{channel.username}" if channel.username else channel.telegram_channel_id
    )

    posts = await fetch_channel_posts(chat_id, limit=limit)
    if not posts:
        return 0

    enriched = 0
    now = datetime.now(timezone.utc)

    for post_data in posts:
        # Find existing post
        result = await db.execute(
            select(ChannelPost).where(
                ChannelPost.channel_id == channel.id,
                ChannelPost.telegram_message_id == post_data.telegram_message_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            changed = False

            # Only update views if new value is higher (views only go up)
            if post_data.views is not None and (
                existing.views is None or post_data.views > existing.views
            ):
                existing.views = post_data.views
                changed = True

            if post_data.reactions_count is not None:
                existing.reactions_count = post_data.reactions_count
                changed = True

            if post_data.forward_count is not None:
                existing.forward_count = post_data.forward_count
                changed = True

            if post_data.edit_date is not None and existing.edit_date is None:
                existing.edit_date = post_data.edit_date
                changed = True

            # Record view snapshot when views changed
            if changed and post_data.views is not None:
                db.add(PostViewSnapshot(
                    post_id=existing.id,
                    views=post_data.views,
                    recorded_at=now,
                ))
                enriched += 1
        else:
            # Backfill: create new post
            if post_data.date is None:
                continue

            new_post = ChannelPost(
                channel_id=channel.id,
                telegram_message_id=post_data.telegram_message_id,
                post_type=post_data.post_type,
                views=post_data.views,
                text_preview=post_data.text_preview,
                date=post_data.date,
                edit_date=post_data.edit_date,
                has_media=post_data.has_media,
                reactions_count=post_data.reactions_count,
                forward_count=post_data.forward_count,
            )
            db.add(new_post)

            # Flush to get the ID for snapshot
            if post_data.views is not None:
                await db.flush()
                db.add(PostViewSnapshot(
                    post_id=new_post.id,
                    views=post_data.views,
                    recorded_at=now,
                ))
            enriched += 1

    await db.flush()
    logger.info("MTProto enriched %d posts for channel %s", enriched, channel.id)
    return enriched
