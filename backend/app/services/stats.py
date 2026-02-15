import asyncio
import logging
import statistics
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel import Channel
from app.models.channel_post import ChannelPost
from app.models.channel_stats import ChannelStatsSnapshot
from app.models.post_view_snapshot import PostViewSnapshot
from app.services import mtproto, telegram

logger = logging.getLogger(__name__)

# Unicode range for Cyrillic script detection
_CYRILLIC = set(range(0x0400, 0x0500))


async def _detect_language(db: AsyncSession, channel_id: int) -> str:
    """Detect the predominant language from recent post texts. Defaults to 'en'."""
    result = await db.execute(
        select(ChannelPost.text_preview)
        .where(
            ChannelPost.channel_id == channel_id,
            ChannelPost.text_preview.is_not(None),
        )
        .order_by(ChannelPost.date.desc())
        .limit(50)
    )
    texts = [r[0] for r in result.all() if r[0]]
    if not texts:
        return "en"

    combined = " ".join(texts)
    letters = [ch for ch in combined if ch.isalpha()]
    if not letters:
        return "en"

    cyrillic = sum(1 for ch in letters if ord(ch) in _CYRILLIC)
    if cyrillic / len(letters) > 0.3:
        return "ru"
    return "en"


async def _compute_growth(
    db: AsyncSession,
    channel_id: int,
    days: int,
    current_subscribers: int,
) -> tuple[int | None, float | None]:
    """Find the closest snapshot ~N days ago and compute absolute + percentage growth."""
    target_date = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(ChannelStatsSnapshot)
        .where(
            ChannelStatsSnapshot.channel_id == channel_id,
            ChannelStatsSnapshot.created_at <= target_date,
        )
        .order_by(ChannelStatsSnapshot.created_at.desc())
        .limit(1)
    )
    old_snapshot = result.scalar_one_or_none()
    if old_snapshot is None:
        return None, None

    growth = current_subscribers - old_snapshot.subscribers
    if old_snapshot.subscribers > 0:
        growth_pct = round(growth / old_snapshot.subscribers * 100, 2)
    else:
        growth_pct = None

    return growth, growth_pct


def _avg_views_last_n(views_list: list[int], n: int) -> int | None:
    """Average views of the last N posts (most recent first)."""
    subset = views_list[:n]
    if not subset:
        return None
    return round(statistics.mean(subset))


async def _compute_post_metrics(
    db: AsyncSession,
    channel_id: int,
    subscribers: int,
) -> dict:
    """Compute all view-based metrics from stored channel posts."""
    # Get all posts with views, ordered by date desc (newest first)
    result = await db.execute(
        select(ChannelPost.views, ChannelPost.date)
        .where(
            ChannelPost.channel_id == channel_id,
            ChannelPost.views.is_not(None),
        )
        .order_by(ChannelPost.date.desc())
    )
    rows = result.all()
    views_list = [r[0] for r in rows]

    # Count total tracked posts (including those without views)
    count_result = await db.execute(
        select(func.count(ChannelPost.id)).where(ChannelPost.channel_id == channel_id)
    )
    posts_tracked = count_result.scalar() or 0

    # Posts per week — from oldest to newest tracked post
    posts_per_week: float | None = None
    if posts_tracked >= 2:
        dates_result = await db.execute(
            select(func.min(ChannelPost.date), func.max(ChannelPost.date)).where(
                ChannelPost.channel_id == channel_id
            )
        )
        date_row = dates_result.one()
        oldest, newest = date_row[0], date_row[1]
        if oldest and newest and oldest != newest:
            span_days = (newest - oldest).total_seconds() / 86400
            if span_days > 0:
                posts_per_week = round(posts_tracked / span_days * 7, 1)

    avg_views = round(statistics.mean(views_list)) if views_list else None
    median = round(statistics.median(views_list)) if views_list else None
    # Use median_views per doc spec (not avg_views)
    reach_pct = round(median / subscribers * 100, 1) if median and subscribers > 0 else None

    return {
        "avg_views": avg_views,
        "avg_views_10": _avg_views_last_n(views_list, 10),
        "avg_views_30": _avg_views_last_n(views_list, 30),
        "avg_views_50": _avg_views_last_n(views_list, 50),
        "median_views": median,
        "reach_pct": reach_pct,
        "posts_per_week": posts_per_week,
        "posts_tracked": posts_tracked,
    }


async def _compute_engagement_metrics(
    db: AsyncSession,
    channel_id: int,
) -> dict:
    """Compute reactions_per_views and forwards_per_views from last 50 posts."""
    result = await db.execute(
        select(ChannelPost.views, ChannelPost.reactions_count, ChannelPost.forward_count)
        .where(
            ChannelPost.channel_id == channel_id,
            ChannelPost.views > 0,
        )
        .order_by(ChannelPost.date.desc())
        .limit(50)
    )
    rows = result.all()

    reaction_ratios = []
    forward_ratios = []
    for views, reactions, forwards in rows:
        if reactions is not None:
            reaction_ratios.append(reactions / views)
        if forwards is not None:
            forward_ratios.append(forwards / views)

    return {
        "reactions_per_views": round(statistics.mean(reaction_ratios), 4) if reaction_ratios else None,
        "forwards_per_views": round(statistics.mean(forward_ratios), 4) if forward_ratios else None,
    }


async def _compute_velocity(
    db: AsyncSession,
    channel_id: int,
) -> dict:
    """Compute views velocity (views_1h / views_24h ratio) from view snapshots."""
    # Get last 50 posts that have view snapshots
    result = await db.execute(
        select(ChannelPost.id, ChannelPost.date)
        .where(ChannelPost.channel_id == channel_id)
        .order_by(ChannelPost.date.desc())
        .limit(50)
    )
    posts = result.all()

    ratios = []
    for post_id, post_date in posts:
        # Get all view snapshots for this post
        snap_result = await db.execute(
            select(PostViewSnapshot.views, PostViewSnapshot.recorded_at)
            .where(PostViewSnapshot.post_id == post_id)
            .order_by(PostViewSnapshot.recorded_at.asc())
        )
        snapshots = snap_result.all()
        if len(snapshots) < 2:
            continue

        target_1h = post_date + timedelta(hours=1)
        target_24h = post_date + timedelta(hours=24)

        # Find closest snapshot to +1h and +24h
        views_1h = None
        views_24h = None
        min_diff_1h = None
        min_diff_24h = None

        for views, recorded_at in snapshots:
            diff_1h = abs((recorded_at - target_1h).total_seconds())
            diff_24h = abs((recorded_at - target_24h).total_seconds())

            # Allow up to 2h tolerance for 1h snapshot, 6h for 24h
            if diff_1h < 7200 and (min_diff_1h is None or diff_1h < min_diff_1h):
                views_1h = views
                min_diff_1h = diff_1h
            if diff_24h < 21600 and (min_diff_24h is None or diff_24h < min_diff_24h):
                views_24h = views
                min_diff_24h = diff_24h

        if views_1h is not None and views_24h is not None and views_24h > 0:
            ratios.append(views_1h / views_24h)

    return {
        "velocity_1h_ratio": round(statistics.mean(ratios), 3) if ratios else None,
    }


async def _compute_frequency_metrics(
    db: AsyncSession,
    channel_id: int,
) -> dict:
    """Compute posts_7d, posts_30d, and per-day rates."""
    now = datetime.now(timezone.utc)

    result_7d = await db.execute(
        select(func.count(ChannelPost.id)).where(
            ChannelPost.channel_id == channel_id,
            ChannelPost.date >= now - timedelta(days=7),
        )
    )
    posts_7d = result_7d.scalar() or 0

    result_30d = await db.execute(
        select(func.count(ChannelPost.id)).where(
            ChannelPost.channel_id == channel_id,
            ChannelPost.date >= now - timedelta(days=30),
        )
    )
    posts_30d = result_30d.scalar() or 0

    return {
        "posts_7d": posts_7d,
        "posts_30d": posts_30d,
        "posts_per_day_7d": round(posts_7d / 7, 2),
        "posts_per_day_30d": round(posts_30d / 30, 2),
    }


async def _compute_reliability(
    db: AsyncSession,
    channel_id: int,
) -> dict:
    """Compute edit_rate = edited_posts / total_posts."""
    total_result = await db.execute(
        select(func.count(ChannelPost.id)).where(ChannelPost.channel_id == channel_id)
    )
    total = total_result.scalar() or 0

    if total == 0:
        return {"edit_rate": None}

    edited_result = await db.execute(
        select(func.count(ChannelPost.id)).where(
            ChannelPost.channel_id == channel_id,
            ChannelPost.edit_date.is_not(None),
        )
    )
    edited = edited_result.scalar() or 0

    return {"edit_rate": round(edited / total, 3)}


async def collect_snapshot(db: AsyncSession, channel: Channel) -> ChannelStatsSnapshot:
    """Fetch stats from Bot API, compute all metrics, create snapshot."""
    chat_id = f"@{channel.username}" if channel.username else channel.telegram_channel_id

    # Fetch current subscriber count
    try:
        subscribers = await telegram.get_chat_member_count(chat_id)
    except ValueError:
        subscribers = channel.subscribers

    # Fetch chat metadata
    has_visible_history = None
    has_aggressive_anti_spam = None
    try:
        chat = await telegram.get_chat(chat_id)
        has_visible_history = chat.get("has_visible_history")
        has_aggressive_anti_spam = chat.get("has_aggressive_anti_spam")
        # Update channel metadata
        channel.title = chat.get("title", channel.title)
        channel.description = chat.get("description")
        channel.invite_link = chat.get("invite_link")
    except ValueError:
        pass

    # Compute growth
    growth_7d, growth_pct_7d = await _compute_growth(db, channel.id, 7, subscribers)
    growth_30d, growth_pct_30d = await _compute_growth(db, channel.id, 30, subscribers)

    # Enrich posts with MTProto data (views, reactions, forwards)
    try:
        await mtproto.enrich_channel_posts(db, channel, limit=100)
    except Exception:
        logger.exception("MTProto enrichment failed for channel %s, continuing", channel.id)

    # Compute post-based metrics
    post_metrics = await _compute_post_metrics(db, channel.id, subscribers)

    # Compute advanced metrics
    engagement = await _compute_engagement_metrics(db, channel.id)
    velocity = await _compute_velocity(db, channel.id)
    frequency = await _compute_frequency_metrics(db, channel.id)
    reliability = await _compute_reliability(db, channel.id)

    # Detect channel language from post texts (skip if manually set)
    if not channel.language_manual:
        channel.language = await _detect_language(db, channel.id)

    # Re-check bot admin status
    try:
        bot = await telegram.get_me()
        member = await telegram.get_chat_member(chat_id, bot["id"])
        channel.bot_is_admin = member.get("status") in ("administrator", "creator")
    except ValueError:
        pass

    snapshot = ChannelStatsSnapshot(
        channel_id=channel.id,
        subscribers=subscribers,
        subscribers_growth_7d=growth_7d,
        subscribers_growth_30d=growth_30d,
        subscribers_growth_pct_7d=growth_pct_7d,
        subscribers_growth_pct_30d=growth_pct_30d,
        has_visible_history=has_visible_history,
        has_aggressive_anti_spam=has_aggressive_anti_spam,
        **post_metrics,
        **engagement,
        **velocity,
        **frequency,
        **reliability,
    )
    db.add(snapshot)

    # Update channel denormalized fields
    channel.subscribers = subscribers
    if post_metrics["avg_views"] is not None:
        channel.avg_views = post_metrics["avg_views"]

    await db.commit()
    await db.refresh(snapshot)
    return snapshot


async def get_latest_snapshot(
    db: AsyncSession, channel_id: int
) -> ChannelStatsSnapshot | None:
    """Return the most recent snapshot for a channel."""
    result = await db.execute(
        select(ChannelStatsSnapshot)
        .where(ChannelStatsSnapshot.channel_id == channel_id)
        .order_by(ChannelStatsSnapshot.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_snapshot_history(
    db: AsyncSession, channel_id: int, days: int = 30
) -> list[ChannelStatsSnapshot]:
    """Return snapshots oldest-first for the last N days (for charts)."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(ChannelStatsSnapshot)
        .where(
            ChannelStatsSnapshot.channel_id == channel_id,
            ChannelStatsSnapshot.created_at >= since,
        )
        .order_by(ChannelStatsSnapshot.created_at.asc())
    )
    return list(result.scalars().all())


async def collect_all_snapshots(db: AsyncSession) -> int:
    """Iterate all channels where bot_is_admin=True and collect a snapshot for each."""
    result = await db.execute(
        select(Channel).where(Channel.bot_is_admin == True)  # noqa: E712
    )
    channels = list(result.scalars().all())
    count = 0
    for channel in channels:
        try:
            await collect_snapshot(db, channel)
            count += 1
        except Exception:
            logger.exception("Failed to collect snapshot for channel %s", channel.id)
        # Buffer between channels to respect MTProto rate limits
        await asyncio.sleep(1)
    return count


async def upsert_channel_post(
    db: AsyncSession,
    telegram_channel_id: int,
    telegram_message_id: int,
    post_type: str,
    views: int | None,
    text_preview: str | None,
    date: datetime | None,
    edit_date: datetime | None,
    has_media: bool,
    media_group_id: str | None,
    reactions_count: int | None = None,
    forward_count: int | None = None,
) -> ChannelPost | None:
    """Create or update a channel post record. Returns None if channel not found."""
    # Look up channel by telegram_channel_id
    result = await db.execute(
        select(Channel).where(Channel.telegram_channel_id == telegram_channel_id)
    )
    channel = result.scalar_one_or_none()
    if channel is None:
        return None

    # Check if post already exists
    result = await db.execute(
        select(ChannelPost).where(
            ChannelPost.channel_id == channel.id,
            ChannelPost.telegram_message_id == telegram_message_id,
        )
    )
    post = result.scalar_one_or_none()

    if post is not None:
        # Update existing post
        if views is not None:
            post.views = views
        if edit_date is not None:
            post.edit_date = edit_date
        if reactions_count is not None:
            post.reactions_count = reactions_count
        if forward_count is not None:
            post.forward_count = forward_count
    else:
        # Create new post
        post = ChannelPost(
            channel_id=channel.id,
            telegram_message_id=telegram_message_id,
            post_type=post_type,
            views=views,
            text_preview=text_preview[:500] if text_preview else None,
            date=date or datetime.now(timezone.utc),
            edit_date=edit_date,
            has_media=has_media,
            media_group_id=media_group_id,
            reactions_count=reactions_count,
            forward_count=forward_count,
        )
        db.add(post)

    await db.commit()
    await db.refresh(post)

    # Record a view snapshot if views data is available
    if views is not None:
        snapshot = PostViewSnapshot(
            post_id=post.id,
            views=views,
            recorded_at=datetime.now(timezone.utc),
        )
        db.add(snapshot)
        await db.commit()

    return post
