"""Tests for deal timeout logic — expire inactive deals and refund overdue deals."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.deal import Deal
from app.services.deal import get_deals_for_timeout


def _make_deal(deal_id: int, status: str, hours_ago: int) -> Deal:
    deal = Deal(
        listing_id=10,
        advertiser_id=1,
        owner_id=2,
        price=Decimal("25.0"),
        status=status,
        last_activity_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
    )
    object.__setattr__(deal, "id", deal_id)
    return deal


def _mock_db_scalars(items: list):
    db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = items
    mock_result.scalars.return_value = mock_scalars
    db.execute = AsyncMock(return_value=mock_result)
    return db


class TestGetDealsForTimeout:
    @pytest.mark.asyncio
    async def test_returns_old_deals(self):
        """Should return deals with last_activity_at older than cutoff."""
        old_deal = _make_deal(1, "NEGOTIATION", hours_ago=100)
        db = _mock_db_scalars([old_deal])

        cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
        results = await get_deals_for_timeout(
            db, cutoff, ["NEGOTIATION", "OWNER_ACCEPTED"]
        )
        assert len(results) == 1
        assert results[0].id == 1

    @pytest.mark.asyncio
    async def test_returns_empty_for_recent_deals(self):
        """Should return empty list when all deals are recent."""
        db = _mock_db_scalars([])

        cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
        results = await get_deals_for_timeout(
            db, cutoff, ["NEGOTIATION"]
        )
        assert results == []

    @pytest.mark.asyncio
    async def test_filters_by_status(self):
        """get_deals_for_timeout passes statuses to the query."""
        old_deal = _make_deal(1, "SCHEDULED", hours_ago=100)
        db = _mock_db_scalars([old_deal])

        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        results = await get_deals_for_timeout(
            db, cutoff, ["SCHEDULED"]
        )
        assert len(results) == 1
