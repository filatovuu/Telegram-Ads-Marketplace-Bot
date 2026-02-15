from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    CampaignPublicResponse,
    ChannelPublicStatsResponse,
    ListingFilter,
    ListingResponse,
    PaginatedCampaignPublicResponse,
    PaginatedListingResponse,
)
from app.core.deps import get_db
from app.services import campaign as campaign_svc
from app.services import listing as listing_svc
from app.services import stats as stats_svc

router = APIRouter(prefix="/market", tags=["market"])

_MAX_BUDGET = Decimal("999999999999")


@router.get("/listings", response_model=PaginatedListingResponse)
async def search_listings(
    min_price: Decimal | None = Query(default=None, ge=0, le=_MAX_BUDGET),
    max_price: Decimal | None = Query(default=None, ge=0, le=_MAX_BUDGET),
    language: str | None = Query(default=None),
    category: str | None = Query(default=None),
    format: str | None = Query(default=None),
    min_subscribers: int | None = Query(default=None),
    min_avg_views: int | None = Query(default=None),
    min_growth_pct_7d: float | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    filters = ListingFilter(
        min_price=min_price,
        max_price=max_price,
        language=language,
        category=category,
        format=format,
        min_subscribers=min_subscribers,
        min_avg_views=min_avg_views,
        min_growth_pct_7d=min_growth_pct_7d,
    )
    items, total = await listing_svc.search_listings_paginated(db, filters, offset=offset, limit=limit)
    return PaginatedListingResponse(
        items=items,
        total=total,
        offset=offset,
        limit=limit,
        has_more=(offset + limit) < total,
    )


@router.get("/listings/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await listing_svc.get_listing(db, listing_id)


@router.get("/campaigns", response_model=PaginatedCampaignPublicResponse)
async def search_campaigns(
    min_budget: Decimal | None = Query(default=None, ge=0, le=_MAX_BUDGET),
    max_budget: Decimal | None = Query(default=None, ge=0, le=_MAX_BUDGET),
    category: str | None = Query(default=None),
    target_language: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    items, total = await campaign_svc.search_campaigns_public(
        db,
        min_budget=min_budget,
        max_budget=max_budget,
        category=category,
        target_language=target_language,
        offset=offset,
        limit=limit,
    )
    return PaginatedCampaignPublicResponse(
        items=items,
        total=total,
        offset=offset,
        limit=limit,
        has_more=(offset + limit) < total,
    )


@router.get("/campaigns/{campaign_id}", response_model=CampaignPublicResponse)
async def get_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await campaign_svc.get_campaign_public(db, campaign_id)


@router.get("/channels/{channel_id}/stats", response_model=ChannelPublicStatsResponse)
async def get_channel_public_stats(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
):
    snapshot = await stats_svc.get_latest_snapshot(db, channel_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No stats available for this channel.",
        )
    return ChannelPublicStatsResponse.from_snapshot(snapshot)
