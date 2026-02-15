"""Unit tests for team-based deal access — _actor_for_user, permission checks."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.channel import Channel
from app.models.channel_team import ChannelTeamMember
from app.models.deal import Deal
from app.models.listing import Listing
from app.models.user import User
from app.services.deal import _actor_for_user, _check_team_permission_for_action


def _make_user(id: int = 1, telegram_id: int = 111) -> User:
    user = User(
        telegram_id=telegram_id,
        username="testuser",
        first_name="Test",
        locale="en",
        active_role="owner",
    )
    object.__setattr__(user, "id", id)
    return user


def _make_deal(
    id: int = 1,
    advertiser_id: int = 10,
    owner_id: int = 20,
    listing_id: int = 100,
    status: str = "NEGOTIATION",
) -> Deal:
    deal = Deal(
        advertiser_id=advertiser_id,
        owner_id=owner_id,
        listing_id=listing_id,
        status=status,
        price=Decimal("10.0"),
        currency="TON",
    )
    object.__setattr__(deal, "id", id)
    return deal


def _make_listing(id: int = 100, channel_id: int = 5) -> Listing:
    listing = Listing(
        channel_id=channel_id,
        title="Test Listing",
        price=Decimal("10.0"),
    )
    object.__setattr__(listing, "id", id)
    return listing


def _make_channel(id: int = 5, telegram_channel_id: int = -1001234) -> Channel:
    ch = Channel(
        telegram_channel_id=telegram_channel_id,
        title="Test Channel",
        owner_id=20,
    )
    object.__setattr__(ch, "id", id)
    return ch


def _make_member(
    user_id: int = 30,
    channel_id: int = 5,
    role: str = "manager",
    can_accept_deals: bool = False,
    can_post: bool = False,
    can_payout: bool = False,
) -> ChannelTeamMember:
    m = ChannelTeamMember(
        channel_id=channel_id,
        user_id=user_id,
        role=role,
        can_accept_deals=can_accept_deals,
        can_post=can_post,
        can_payout=can_payout,
    )
    object.__setattr__(m, "id", 50)
    return m


def _mock_scalar(value):
    """Create a MagicMock result with scalar_one_or_none returning value."""
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


class TestActorForUser:
    @pytest.mark.asyncio
    async def test_advertiser(self):
        deal = _make_deal(advertiser_id=10)
        db = AsyncMock()
        actor = await _actor_for_user(db, deal, 10)
        assert actor == "advertiser"

    @pytest.mark.asyncio
    async def test_owner(self):
        deal = _make_deal(owner_id=20)
        db = AsyncMock()
        actor = await _actor_for_user(db, deal, 20)
        assert actor == "owner"

    @pytest.mark.asyncio
    async def test_team_member_returns_owner(self):
        deal = _make_deal(listing_id=100)
        listing = _make_listing(id=100, channel_id=5)
        member = _make_member(user_id=30, channel_id=5)

        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[_mock_scalar(listing), _mock_scalar(member)]
        )

        actor = await _actor_for_user(db, deal, 30)
        assert actor == "owner"

    @pytest.mark.asyncio
    async def test_stranger_raises_403(self):
        deal = _make_deal(listing_id=100)
        listing = _make_listing(id=100, channel_id=5)

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_mock_scalar(listing), _mock_scalar(None)])

        with pytest.raises(HTTPException) as exc:
            await _actor_for_user(db, deal, 999)
        assert exc.value.status_code == 403


class TestCheckTeamPermissionForAction:
    @pytest.mark.asyncio
    async def test_owner_always_passes(self):
        deal = _make_deal(owner_id=20)
        user = _make_user(id=20, telegram_id=222)
        db = AsyncMock()
        # Should not raise for the actual owner (early return)
        await _check_team_permission_for_action(db, deal, user, "accept")

    @pytest.mark.asyncio
    async def test_manager_with_permission_passes(self):
        deal = _make_deal(owner_id=20, listing_id=100)
        user = _make_user(id=30, telegram_id=333)
        listing = _make_listing(id=100, channel_id=5)
        channel = _make_channel(id=5)
        member = _make_member(
            user_id=30, channel_id=5, role="manager", can_accept_deals=True
        )

        # 3 db.execute calls: listing, member (via get_team_membership), channel
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                _mock_scalar(listing),
                _mock_scalar(member),
                _mock_scalar(channel),
            ]
        )

        with patch(
            "app.services.team_permissions.check_telegram_admin_cached",
            new_callable=AsyncMock,
            return_value=True,
        ):
            # Should not raise
            await _check_team_permission_for_action(db, deal, user, "accept")

    @pytest.mark.asyncio
    async def test_manager_without_permission_raises(self):
        deal = _make_deal(owner_id=20, listing_id=100)
        user = _make_user(id=30, telegram_id=333)
        listing = _make_listing(id=100, channel_id=5)
        member = _make_member(
            user_id=30, channel_id=5, role="manager", can_accept_deals=False
        )

        # Only 2 calls needed: listing, member — raises before channel query
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[_mock_scalar(listing), _mock_scalar(member)]
        )

        with pytest.raises(HTTPException) as exc:
            await _check_team_permission_for_action(db, deal, user, "accept")
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_always_blocked(self):
        deal = _make_deal(owner_id=20, listing_id=100)
        user = _make_user(id=30, telegram_id=333)
        listing = _make_listing(id=100, channel_id=5)
        member = _make_member(
            user_id=30, channel_id=5, role="viewer", can_accept_deals=True
        )

        # Only 2 calls needed: listing, member — raises before channel query
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[_mock_scalar(listing), _mock_scalar(member)]
        )

        with pytest.raises(HTTPException) as exc:
            await _check_team_permission_for_action(db, deal, user, "accept")
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_not_tg_admin_blocked(self):
        deal = _make_deal(owner_id=20, listing_id=100)
        user = _make_user(id=30, telegram_id=333)
        listing = _make_listing(id=100, channel_id=5)
        channel = _make_channel(id=5)
        member = _make_member(
            user_id=30, channel_id=5, role="manager", can_accept_deals=True
        )

        # 3 db.execute calls: listing, member, channel
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                _mock_scalar(listing),
                _mock_scalar(member),
                _mock_scalar(channel),
            ]
        )

        with patch(
            "app.services.team_permissions.check_telegram_admin_cached",
            new_callable=AsyncMock,
            return_value=False,
        ):
            with pytest.raises(HTTPException) as exc:
                await _check_team_permission_for_action(db, deal, user, "accept")
            assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_unmapped_action_passes(self):
        """Actions not in _ACTION_PERMISSIONS should pass without permission check."""
        deal = _make_deal(owner_id=20, listing_id=100)
        user = _make_user(id=30, telegram_id=333)
        listing = _make_listing(id=100, channel_id=5)
        channel = _make_channel(id=5)
        member = _make_member(
            user_id=30, channel_id=5, role="manager", can_accept_deals=False
        )

        # 3 db.execute calls: listing, member, channel
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                _mock_scalar(listing),
                _mock_scalar(member),
                _mock_scalar(channel),
            ]
        )

        with patch(
            "app.services.team_permissions.check_telegram_admin_cached",
            new_callable=AsyncMock,
            return_value=True,
        ):
            # "release" is not in _ACTION_PERMISSIONS — should pass
            await _check_team_permission_for_action(db, deal, user, "release")
