"""Tests for channel service — ownership validation with mocked Telegram API."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.channel import Channel
from app.models.user import User
from app.services.channel import create_channel


def _make_user(id: int = 1, telegram_id: int = 111, wallet_address: str | None = "EQ_test_wallet") -> User:
    user = User(
        telegram_id=telegram_id,
        username="testowner",
        first_name="Test",
        last_name="Owner",
        locale="en",
        active_role="owner",
        wallet_address=wallet_address,
    )
    object.__setattr__(user, "id", id)
    return user


def _mock_db(scalar_result=None):
    """Create a mock AsyncSession whose execute().scalar_one_or_none() returns scalar_result."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = scalar_result
    db.execute = AsyncMock(return_value=mock_result)
    return db


def _setup_bot_admin_mock(mock_tg, is_admin: bool = True):
    """Configure the mock so _check_bot_is_admin returns the desired result."""
    mock_tg.get_me = AsyncMock(return_value={"id": 999, "username": "test_bot"})
    if is_admin:
        # For bot admin check — returns admin status
        original_get_chat_member = mock_tg.get_chat_member

        async def _get_chat_member(chat_id, user_id):
            if user_id == 999:  # bot id
                return {"status": "administrator"}
            return await original_get_chat_member(chat_id, user_id)

        mock_tg.get_chat_member = AsyncMock(side_effect=_get_chat_member)


class TestChannelOwnershipValidation:
    @pytest.mark.asyncio
    @patch("app.services.channel.telegram")
    async def test_rejects_non_admin(self, mock_tg):
        """User who is not admin/creator of the channel should be rejected."""
        mock_tg.get_chat = AsyncMock(return_value={"id": -1001234, "title": "Test", "username": "test_ch"})
        mock_tg.get_chat_member = AsyncMock(return_value={"status": "member"})

        db = _mock_db()
        user = _make_user()

        with pytest.raises(HTTPException) as exc_info:
            await create_channel(db, user, "test_ch")
        assert exc_info.value.status_code == 403
        assert "not an admin" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("app.services.channel.telegram")
    async def test_rejects_invalid_channel(self, mock_tg):
        """Non-existent channel should raise 404 with helpful message."""
        mock_tg.get_chat = AsyncMock(side_effect=ValueError("Bad Request: chat not found"))

        db = _mock_db()
        user = _make_user()

        with pytest.raises(HTTPException) as exc_info:
            await create_channel(db, user, "nonexistent")
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("app.services.channel.telegram")
    async def test_rejects_bot_not_admin(self, mock_tg):
        """Should reject when bot is not an admin of the channel."""
        mock_tg.get_chat = AsyncMock(return_value={
            "id": -1001234,
            "title": "No Bot Admin",
            "username": "no_bot_admin",
        })
        # User is creator, but bot is not admin
        mock_tg.get_me = AsyncMock(return_value={"id": 999, "username": "test_bot"})

        async def _get_chat_member(chat_id, user_id):
            if user_id == 999:  # bot
                return {"status": "member"}  # not admin
            return {"status": "creator"}  # user is creator

        mock_tg.get_chat_member = AsyncMock(side_effect=_get_chat_member)

        db = _mock_db()
        user = _make_user()

        with pytest.raises(HTTPException) as exc_info:
            await create_channel(db, user, "no_bot_admin")
        assert exc_info.value.status_code == 400
        assert "@test_bot" in exc_info.value.detail
        assert "administrator" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("app.services.channel.telegram")
    async def test_accepts_creator(self, mock_tg):
        """Channel creator should be accepted when bot is also admin."""
        mock_tg.get_chat = AsyncMock(return_value={
            "id": -1001234,
            "title": "My Channel",
            "username": "my_channel",
            "description": "desc",
            "invite_link": None,
        })
        mock_tg.get_me = AsyncMock(return_value={"id": 999, "username": "test_bot"})
        mock_tg.get_chat_member_count = AsyncMock(return_value=5000)

        async def _get_chat_member(chat_id, user_id):
            if user_id == 999:
                return {"status": "administrator"}
            return {"status": "creator"}

        mock_tg.get_chat_member = AsyncMock(side_effect=_get_chat_member)

        db = _mock_db(scalar_result=None)
        user = _make_user()

        channel = await create_channel(db, user, "my_channel")

        assert channel.telegram_channel_id == -1001234
        assert channel.title == "My Channel"
        assert channel.subscribers == 5000
        assert channel.is_verified is True
        assert channel.bot_is_admin is True
        assert channel.owner_id == user.id
        db.add.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.channel.telegram")
    async def test_accepts_administrator(self, mock_tg):
        """Channel administrator should also be accepted."""
        mock_tg.get_chat = AsyncMock(return_value={
            "id": -1001235,
            "title": "Admin Channel",
            "username": "admin_ch",
        })
        mock_tg.get_me = AsyncMock(return_value={"id": 999, "username": "test_bot"})
        mock_tg.get_chat_member_count = AsyncMock(return_value=1200)

        async def _get_chat_member(chat_id, user_id):
            return {"status": "administrator"}

        mock_tg.get_chat_member = AsyncMock(side_effect=_get_chat_member)

        db = _mock_db(scalar_result=None)
        user = _make_user()

        channel = await create_channel(db, user, "admin_ch")

        assert channel.telegram_channel_id == -1001235
        assert channel.subscribers == 1200

    @pytest.mark.asyncio
    @patch("app.services.channel.telegram")
    async def test_rejects_duplicate_channel(self, mock_tg):
        """Already registered channel should raise 409 with helpful message."""
        mock_tg.get_chat = AsyncMock(return_value={"id": -1001234, "title": "Test", "username": "test_ch"})
        mock_tg.get_me = AsyncMock(return_value={"id": 999, "username": "test_bot"})

        async def _get_chat_member(chat_id, user_id):
            return {"status": "creator"}

        mock_tg.get_chat_member = AsyncMock(side_effect=_get_chat_member)

        existing_channel = Channel(
            telegram_channel_id=-1001234,
            title="Test",
            owner_id=1,
        )
        db = _mock_db(scalar_result=existing_channel)
        user = _make_user()

        with pytest.raises(HTTPException) as exc_info:
            await create_channel(db, user, "test_ch")
        assert exc_info.value.status_code == 409
        assert "already registered" in exc_info.value.detail
