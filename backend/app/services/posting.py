"""Post scheduling, auto-posting, and retention verification."""

import json
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel import Channel
from app.models.deal import Deal
from app.models.deal_posting import DealPosting
from app.models.listing import Listing
from app.models.user import User
from app.services.creative import get_current_creative
from app.services.deal import (
    get_deal,
    transition_deal,
    system_transition_deal,
    _actor_for_user,
    _check_team_permission_for_action,
)
from app.services import telegram

logger = logging.getLogger(__name__)


async def schedule_post(
    db: AsyncSession,
    deal_id: int,
    user: User,
    scheduled_at: datetime,
) -> DealPosting:
    """Owner schedules the approved creative for posting."""
    deal = await get_deal(db, deal_id, user.id)

    if deal.status != "CREATIVE_APPROVED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot schedule post in status {deal.status}",
        )

    actor = await _actor_for_user(db, deal, user.id)
    if actor != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the channel owner or team managers can schedule posts",
        )

    # Team member permission check
    if user.id != deal.owner_id:
        await _check_team_permission_for_action(db, deal, user, "schedule")

    # Resolve channel from deal → listing → channel
    if not deal.listing_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Deal has no associated listing",
        )

    listing_result = await db.execute(
        select(Listing).where(Listing.id == deal.listing_id)
    )
    listing = listing_result.scalar_one_or_none()
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found",
        )

    channel_result = await db.execute(
        select(Channel).where(Channel.id == listing.channel_id)
    )
    channel = channel_result.scalar_one_or_none()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )

    # Check for existing posting
    existing = await db.execute(
        select(DealPosting).where(DealPosting.deal_id == deal_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Post is already scheduled for this deal",
        )

    # Timezone handling: if scheduled_at is naive, treat it as user's local time
    if scheduled_at.tzinfo is None:
        try:
            user_tz = ZoneInfo(user.timezone)
        except (KeyError, Exception):
            user_tz = ZoneInfo("UTC")
        scheduled_at = scheduled_at.replace(tzinfo=user_tz)

    # Convert to UTC for storage
    scheduled_at_utc = scheduled_at.astimezone(timezone.utc)

    posting = DealPosting(
        deal_id=deal_id,
        channel_id=channel.id,
        scheduled_at=scheduled_at_utc,
        retention_hours=deal.retention_hours,
    )
    db.add(posting)

    # Transition deal: schedule
    deal = await transition_deal(db, deal_id, "schedule", user)

    await db.refresh(posting)
    return posting


async def auto_post(db: AsyncSession, deal_id: int) -> DealPosting:
    """Execute the scheduled post — called by Celery worker."""
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise ValueError(f"Deal {deal_id} not found")

    creative = await get_current_creative(db, deal_id)
    if not creative:
        raise ValueError(f"No current creative for deal {deal_id}")

    posting_result = await db.execute(
        select(DealPosting).where(DealPosting.deal_id == deal_id)
    )
    posting = posting_result.scalar_one_or_none()
    if not posting:
        raise ValueError(f"No posting record for deal {deal_id}")

    channel_result = await db.execute(
        select(Channel).where(Channel.id == posting.channel_id)
    )
    channel = channel_result.scalar_one_or_none()
    if not channel:
        raise ValueError(f"Channel {posting.channel_id} not found")

    # Verify bot is still admin
    try:
        bot_info = await telegram.get_me()
        member = await telegram.get_chat_member(
            channel.telegram_channel_id, bot_info["id"]
        )
        if member.get("status") not in ("administrator", "creator"):
            raise ValueError(
                f"Bot is not admin in channel {channel.telegram_channel_id}"
            )
    except Exception:
        logger.exception("Bot admin check failed for deal %d", deal_id)
        raise

    # Parse entities if present
    entities = None
    if creative.entities_json:
        try:
            entities = json.loads(creative.entities_json)
        except json.JSONDecodeError:
            pass

    # Send based on media
    chat_id = channel.telegram_channel_id
    items = creative.media_items or []
    try:
        if len(items) >= 2:
            api_results = await telegram.send_media_group(
                chat_id,
                items,
                caption=creative.text,
                caption_entities=entities,
            )
            # Use the first message_id for retention tracking
            api_result = api_results[0] if api_results else {}
        elif len(items) == 1:
            item = items[0]
            media_type = item["type"]
            file_id = item["file_id"]
            if media_type == "photo":
                api_result = await telegram.send_photo(
                    chat_id,
                    file_id,
                    caption=creative.text,
                    caption_entities=entities,
                )
            elif media_type == "video":
                api_result = await telegram.send_video(
                    chat_id,
                    file_id,
                    caption=creative.text,
                    caption_entities=entities,
                )
            elif media_type == "document":
                api_result = await telegram.send_document(
                    chat_id,
                    file_id,
                    caption=creative.text,
                    caption_entities=entities,
                )
            elif media_type == "animation":
                api_result = await telegram.send_animation(
                    chat_id,
                    file_id,
                    caption=creative.text,
                    caption_entities=entities,
                )
            else:
                api_result = await telegram.send_message(
                    chat_id,
                    creative.text,
                    entities=entities,
                )
        else:
            api_result = await telegram.send_message(
                chat_id,
                creative.text,
                entities=entities,
            )
    except Exception:
        logger.exception("Failed to send post for deal %d", deal_id)
        raise

    now = datetime.now(timezone.utc)
    posting.telegram_message_id = api_result.get("message_id")
    posting.posted_at = now
    posting.raw_payload = json.dumps(api_result, default=str)

    # Audit log
    from app.services.audit import log_audit

    await log_audit(
        db,
        action="auto_post",
        entity_type="deal",
        entity_id=deal_id,
        details={
            "message_id": posting.telegram_message_id,
            "channel_id": channel.telegram_channel_id,
        },
    )

    # Transition: mark_posted then start_retention
    await system_transition_deal(db, deal_id, "mark_posted")
    await system_transition_deal(db, deal_id, "start_retention")

    await db.commit()
    await db.refresh(posting)
    return posting


async def _fail_retention(
    db: AsyncSession,
    deal_id: int,
    posting: DealPosting,
    error: str,
) -> bool:
    """Mark retention as failed, transition deal to REFUNDED, dispatch escrow refund in background.

    Returns immediately after DB commit. The blockchain refund is handled
    by a Celery task; the escrow monitor will send a confirmation notification
    when the refund is confirmed on-chain.
    """
    now = datetime.now(timezone.utc)
    posting.retained = False
    posting.verified_at = now
    posting.verification_error = error

    # Transition deal to REFUNDED (silent=True: we send a custom notification below)
    deal = await system_transition_deal(db, deal_id, "refund", silent=True)

    # Send detailed notification with violation reason
    from app.services.notification import notify_retention_violation

    await notify_retention_violation(deal, error)

    # Dispatch escrow refund to background worker (non-blocking)
    from app.workers.escrow_operations import trigger_escrow_refund

    trigger_escrow_refund.delay(deal_id)

    return False


async def _read_channel_message(channel: Channel, message_id: int) -> dict | None:
    """Read a channel message via MTProto.

    Returns {"text": str, "exists": True, "edit_date": datetime|None} or
    None if the message was deleted / inaccessible.
    Raises ValueError if MTProto is not configured.
    """
    from app.services.mtproto import get_message

    chat_id: int | str = (
        f"@{channel.username}" if channel.username else channel.telegram_channel_id
    )
    post = await get_message(chat_id, message_id)
    if post is None:
        return None
    return {
        "text": post.text_preview or "",
        "exists": True,
        "edit_date": post.edit_date,
    }


async def verify_retention(db: AsyncSession, deal_id: int) -> bool:
    """Verify post retention after the required period — called by Celery worker."""
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise ValueError(f"Deal {deal_id} not found")

    posting_result = await db.execute(
        select(DealPosting).where(DealPosting.deal_id == deal_id)
    )
    posting = posting_result.scalar_one_or_none()
    if not posting:
        raise ValueError(f"No posting record for deal {deal_id}")

    if not posting.posted_at or not posting.telegram_message_id:
        raise ValueError(f"Deal {deal_id} has not been posted yet")

    channel_result = await db.execute(
        select(Channel).where(Channel.id == posting.channel_id)
    )
    channel = channel_result.scalar_one_or_none()
    if not channel:
        raise ValueError(f"Channel {posting.channel_id} not found")

    creative = await get_current_creative(db, deal_id)
    now = datetime.now(timezone.utc)

    # Read the message via MTProto
    try:
        msg = await _read_channel_message(channel, posting.telegram_message_id)
    except Exception as exc:
        logger.warning("Retention check failed for deal %d: %s", deal_id, exc)
        return await _fail_retention(db, deal_id, posting, str(exc))

    # Message deleted
    if msg is None:
        logger.warning("Deal %d: post was deleted from channel", deal_id)
        return await _fail_retention(
            db,
            deal_id,
            posting,
            "Post was deleted during retention period",
        )

    # Check if post was edited (any edit — text, media, formatting)
    if msg["edit_date"] is not None:
        logger.warning("Deal %d: post has edit_date set", deal_id)
        return await _fail_retention(
            db,
            deal_id,
            posting,
            "Post was edited during retention period",
        )

    if creative:
        # Compare text (creative.text may be longer than 500-char preview)
        original = creative.text or ""
        current = msg["text"] or ""
        # MTProto preview is truncated to 500 chars — compare up to that length
        if current != original[:500]:
            logger.warning("Deal %d: post text differs from creative", deal_id)
            return await _fail_retention(
                db,
                deal_id,
                posting,
                "Post was edited during retention period",
            )

    # Post OK — release
    posting.retained = True
    posting.verified_at = now

    # Audit log
    from app.services.audit import log_audit

    await log_audit(
        db,
        action="verify_retention",
        entity_type="deal",
        entity_id=deal_id,
        details={"retained": True},
    )

    await system_transition_deal(db, deal_id, "release")

    # Dispatch escrow release to background worker
    from app.workers.escrow_operations import trigger_escrow_release

    trigger_escrow_release.delay(deal_id)

    return True


async def fail_retention_on_edit(
    db: AsyncSession,
    telegram_channel_id: int,
    telegram_message_id: int,
) -> bool:
    """Fail retention check if the edited message belongs to a deal in RETENTION_CHECK.

    Called when the bot receives an edited_channel_post event.
    Returns True if a deal was affected, False otherwise.
    """
    # Find channel by telegram_channel_id
    channel_result = await db.execute(
        select(Channel).where(Channel.telegram_channel_id == telegram_channel_id)
    )
    channel = channel_result.scalar_one_or_none()
    if not channel:
        return False

    # Find matching deal posting
    posting_result = await db.execute(
        select(DealPosting)
        .join(Deal, Deal.id == DealPosting.deal_id)
        .where(
            DealPosting.channel_id == channel.id,
            DealPosting.telegram_message_id == telegram_message_id,
            DealPosting.posted_at.isnot(None),
            DealPosting.verified_at.is_(None),
            Deal.status == "RETENTION_CHECK",
        )
    )
    posting = posting_result.scalar_one_or_none()
    if not posting:
        return False

    now = datetime.now(timezone.utc)
    error = "Post was edited during retention period"
    posting.retained = False
    posting.verified_at = now
    posting.verification_error = error

    # Transition deal to REFUNDED (silent: custom notification follows)
    deal = await system_transition_deal(db, posting.deal_id, "refund", silent=True)

    # Send detailed notification with violation reason
    from app.services.notification import notify_retention_violation

    await notify_retention_violation(deal, error)

    # Dispatch escrow refund to background worker
    from app.workers.escrow_operations import trigger_escrow_refund

    trigger_escrow_refund.delay(posting.deal_id)

    logger.info(
        "Retention failed for deal %d — post %d was edited in channel %d",
        posting.deal_id,
        telegram_message_id,
        telegram_channel_id,
    )
    return True


async def check_retention(
    db: AsyncSession,
    deal_id: int,
    user_id: int,
) -> dict:
    """Manual retention check — verifies post integrity without finalizing if period hasn't elapsed.

    Returns a dict with:
      ok: bool — post exists and text matches
      elapsed: bool — retention period has passed
      finalized: bool — whether a state transition happened (release or refund)
      error: str | None — error description if not ok
      posting: DealPosting
    """
    deal = await get_deal(db, deal_id, user_id)

    if deal.status != "RETENTION_CHECK":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Deal is not in RETENTION_CHECK (current: {deal.status})",
        )

    posting_result = await db.execute(
        select(DealPosting).where(DealPosting.deal_id == deal_id)
    )
    posting = posting_result.scalar_one_or_none()
    if not posting or not posting.posted_at or not posting.telegram_message_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Post has not been published yet",
        )

    channel_result = await db.execute(
        select(Channel).where(Channel.id == posting.channel_id)
    )
    channel = channel_result.scalar_one_or_none()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )

    creative = await get_current_creative(db, deal_id)
    now = datetime.now(timezone.utc)
    from datetime import timedelta

    retention_end = posting.posted_at + timedelta(hours=posting.retention_hours)
    elapsed = now >= retention_end

    # Read message via MTProto
    try:
        msg = await _read_channel_message(channel, posting.telegram_message_id)
    except Exception as exc:
        logger.warning("Manual retention check failed for deal %d: %s", deal_id, exc)
        await _fail_retention(db, deal_id, posting, str(exc))
        await db.refresh(posting)
        return {
            "ok": False,
            "elapsed": elapsed,
            "finalized": True,
            "error": str(exc),
            "posting": posting,
        }

    # Message deleted
    if msg is None:
        await _fail_retention(
            db,
            deal_id,
            posting,
            "Post was deleted during retention period",
        )
        await db.refresh(posting)
        return {
            "ok": False,
            "elapsed": elapsed,
            "finalized": True,
            "error": "Post was deleted during retention period",
            "posting": posting,
        }

    # Check if post was edited (any edit — text, media, formatting)
    if msg["edit_date"] is not None:
        error = "Post was edited during retention period"
        await _fail_retention(db, deal_id, posting, error)
        await db.refresh(posting)
        return {
            "ok": False,
            "elapsed": elapsed,
            "finalized": True,
            "error": error,
            "posting": posting,
        }

    # Check text content integrity
    if creative:
        original = creative.text or ""
        current = msg["text"] or ""
        if current != original[:500]:
            error = "Post was edited during retention period"
            await _fail_retention(db, deal_id, posting, error)
            await db.refresh(posting)
            return {
                "ok": False,
                "elapsed": elapsed,
                "finalized": True,
                "error": error,
                "posting": posting,
            }

    # Post is OK
    if elapsed:
        posting.retained = True
        posting.verified_at = now
        await system_transition_deal(db, deal_id, "release")

        # Dispatch escrow release to background worker
        from app.workers.escrow_operations import trigger_escrow_release

        trigger_escrow_release.delay(deal_id)

        await db.refresh(posting)
        return {
            "ok": True,
            "elapsed": True,
            "finalized": True,
            "error": None,
            "posting": posting,
        }

    # Post OK but retention period not yet elapsed — no state change
    return {
        "ok": True,
        "elapsed": False,
        "finalized": False,
        "error": None,
        "posting": posting,
    }


async def get_posting(db: AsyncSession, deal_id: int) -> DealPosting | None:
    """Return the posting record for a deal."""
    result = await db.execute(select(DealPosting).where(DealPosting.deal_id == deal_id))
    return result.scalar_one_or_none()
