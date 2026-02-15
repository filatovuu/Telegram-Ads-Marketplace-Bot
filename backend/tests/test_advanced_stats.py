"""Tests for advanced analytics functions: engagement, velocity, frequency, reliability."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.stats import (
    _compute_engagement_metrics,
    _compute_frequency_metrics,
    _compute_reliability,
    _compute_velocity,
)


class TestComputeEngagementMetrics:
    @pytest.mark.asyncio
    async def test_no_posts(self):
        db = AsyncMock()
        result = MagicMock()
        result.all.return_value = []
        db.execute = AsyncMock(return_value=result)

        metrics = await _compute_engagement_metrics(db, channel_id=1)
        assert metrics["reactions_per_views"] is None
        assert metrics["forwards_per_views"] is None

    @pytest.mark.asyncio
    async def test_with_reactions_and_forwards(self):
        db = AsyncMock()
        result = MagicMock()
        # (views, reactions_count, forward_count)
        result.all.return_value = [
            (1000, 50, 20),
            (2000, 100, 40),
            (500, 25, 10),
        ]
        db.execute = AsyncMock(return_value=result)

        metrics = await _compute_engagement_metrics(db, channel_id=1)
        # All ratios are 0.05 for reactions, 0.02 for forwards
        assert metrics["reactions_per_views"] == pytest.approx(0.05, abs=0.001)
        assert metrics["forwards_per_views"] == pytest.approx(0.02, abs=0.001)

    @pytest.mark.asyncio
    async def test_partial_data(self):
        db = AsyncMock()
        result = MagicMock()
        # Only some posts have reactions, none have forwards
        result.all.return_value = [
            (1000, 50, None),
            (2000, None, None),
            (500, 25, None),
        ]
        db.execute = AsyncMock(return_value=result)

        metrics = await _compute_engagement_metrics(db, channel_id=1)
        # Mean of 50/1000=0.05 and 25/500=0.05
        assert metrics["reactions_per_views"] == pytest.approx(0.05, abs=0.001)
        assert metrics["forwards_per_views"] is None


class TestComputeVelocity:
    @pytest.mark.asyncio
    async def test_no_posts(self):
        db = AsyncMock()
        result = MagicMock()
        result.all.return_value = []
        db.execute = AsyncMock(return_value=result)

        metrics = await _compute_velocity(db, channel_id=1)
        assert metrics["velocity_1h_ratio"] is None

    @pytest.mark.asyncio
    async def test_with_snapshots(self):
        now = datetime.now(timezone.utc) - timedelta(days=1)
        post_id = 42

        db = AsyncMock()
        # First call: select posts
        posts_result = MagicMock()
        posts_result.all.return_value = [(post_id, now)]

        # Second call: select view snapshots for post 42
        snaps_result = MagicMock()
        snaps_result.all.return_value = [
            (100, now + timedelta(minutes=5)),       # initial
            (500, now + timedelta(minutes=55)),      # ~1h
            (2000, now + timedelta(hours=23, minutes=50)),  # ~24h
        ]

        db.execute = AsyncMock(side_effect=[posts_result, snaps_result])

        metrics = await _compute_velocity(db, channel_id=1)
        # views_1h=500, views_24h=2000, ratio=0.25
        assert metrics["velocity_1h_ratio"] == pytest.approx(0.25, abs=0.01)

    @pytest.mark.asyncio
    async def test_insufficient_snapshots(self):
        now = datetime.now(timezone.utc) - timedelta(days=1)
        post_id = 42

        db = AsyncMock()
        posts_result = MagicMock()
        posts_result.all.return_value = [(post_id, now)]

        snaps_result = MagicMock()
        snaps_result.all.return_value = [
            (100, now + timedelta(minutes=5)),  # only one snapshot
        ]

        db.execute = AsyncMock(side_effect=[posts_result, snaps_result])

        metrics = await _compute_velocity(db, channel_id=1)
        assert metrics["velocity_1h_ratio"] is None


class TestComputeFrequencyMetrics:
    @pytest.mark.asyncio
    async def test_no_posts(self):
        db = AsyncMock()
        result_7d = MagicMock()
        result_7d.scalar.return_value = 0
        result_30d = MagicMock()
        result_30d.scalar.return_value = 0
        db.execute = AsyncMock(side_effect=[result_7d, result_30d])

        metrics = await _compute_frequency_metrics(db, channel_id=1)
        assert metrics["posts_7d"] == 0
        assert metrics["posts_30d"] == 0
        assert metrics["posts_per_day_7d"] == 0.0
        assert metrics["posts_per_day_30d"] == 0.0

    @pytest.mark.asyncio
    async def test_with_posts(self):
        db = AsyncMock()
        result_7d = MagicMock()
        result_7d.scalar.return_value = 14
        result_30d = MagicMock()
        result_30d.scalar.return_value = 45
        db.execute = AsyncMock(side_effect=[result_7d, result_30d])

        metrics = await _compute_frequency_metrics(db, channel_id=1)
        assert metrics["posts_7d"] == 14
        assert metrics["posts_30d"] == 45
        assert metrics["posts_per_day_7d"] == 2.0
        assert metrics["posts_per_day_30d"] == 1.5


class TestComputeReliability:
    @pytest.mark.asyncio
    async def test_no_posts(self):
        db = AsyncMock()
        total_result = MagicMock()
        total_result.scalar.return_value = 0
        db.execute = AsyncMock(return_value=total_result)

        metrics = await _compute_reliability(db, channel_id=1)
        assert metrics["edit_rate"] is None

    @pytest.mark.asyncio
    async def test_some_edited(self):
        db = AsyncMock()
        total_result = MagicMock()
        total_result.scalar.return_value = 100
        edited_result = MagicMock()
        edited_result.scalar.return_value = 15
        db.execute = AsyncMock(side_effect=[total_result, edited_result])

        metrics = await _compute_reliability(db, channel_id=1)
        assert metrics["edit_rate"] == 0.15

    @pytest.mark.asyncio
    async def test_none_edited(self):
        db = AsyncMock()
        total_result = MagicMock()
        total_result.scalar.return_value = 50
        edited_result = MagicMock()
        edited_result.scalar.return_value = 0
        db.execute = AsyncMock(side_effect=[total_result, edited_result])

        metrics = await _compute_reliability(db, channel_id=1)
        assert metrics["edit_rate"] == 0.0
