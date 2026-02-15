"""Tests for stats service — snapshot creation and growth calculation."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.channel import Channel
from app.models.channel_stats import ChannelStatsSnapshot
from app.services.stats import _compute_growth, collect_snapshot


def _make_channel(id: int = 1, username: str = "test_ch", subscribers: int = 1000) -> Channel:
    ch = Channel(
        telegram_channel_id=-1001234,
        username=username,
        title="Test Channel",
        subscribers=subscribers,
        avg_views=0,
        bot_is_admin=True,
        owner_id=1,
    )
    object.__setattr__(ch, "id", id)
    return ch


def _make_snapshot(
    channel_id: int,
    subscribers: int,
    created_at: datetime,
) -> ChannelStatsSnapshot:
    s = ChannelStatsSnapshot(
        channel_id=channel_id,
        subscribers=subscribers,
    )
    object.__setattr__(s, "created_at", created_at)
    return s


def _mock_db_for_collect():
    """Create a mock DB that handles the multiple queries in collect_snapshot."""
    db = AsyncMock()

    # Queries in order:
    # 1-2: _compute_growth x2 (7d, 30d) — return None
    # 3: _compute_post_metrics — select views
    # 4: _compute_post_metrics — count posts
    # (no min/max dates when posts_tracked < 2)
    # 5: _compute_engagement_metrics — select views/reactions/forwards
    # 6: _compute_velocity — select post ids
    # 7-8: _compute_frequency_metrics — count 7d, count 30d
    # 9-10: _compute_reliability — total count, edited count

    growth_result = MagicMock()
    growth_result.scalar_one_or_none.return_value = None

    views_result = MagicMock()
    views_result.all.return_value = []  # no posts with views

    count_result = MagicMock()
    count_result.scalar.return_value = 0  # no posts tracked

    engagement_result = MagicMock()
    engagement_result.all.return_value = []  # no posts for engagement

    velocity_result = MagicMock()
    velocity_result.all.return_value = []  # no posts for velocity

    freq_7d_result = MagicMock()
    freq_7d_result.scalar.return_value = 0

    freq_30d_result = MagicMock()
    freq_30d_result.scalar.return_value = 0

    reliability_total = MagicMock()
    reliability_total.scalar.return_value = 0

    reliability_edited = MagicMock()
    reliability_edited.scalar.return_value = 0

    db.execute = AsyncMock(
        side_effect=[
            growth_result, growth_result,
            views_result, count_result,
            engagement_result,
            velocity_result,
            freq_7d_result, freq_30d_result,
            reliability_total, reliability_edited,
        ]
    )
    db.refresh = AsyncMock()
    return db


class TestComputeGrowth:
    @pytest.mark.asyncio
    async def test_no_history_returns_none(self):
        """When no old snapshot exists, growth should be None."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        growth, pct = await _compute_growth(db, channel_id=1, days=7, current_subscribers=5000)
        assert growth is None
        assert pct is None

    @pytest.mark.asyncio
    async def test_positive_growth(self):
        """When subscribers increased, growth should be positive."""
        old_snapshot = _make_snapshot(
            channel_id=1,
            subscribers=4000,
            created_at=datetime.now(timezone.utc) - timedelta(days=8),
        )
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = old_snapshot
        db.execute = AsyncMock(return_value=mock_result)

        growth, pct = await _compute_growth(db, channel_id=1, days=7, current_subscribers=5000)
        assert growth == 1000
        assert pct == 25.0

    @pytest.mark.asyncio
    async def test_negative_growth(self):
        """When subscribers decreased, growth should be negative."""
        old_snapshot = _make_snapshot(
            channel_id=1,
            subscribers=6000,
            created_at=datetime.now(timezone.utc) - timedelta(days=8),
        )
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = old_snapshot
        db.execute = AsyncMock(return_value=mock_result)

        growth, pct = await _compute_growth(db, channel_id=1, days=7, current_subscribers=5000)
        assert growth == -1000
        assert pct == pytest.approx(-16.67, abs=0.01)

    @pytest.mark.asyncio
    async def test_zero_base_subscribers(self):
        """When old snapshot has 0 subscribers, percentage should be None."""
        old_snapshot = _make_snapshot(
            channel_id=1,
            subscribers=0,
            created_at=datetime.now(timezone.utc) - timedelta(days=8),
        )
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = old_snapshot
        db.execute = AsyncMock(return_value=mock_result)

        growth, pct = await _compute_growth(db, channel_id=1, days=7, current_subscribers=100)
        assert growth == 100
        assert pct is None


class TestCollectSnapshot:
    @pytest.mark.asyncio
    @patch("app.services.stats.telegram")
    async def test_creates_snapshot(self, mock_tg):
        """collect_snapshot should fetch from Bot API and create a snapshot."""
        mock_tg.get_chat_member_count = AsyncMock(return_value=5500)
        mock_tg.get_chat = AsyncMock(return_value={
            "id": -1001234,
            "title": "Test Channel",
            "has_visible_history": True,
            "has_aggressive_anti_spam": False,
        })
        mock_tg.get_me = AsyncMock(return_value={"id": 999})
        mock_tg.get_chat_member = AsyncMock(return_value={"status": "administrator"})

        db = _mock_db_for_collect()
        channel = _make_channel(subscribers=5000)

        snapshot = await collect_snapshot(db, channel)

        assert snapshot.subscribers == 5500
        assert snapshot.channel_id == channel.id
        assert snapshot.has_visible_history is True
        assert snapshot.has_aggressive_anti_spam is False
        assert snapshot.posts_tracked == 0
        assert snapshot.avg_views is None
        assert channel.subscribers == 5500
        assert channel.bot_is_admin is True
        db.add.assert_called_once_with(snapshot)
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.services.stats.telegram")
    async def test_falls_back_on_api_error(self, mock_tg):
        """When Bot API fails, snapshot should use existing subscriber count."""
        mock_tg.get_chat_member_count = AsyncMock(side_effect=ValueError("API error"))
        mock_tg.get_chat = AsyncMock(side_effect=ValueError("API error"))
        mock_tg.get_me = AsyncMock(side_effect=ValueError("API error"))

        db = _mock_db_for_collect()
        channel = _make_channel(subscribers=3000)

        snapshot = await collect_snapshot(db, channel)

        assert snapshot.subscribers == 3000
        assert snapshot.has_visible_history is None
        assert snapshot.posts_tracked == 0

    @pytest.mark.asyncio
    @patch("app.services.stats.telegram")
    async def test_bot_admin_status_updated(self, mock_tg):
        """collect_snapshot should update bot_is_admin based on getChatMember."""
        mock_tg.get_chat_member_count = AsyncMock(return_value=1000)
        mock_tg.get_chat = AsyncMock(return_value={
            "id": -1001234, "title": "Test",
        })
        mock_tg.get_me = AsyncMock(return_value={"id": 999})
        mock_tg.get_chat_member = AsyncMock(return_value={"status": "left"})

        db = _mock_db_for_collect()
        channel = _make_channel(subscribers=1000)

        await collect_snapshot(db, channel)

        # Bot lost admin — should be False
        assert channel.bot_is_admin is False
