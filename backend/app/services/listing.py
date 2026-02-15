import json
import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sqlalchemy import func as sa_func

from app.api.schemas import ListingCreate, ListingFilter, ListingUpdate
from app.core.cache import cache_delete_pattern, cache_get, cache_set, make_cache_key
from app.core.config import settings
from app.models.channel import Channel
from app.models.channel_stats import ChannelStatsSnapshot
from app.models.listing import Listing
from app.models.user import User

logger = logging.getLogger(__name__)

_LISTING_CACHE_PREFIX = "listings"


async def _invalidate_listing_cache() -> None:
    """Invalidate all cached listing search results."""
    await cache_delete_pattern(f"cache:{_LISTING_CACHE_PREFIX}:*")


async def create_listing(db: AsyncSession, owner: User, data: ListingCreate) -> Listing:
    # Verify channel ownership
    result = await db.execute(
        select(Channel).where(
            Channel.id == data.channel_id, Channel.owner_id == owner.id
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found or you are not the owner",
        )

    listing = Listing(
        channel_id=data.channel_id,
        title=data.title,
        description=data.description,
        price=data.price,
        currency=data.currency,
        format=data.format,
        language=channel.language,
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing, attribute_names=["channel"])
    await _invalidate_listing_cache()
    return listing


async def get_listings_by_owner(
    db: AsyncSession, owner_id: int, offset: int = 0, limit: int = 50,
) -> list[Listing]:
    result = await db.execute(
        select(Listing)
        .join(Channel)
        .where(Channel.owner_id == owner_id)
        .options(selectinload(Listing.channel))
        .order_by(Listing.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_listing(db: AsyncSession, listing_id: int) -> Listing:
    result = await db.execute(
        select(Listing)
        .where(Listing.id == listing_id)
        .options(selectinload(Listing.channel))
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found"
        )
    return listing


async def update_listing(
    db: AsyncSession, listing: Listing, data: ListingUpdate
) -> Listing:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(listing, field, value)
    await db.commit()
    await db.refresh(listing, attribute_names=["channel"])
    await _invalidate_listing_cache()
    return listing


async def delete_listing(db: AsyncSession, listing: Listing) -> None:
    await db.delete(listing)
    await db.commit()
    await _invalidate_listing_cache()


def _build_search_query(filters: ListingFilter):
    """Build the base filtered query (without pagination)."""
    query = (
        select(Listing)
        .join(Channel)
        .where(Listing.is_active == True)  # noqa: E712
        .options(selectinload(Listing.channel))
    )

    if filters.min_price is not None:
        query = query.where(Listing.price >= filters.min_price)
    if filters.max_price is not None:
        query = query.where(Listing.price <= filters.max_price)
    if filters.language is not None:
        query = query.where(Channel.language == filters.language)
    if filters.format is not None:
        query = query.where(Listing.format == filters.format)
    if filters.min_subscribers is not None:
        query = query.where(Channel.subscribers >= filters.min_subscribers)
    if filters.min_avg_views is not None:
        query = query.where(Channel.avg_views >= filters.min_avg_views)

    if filters.min_growth_pct_7d is not None:
        latest_snapshot = (
            select(
                ChannelStatsSnapshot.channel_id,
                ChannelStatsSnapshot.subscribers_growth_pct_7d,
            )
            .distinct(ChannelStatsSnapshot.channel_id)
            .order_by(
                ChannelStatsSnapshot.channel_id,
                ChannelStatsSnapshot.created_at.desc(),
            )
            .subquery()
        )
        query = query.join(
            latest_snapshot,
            Channel.id == latest_snapshot.c.channel_id,
        ).where(
            latest_snapshot.c.subscribers_growth_pct_7d >= filters.min_growth_pct_7d
        )

    return query


async def search_listings(
    db: AsyncSession,
    filters: ListingFilter,
    offset: int = 0,
    limit: int = 20,
) -> list[Listing]:
    query = _build_search_query(filters)
    query = query.order_by(Listing.id.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def search_listings_paginated(
    db: AsyncSession,
    filters: ListingFilter,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Listing], int]:
    """Return (items, total_count)."""
    base = _build_search_query(filters)

    # Count total
    count_q = select(sa_func.count()).select_from(
        base.with_only_columns(Listing.id).subquery()
    )
    total = (await db.execute(count_q)).scalar() or 0

    # Fetch page
    query = base.order_by(Listing.id.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return items, total
