"""Tests for stats API endpoints."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.deps import get_db
from app.core.security import get_current_user
from app.main import app
from app.models.channel import Channel
from app.models.channel_stats import ChannelStatsSnapshot
from app.models.user import User


def _make_user() -> User:
    user = User(
        telegram_id=111,
        username="testowner",
        first_name="Test",
        last_name="Owner",
        locale="en",
        active_role="owner",
    )
    object.__setattr__(user, "id", 1)
    return user


def _make_channel() -> Channel:
    ch = Channel(
        telegram_channel_id=-1001234,
        username="test_ch",
        title="Test Channel",
        subscribers=5000,
        avg_views=0,
        bot_is_admin=True,
        owner_id=1,
    )
    object.__setattr__(ch, "id", 10)
    return ch


def _make_snapshot(created_at: datetime | None = None) -> ChannelStatsSnapshot:
    s = ChannelStatsSnapshot(
        channel_id=10,
        subscribers=5000,
        subscribers_growth_7d=500,
        subscribers_growth_30d=1500,
        subscribers_growth_pct_7d=11.11,
        subscribers_growth_pct_30d=42.86,
        has_visible_history=True,
        has_aggressive_anti_spam=False,
        avg_views=2500,
        avg_views_10=2800,
        avg_views_30=2600,
        avg_views_50=2400,
        median_views=2300,
        reach_pct=50.0,
        posts_per_week=3.5,
        posts_tracked=42,
        reactions_per_views=0.025,
        forwards_per_views=0.01,
        velocity_1h_ratio=0.45,
        posts_7d=7,
        posts_30d=28,
        posts_per_day_7d=1.0,
        posts_per_day_30d=0.93,
        edit_rate=0.05,
        source="bot_api",
    )
    ts = created_at or datetime.now(timezone.utc)
    object.__setattr__(s, "created_at", ts)
    object.__setattr__(s, "updated_at", ts)
    return s


def _mock_db():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = _make_channel()
    db.execute = AsyncMock(return_value=mock_result)
    return db


@pytest.fixture
async def client():
    user = _make_user()
    db = _mock_db()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestGetChannelStats:
    @pytest.mark.asyncio
    @patch("app.api.owner.stats_svc.get_latest_snapshot")
    @patch("app.api.owner.channel_svc.get_channel")
    async def test_returns_stats(self, mock_get_ch, mock_latest, client):
        mock_get_ch.return_value = _make_channel()
        mock_latest.return_value = _make_snapshot()

        resp = await client.get("/api/owner/channels/10/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["channel_id"] == 10
        assert data["subscribers"] == 5000
        assert data["subscribers_growth_pct_7d"] == 11.11
        assert data["avg_views"] == 2500
        assert data["avg_views_10"] == 2800
        assert data["median_views"] == 2300
        assert data["reach_pct"] == 50.0
        assert data["posts_tracked"] == 42
        assert data["posts_per_week"] == 3.5
        assert data["reactions_per_views"] == 0.025
        assert data["forwards_per_views"] == 0.01
        assert data["velocity_1h_ratio"] == 0.45
        assert data["posts_7d"] == 7
        assert data["posts_30d"] == 28
        assert data["posts_per_day_7d"] == 1.0
        assert data["posts_per_day_30d"] == 0.93
        assert data["edit_rate"] == 0.05

    @pytest.mark.asyncio
    @patch("app.api.owner.stats_svc.get_latest_snapshot")
    @patch("app.api.owner.channel_svc.get_channel")
    async def test_404_when_no_stats(self, mock_get_ch, mock_latest, client):
        mock_get_ch.return_value = _make_channel()
        mock_latest.return_value = None

        resp = await client.get("/api/owner/channels/10/stats")
        assert resp.status_code == 404


class TestRefreshStatsSnapshot:
    @pytest.mark.asyncio
    @patch("app.api.owner.stats_svc.collect_snapshot")
    @patch("app.api.owner.stats_svc.get_latest_snapshot")
    @patch("app.api.owner.channel_svc.get_channel")
    async def test_refresh_creates_snapshot(self, mock_get_ch, mock_latest, mock_collect, client):
        mock_get_ch.return_value = _make_channel()
        mock_latest.return_value = None
        mock_collect.return_value = _make_snapshot()

        resp = await client.post("/api/owner/channels/10/stats/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert data["subscribers"] == 5000
        assert data["posts_tracked"] == 42
        assert data["avg_views"] == 2500
        mock_collect.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.api.owner.stats_svc.get_latest_snapshot")
    @patch("app.api.owner.channel_svc.get_channel")
    async def test_rate_limited(self, mock_get_ch, mock_latest, client):
        mock_get_ch.return_value = _make_channel()
        mock_latest.return_value = _make_snapshot(
            created_at=datetime.now(timezone.utc)
        )

        resp = await client.post("/api/owner/channels/10/stats/refresh")
        assert resp.status_code == 429
        assert "once per hour" in resp.json()["detail"]
