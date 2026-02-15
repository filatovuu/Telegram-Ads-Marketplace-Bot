"""Tests for deal service — creation from listing, validation, and transitions."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.schemas import DealCreate
from app.models.channel import Channel
from app.models.deal import Deal
from app.models.deal_message import DealMessage
from app.models.listing import Listing
from app.models.user import User
from app.services.deal import (
    add_deal_message,
    create_deal_from_listing,
    get_deal,
    get_deals_by_user,
    transition_deal,
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


def _make_listing(id: int = 10, owner_id: int = 2, is_active: bool = True) -> Listing:
    channel = Channel(
        telegram_channel_id=-1001234,
        title="Test Channel",
        owner_id=owner_id,
    )
    object.__setattr__(channel, "id", 5)

    listing = Listing(
        channel_id=5,
        title="Ad Placement",
        price=Decimal("25.0"),
        is_active=is_active,
    )
    listing.channel = channel
    object.__setattr__(listing, "id", id)
    return listing


class TestCreateDealFromListing:
    @pytest.mark.asyncio
    async def test_creates_deal_from_active_listing(self):
        """Advertiser should create a deal from an active listing."""
        listing = _make_listing()
        db = _mock_db(scalar_result=listing)
        user = _make_user(id=1)
        data = DealCreate(listing_id=10, price=Decimal("25.0"), currency="TON")

        deal = await create_deal_from_listing(db, user, data)
        assert deal.listing_id == 10
        assert deal.advertiser_id == 1
        assert deal.owner_id == 2
        assert deal.status == "DRAFT"
        assert deal.price == Decimal("25.0")
        assert deal.currency == "TON"
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_rejects_nonexistent_listing(self):
        """Should raise 404 when listing does not exist."""
        db = _mock_db(scalar_result=None)
        user = _make_user()
        data = DealCreate(listing_id=999, price=Decimal("10.0"))

        with pytest.raises(HTTPException) as exc_info:
            await create_deal_from_listing(db, user, data)
        assert exc_info.value.status_code == 404


class TestGetDealsByUser:
    @pytest.mark.asyncio
    async def test_returns_empty_list(self):
        """Should return empty list when no deals exist."""
        db = _mock_db_scalars([])
        results = await get_deals_by_user(db, 1, role="advertiser")
        assert results == []

    @pytest.mark.asyncio
    async def test_returns_deals_for_owner_role(self):
        """Should query by owner_id when role is owner."""
        d1 = Deal(
            listing_id=10,
            advertiser_id=1,
            owner_id=2,
            price=Decimal("25.0"),
        )
        db = _mock_db_scalars([d1])
        results = await get_deals_by_user(db, 2, role="owner")
        assert len(results) == 1


class TestGetDeal:
    @pytest.mark.asyncio
    async def test_returns_deal_for_participant(self):
        """Should return deal when user is advertiser or owner."""
        deal = Deal(
            listing_id=10,
            advertiser_id=1,
            owner_id=2,
            price=Decimal("25.0"),
        )
        object.__setattr__(deal, "id", 1)
        db = _mock_db(scalar_result=deal)

        result = await get_deal(db, 1, user_id=1)
        assert result.price == Decimal("25.0")

    @pytest.mark.asyncio
    async def test_raises_404_for_missing_deal(self):
        """Should raise 404 when deal does not exist."""
        db = _mock_db(scalar_result=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_deal(db, 999, user_id=1)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_raises_403_for_non_participant(self):
        """Should raise 403 when user is not a participant."""
        deal = Deal(
            listing_id=10,
            advertiser_id=1,
            owner_id=2,
            price=Decimal("25.0"),
        )
        object.__setattr__(deal, "id", 1)
        # First query returns deal, second returns None (no listing found for team check)
        deal_result = MagicMock()
        deal_result.scalar_one_or_none.return_value = deal
        no_result = MagicMock()
        no_result.scalar_one_or_none.return_value = None
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[deal_result, no_result])

        with pytest.raises(HTTPException) as exc_info:
            await get_deal(db, 1, user_id=99)
        assert exc_info.value.status_code == 403


def _make_deal_with_status(status: str = "DRAFT", deal_id: int = 1, brief: str = "Test brief") -> Deal:
    deal = Deal(
        listing_id=10,
        advertiser_id=1,
        owner_id=2,
        price=Decimal("25.0"),
        status=status,
        brief=brief,
        last_activity_at=datetime.now(timezone.utc),
    )
    object.__setattr__(deal, "id", deal_id)
    # Mock relationships for notification
    advertiser = _make_user(id=1)
    advertiser.telegram_id = 111
    owner = User(
        telegram_id=222,
        username="testowner",
        first_name="Owner",
        last_name="User",
        locale="en",
        active_role="owner",
    )
    object.__setattr__(owner, "id", 2)
    deal.advertiser = advertiser
    deal.owner = owner
    return deal


class TestTransitionDeal:
    @pytest.mark.asyncio
    @patch("app.services.notification.notify_deal_status_change", new_callable=AsyncMock)
    async def test_valid_transition(self, mock_notify):
        """Advertiser should transition DRAFT → NEGOTIATION via send."""
        deal = _make_deal_with_status("DRAFT")
        db = _mock_db(scalar_result=deal)
        user = _make_user(id=1)

        result = await transition_deal(db, 1, "send", user)
        assert result.status == "NEGOTIATION"

    @pytest.mark.asyncio
    @patch("app.services.notification.notify_deal_status_change", new_callable=AsyncMock)
    async def test_invalid_transition_returns_409(self, mock_notify):
        """Should raise 409 on invalid transition."""
        deal = _make_deal_with_status("DRAFT")
        db = _mock_db(scalar_result=deal)
        user = _make_user(id=1)

        with pytest.raises(HTTPException) as exc_info:
            await transition_deal(db, 1, "accept", user)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    @patch("app.services.notification.notify_deal_status_change", new_callable=AsyncMock)
    async def test_wrong_role_returns_409(self, mock_notify):
        """Advertiser should not be able to submit creative."""
        deal = _make_deal_with_status("CREATIVE_PENDING_OWNER")
        db = _mock_db(scalar_result=deal)
        user = _make_user(id=1)

        with pytest.raises(HTTPException) as exc_info:
            await transition_deal(db, 1, "submit_creative", user)
        assert exc_info.value.status_code == 409


class TestAddDealMessage:
    @pytest.mark.asyncio
    @patch("app.services.notification.notify_deal_message", new_callable=AsyncMock)
    async def test_message_during_negotiation(self, mock_notify):
        """Should allow messages during NEGOTIATION status."""
        deal = _make_deal_with_status("NEGOTIATION")
        db = _mock_db(scalar_result=deal)
        user = _make_user(id=1)

        msg = await add_deal_message(db, 1, user, "Hello!")
        assert msg.text == "Hello!"
        assert msg.message_type == "text"
        db.add.assert_called()

    @pytest.mark.asyncio
    async def test_message_blocked_in_draft(self):
        """Should reject messages during DRAFT status."""
        deal = _make_deal_with_status("DRAFT")
        db = _mock_db(scalar_result=deal)
        user = _make_user(id=1)

        with pytest.raises(HTTPException) as exc_info:
            await add_deal_message(db, 1, user, "Hello!")
        assert exc_info.value.status_code == 409
