"""Tests for MTProto service — post data extraction, enrichment, graceful degradation."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.channel import Channel
from app.models.channel_post import ChannelPost
from app.services.mtproto import PostData, _extract_post_data, enrich_channel_posts


def _make_channel(id: int = 1) -> Channel:
    ch = Channel(
        telegram_channel_id=-1001234567890,
        username="test_ch",
        title="Test Channel",
        subscribers=1000,
        avg_views=0,
        bot_is_admin=True,
        owner_id=1,
    )
    object.__setattr__(ch, "id", id)
    return ch


def _make_pyrogram_message(
    msg_id: int = 42,
    views: int | None = 1500,
    forwards: int | None = 10,
    reactions: list[int] | None = None,
    text: str | None = "Hello world",
    caption: str | None = None,
    media=None,
    date: datetime | None = None,
    edit_date: datetime | None = None,
) -> MagicMock:
    """Create a mock Pyrogram Message object."""
    msg = MagicMock()
    msg.id = msg_id
    msg.views = views
    msg.forwards = forwards
    msg.text = text
    msg.caption = caption
    msg.media = media
    msg.date = date or datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)
    msg.edit_date = edit_date
    msg.empty = False
    msg.service = None

    if reactions is not None:
        mock_reactions = []
        for count in reactions:
            r = MagicMock()
            r.count = count
            mock_reactions.append(r)
        msg.reactions = MagicMock()
        msg.reactions.reactions = mock_reactions
    else:
        msg.reactions = None

    return msg


class TestExtractPostData:
    def test_basic_text_post(self):
        """Should extract views, forwards, and text from a simple text post."""
        msg = _make_pyrogram_message(
            msg_id=100,
            views=2500,
            forwards=15,
            text="Test post content",
        )

        result = _extract_post_data(msg)

        assert isinstance(result, PostData)
        assert result.telegram_message_id == 100
        assert result.views == 2500
        assert result.forward_count == 15
        assert result.reactions_count is None
        assert result.text_preview == "Test post content"
        assert result.has_media is False
        assert result.post_type == "text"

    def test_post_with_reactions(self):
        """Should sum up all reaction counts."""
        msg = _make_pyrogram_message(
            reactions=[10, 5, 3],  # 18 total reactions
        )

        result = _extract_post_data(msg)

        assert result.reactions_count == 18

    def test_post_with_no_views(self):
        """Posts without views should have views=None."""
        msg = _make_pyrogram_message(views=None, forwards=None)

        result = _extract_post_data(msg)

        assert result.views is None
        assert result.forward_count is None

    def test_caption_used_when_no_text(self):
        """Should fall back to caption when text is None."""
        msg = _make_pyrogram_message(text=None, caption="Photo caption")

        result = _extract_post_data(msg)

        assert result.text_preview == "Photo caption"

    def test_text_preview_truncated(self):
        """Long text should be truncated to 500 chars."""
        long_text = "A" * 1000
        msg = _make_pyrogram_message(text=long_text)

        result = _extract_post_data(msg)

        assert len(result.text_preview) == 500

    def test_naive_datetime_gets_utc(self):
        """Naive datetimes should get UTC timezone attached."""
        naive_date = datetime(2025, 6, 1, 12, 0)
        msg = _make_pyrogram_message(date=naive_date)

        result = _extract_post_data(msg)

        assert result.date.tzinfo == timezone.utc

    def test_media_post_detection(self):
        """Posts with media should be detected correctly."""
        try:
            from pyrogram import enums
            media_value = enums.MessageMediaType.PHOTO
        except ImportError:
            # Pyrogram not installed — use a mock whose str() contains "photo"
            media_value = MagicMock()
            media_value.__str__ = lambda self: "MessageMediaType.PHOTO"

        msg = _make_pyrogram_message()
        msg.media = media_value

        result = _extract_post_data(msg)

        assert result.has_media is True
        assert result.post_type == "photo"


class TestEnrichChannelPosts:
    @pytest.mark.asyncio
    @patch("app.services.mtproto.fetch_channel_posts")
    async def test_enriches_existing_post(self, mock_fetch):
        """Should update views when new value is higher."""
        mock_fetch.return_value = [
            PostData(
                telegram_message_id=42,
                views=2000,
                forward_count=20,
                reactions_count=50,
                date=datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc),
                edit_date=None,
                text_preview="Test",
                has_media=False,
                post_type="text",
            )
        ]

        # Existing post with lower views
        existing_post = MagicMock(spec=ChannelPost)
        existing_post.id = 10
        existing_post.views = 1000
        existing_post.reactions_count = None
        existing_post.forward_count = None
        existing_post.edit_date = None

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_post
        db.execute = AsyncMock(return_value=mock_result)

        channel = _make_channel()
        count = await enrich_channel_posts(db, channel, limit=10)

        assert count == 1
        assert existing_post.views == 2000
        assert existing_post.reactions_count == 50
        assert existing_post.forward_count == 20
        db.flush.assert_awaited()

    @pytest.mark.asyncio
    @patch("app.services.mtproto.fetch_channel_posts")
    async def test_does_not_lower_views(self, mock_fetch):
        """Should NOT update views when new value is lower (views only go up)."""
        mock_fetch.return_value = [
            PostData(
                telegram_message_id=42,
                views=500,
                forward_count=None,
                reactions_count=None,
                date=datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc),
                edit_date=None,
                text_preview="Test",
                has_media=False,
                post_type="text",
            )
        ]

        existing_post = MagicMock(spec=ChannelPost)
        existing_post.id = 10
        existing_post.views = 1000
        existing_post.reactions_count = None
        existing_post.forward_count = None
        existing_post.edit_date = None

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_post
        db.execute = AsyncMock(return_value=mock_result)

        channel = _make_channel()
        count = await enrich_channel_posts(db, channel, limit=10)

        # Views should remain at 1000
        assert existing_post.views == 1000
        assert count == 0

    @pytest.mark.asyncio
    @patch("app.services.mtproto.fetch_channel_posts")
    async def test_creates_new_post_on_backfill(self, mock_fetch):
        """Should create a new ChannelPost for posts not yet in the database."""
        mock_fetch.return_value = [
            PostData(
                telegram_message_id=99,
                views=3000,
                forward_count=5,
                reactions_count=30,
                date=datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc),
                edit_date=None,
                text_preview="New post",
                has_media=True,
                post_type="photo",
            )
        ]

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # Post not found
        db.execute = AsyncMock(return_value=mock_result)

        channel = _make_channel()
        count = await enrich_channel_posts(db, channel, limit=10)

        assert count == 1
        # Should have called db.add for the new post + view snapshot
        assert db.add.call_count >= 1

    @pytest.mark.asyncio
    @patch("app.services.mtproto.fetch_channel_posts")
    async def test_empty_posts_returns_zero(self, mock_fetch):
        """When fetch returns no posts, should return 0 and not touch DB."""
        mock_fetch.return_value = []

        db = AsyncMock()
        channel = _make_channel()
        count = await enrich_channel_posts(db, channel, limit=10)

        assert count == 0
        db.execute.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("app.services.mtproto.get_client")
    async def test_graceful_skip_when_not_configured(self, mock_get_client):
        """When MTProto is not configured, fetch_channel_posts returns []."""
        mock_get_client.return_value = None

        from app.services.mtproto import fetch_channel_posts

        result = await fetch_channel_posts(-1001234, limit=10)

        assert result == []
