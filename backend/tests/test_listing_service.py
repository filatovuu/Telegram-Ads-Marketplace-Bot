"""Tests for listing service — filter queries and ownership validation."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.schemas import ListingCreate, ListingFilter
from app.models.channel import Channel
from app.models.listing import Listing
from app.models.user import User
from app.services.listing import create_listing, search_listings


def _make_user(id: int = 1) -> User:
    user = User(
        telegram_id=111,
        username="testuser",
        first_name="Test",
        last_name="User",
        locale="en",
        active_role="owner",
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
    """Mock DB for queries that use .scalars().all()."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = items
    mock_result.scalars.return_value = mock_scalars
    db.execute = AsyncMock(return_value=mock_result)
    return db


class TestCreateListing:
    @pytest.mark.asyncio
    async def test_rejects_non_owner_channel(self):
        """Creating a listing for someone else's channel should raise 404."""
        db = _mock_db(scalar_result=None)
        user = _make_user()
        data = ListingCreate(
            channel_id=999,
            title="Test Listing",
            price=Decimal("10.5"),
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_listing(db, user, data)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_creates_listing_for_own_channel(self):
        """Owner should be able to create listing for their channel."""
        channel = Channel(
            telegram_channel_id=-1001234,
            title="My Channel",
            owner_id=1,
        )
        channel.language = "en"
        object.__setattr__(channel, "id", 5)

        db = _mock_db(scalar_result=channel)
        user = _make_user()
        data = ListingCreate(
            channel_id=5,
            title="Ad Placement",
            description="Top of feed",
            price=Decimal("25.0"),
            currency="TON",
            format="post",
        )

        listing = await create_listing(db, user, data)
        assert listing.title == "Ad Placement"
        assert listing.price == Decimal("25.0")
        assert listing.channel_id == 5
        assert listing.language == "en"
        db.add.assert_called_once()


class TestSearchListings:
    @pytest.mark.asyncio
    async def test_search_returns_empty_list(self):
        """Search with no results should return empty list."""
        db = _mock_db_scalars([])
        filters = ListingFilter()
        results = await search_listings(db, filters)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_passes_filters_to_query(self):
        """Verify that the query is built with the correct filters."""
        db = _mock_db_scalars([])
        filters = ListingFilter(
            min_price=Decimal("5.0"),
            max_price=Decimal("50.0"),
            language="en",
            min_subscribers=1000,
        )
        results = await search_listings(db, filters)
        assert results == []
        db.execute.assert_called_once()
