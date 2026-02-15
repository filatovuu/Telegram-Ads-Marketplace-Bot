from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import CampaignCreate, CampaignUpdate
from app.models.campaign import Campaign
from app.models.user import User


async def create_campaign(db: AsyncSession, advertiser: User, data: CampaignCreate) -> Campaign:
    campaign = Campaign(
        advertiser_id=advertiser.id,
        title=data.title,
        brief=data.brief,
        category=data.category,
        target_language=data.target_language,
        budget_min=data.budget_min,
        budget_max=data.budget_max,
        publish_from=data.publish_from,
        publish_to=data.publish_to,
        links=data.links,
        restrictions=data.restrictions,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return campaign


async def get_campaigns_by_advertiser(
    db: AsyncSession, advertiser_id: int, offset: int = 0, limit: int = 50,
) -> list[Campaign]:
    result = await db.execute(
        select(Campaign)
        .where(Campaign.advertiser_id == advertiser_id)
        .order_by(Campaign.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_campaign(db: AsyncSession, campaign_id: int, advertiser_id: int) -> Campaign:
    result = await db.execute(
        select(Campaign).where(
            Campaign.id == campaign_id, Campaign.advertiser_id == advertiser_id
        )
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )
    return campaign


async def update_campaign(
    db: AsyncSession, campaign: Campaign, data: CampaignUpdate
) -> Campaign:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(campaign, field, value)
    await db.commit()
    await db.refresh(campaign)
    return campaign


async def delete_campaign(db: AsyncSession, campaign: Campaign) -> None:
    await db.delete(campaign)
    await db.commit()


async def search_campaigns_public(
    db: AsyncSession,
    *,
    min_budget: Decimal | None = None,
    max_budget: Decimal | None = None,
    category: str | None = None,
    target_language: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Campaign], int]:
    query = select(Campaign).where(Campaign.is_active == True)  # noqa: E712
    count_query = select(func.count()).select_from(Campaign).where(Campaign.is_active == True)  # noqa: E712

    if min_budget is not None:
        query = query.where(Campaign.budget_max >= min_budget)
        count_query = count_query.where(Campaign.budget_max >= min_budget)
    if max_budget is not None:
        query = query.where(Campaign.budget_min <= max_budget)
        count_query = count_query.where(Campaign.budget_min <= max_budget)
    if category:
        cat_filter = or_(
            Campaign.category == category,
            Campaign.category.is_(None),
        )
        query = query.where(cat_filter)
        count_query = count_query.where(cat_filter)
    if target_language:
        lang_filter = or_(
            Campaign.target_language == target_language,
            Campaign.target_language.is_(None),
        )
        query = query.where(lang_filter)
        count_query = count_query.where(lang_filter)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Campaign.id.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


async def get_campaign_public(db: AsyncSession, campaign_id: int) -> Campaign:
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.is_active == True)  # noqa: E712
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )
    return campaign
