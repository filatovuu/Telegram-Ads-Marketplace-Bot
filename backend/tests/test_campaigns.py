"""Tests for campaign service — CRUD and ownership validation."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.schemas import CampaignCreate, CampaignUpdate
from app.models.campaign import Campaign
from app.models.user import User
from app.services.campaign import (
    create_campaign,
    delete_campaign,
    get_campaign,
    get_campaigns_by_advertiser,
    update_campaign,
)


def _make_user(id: int = 1) -> User:
    user = User(
        telegram_id=111,
        username="testadvertiser",
        first_name="Test",
        last_name="User",
        locale="en",
        active_role="advertiser",
    )
    object.__setattr__(user, "id", id)
    return user


def _mock_db(scalar_result=None):
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = scalar_result
    db.execute = AsyncMock(return_value=mock_result)
    return db


def _mock_db_scalars(items: list):
    db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = items
    mock_result.scalars.return_value = mock_scalars
    db.execute = AsyncMock(return_value=mock_result)
    return db


class TestCreateCampaign:
    @pytest.mark.asyncio
    async def test_creates_campaign(self):
        """Advertiser should be able to create a campaign."""
        db = _mock_db()
        user = _make_user()
        data = CampaignCreate(
            title="Test Campaign",
            brief="Run ads in tech channels",
            category="tech",
            budget_min=Decimal("10.0"),
            budget_max=Decimal("100.0"),
        )

        campaign = await create_campaign(db, user, data)
        assert campaign.title == "Test Campaign"
        assert campaign.brief == "Run ads in tech channels"
        assert campaign.category == "tech"
        assert campaign.budget_min == Decimal("10.0")
        assert campaign.budget_max == Decimal("100.0")
        assert campaign.advertiser_id == 1
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_campaign_minimal(self):
        """Campaign with only required fields should be created."""
        db = _mock_db()
        user = _make_user()
        data = CampaignCreate(
            title="Minimal Campaign",
            budget_min=Decimal("5.0"),
            budget_max=Decimal("50.0"),
        )

        campaign = await create_campaign(db, user, data)
        assert campaign.title == "Minimal Campaign"
        assert campaign.brief is None
        assert campaign.category is None
        db.add.assert_called_once()


class TestGetCampaign:
    @pytest.mark.asyncio
    async def test_returns_campaign_for_owner(self):
        """Should return campaign when owned by the user."""
        campaign = Campaign(
            advertiser_id=1,
            title="My Campaign",
            budget_min=Decimal("10"),
            budget_max=Decimal("100"),
        )
        object.__setattr__(campaign, "id", 5)
        db = _mock_db(scalar_result=campaign)

        result = await get_campaign(db, 5, 1)
        assert result.title == "My Campaign"

    @pytest.mark.asyncio
    async def test_raises_404_for_non_owner(self):
        """Should raise 404 when campaign not found or not owned."""
        db = _mock_db(scalar_result=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_campaign(db, 999, 1)
        assert exc_info.value.status_code == 404


class TestGetCampaignsByAdvertiser:
    @pytest.mark.asyncio
    async def test_returns_empty_list(self):
        """Should return empty list when no campaigns exist."""
        db = _mock_db_scalars([])
        results = await get_campaigns_by_advertiser(db, 1)
        assert results == []

    @pytest.mark.asyncio
    async def test_returns_campaigns(self):
        """Should return list of campaigns."""
        c1 = Campaign(advertiser_id=1, title="C1", budget_min=Decimal("1"), budget_max=Decimal("10"))
        c2 = Campaign(advertiser_id=1, title="C2", budget_min=Decimal("2"), budget_max=Decimal("20"))
        db = _mock_db_scalars([c1, c2])
        results = await get_campaigns_by_advertiser(db, 1)
        assert len(results) == 2


class TestUpdateCampaign:
    @pytest.mark.asyncio
    async def test_updates_fields(self):
        """Should update only specified fields."""
        campaign = Campaign(
            advertiser_id=1,
            title="Old Title",
            budget_min=Decimal("10"),
            budget_max=Decimal("100"),
        )
        db = _mock_db()
        data = CampaignUpdate(title="New Title")

        result = await update_campaign(db, campaign, data)
        assert result.title == "New Title"
        assert result.budget_min == Decimal("10")


class TestDeleteCampaign:
    @pytest.mark.asyncio
    async def test_deletes_campaign(self):
        """Should delete campaign."""
        campaign = Campaign(
            advertiser_id=1,
            title="To Delete",
            budget_min=Decimal("10"),
            budget_max=Decimal("100"),
        )
        db = _mock_db()
        await delete_campaign(db, campaign)
        db.delete.assert_called_once_with(campaign)
        db.commit.assert_called_once()
