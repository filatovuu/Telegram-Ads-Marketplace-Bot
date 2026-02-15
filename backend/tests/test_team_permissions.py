"""Unit tests for team_permissions service — permission logic only (no DB)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.channel import Channel
from app.models.channel_team import ChannelTeamMember
from app.services.team_permissions import (
    get_user_role_for_channel,
    has_permission,
)


def _make_channel(owner_id: int = 1) -> Channel:
    ch = Channel(telegram_channel_id=-1001234, title="Test", owner_id=owner_id)
    object.__setattr__(ch, "id", 10)
    return ch


def _make_member(
    role: str = "manager",
    can_accept_deals: bool = False,
    can_post: bool = False,
    can_payout: bool = False,
) -> ChannelTeamMember:
    m = ChannelTeamMember(
        channel_id=10,
        user_id=99,
        role=role,
        can_accept_deals=can_accept_deals,
        can_post=can_post,
        can_payout=can_payout,
    )
    object.__setattr__(m, "id", 50)
    return m


# ---------- has_permission ----------


class TestHasPermission:
    def test_owner_has_all_permissions(self):
        assert has_permission("owner", None, "can_accept_deals") is True
        assert has_permission("owner", None, "can_post") is True
        assert has_permission("owner", None, "can_payout") is True

    def test_viewer_has_no_permissions(self):
        member = _make_member(role="viewer", can_accept_deals=True)
        assert has_permission("viewer", member, "can_accept_deals") is False
        assert has_permission("viewer", member, "can_post") is False

    def test_manager_checks_flag(self):
        member = _make_member(role="manager", can_accept_deals=True, can_post=False)
        assert has_permission("manager", member, "can_accept_deals") is True
        assert has_permission("manager", member, "can_post") is False
        assert has_permission("manager", member, "can_payout") is False

    def test_unknown_role_returns_false(self):
        member = _make_member(role="alien")
        assert has_permission("alien", member, "can_post") is False


# ---------- get_user_role_for_channel ----------


class TestGetUserRoleForChannel:
    @pytest.mark.asyncio
    async def test_owner_by_fk(self):
        ch = _make_channel(owner_id=1)
        db = AsyncMock()
        role, member = await get_user_role_for_channel(db, ch, 1)
        assert role == "owner"
        assert member is None

    @pytest.mark.asyncio
    async def test_manager_via_membership(self):
        ch = _make_channel(owner_id=1)
        team_member = _make_member(role="manager")

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = team_member
        db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.services.team_permissions.get_team_membership",
            return_value=team_member,
        ):
            role, member = await get_user_role_for_channel(db, ch, 99)
            assert role == "manager"
            assert member == team_member

    @pytest.mark.asyncio
    async def test_no_access(self):
        ch = _make_channel(owner_id=1)
        db = AsyncMock()

        with patch(
            "app.services.team_permissions.get_team_membership",
            return_value=None,
        ):
            role, member = await get_user_role_for_channel(db, ch, 999)
            assert role is None
            assert member is None
