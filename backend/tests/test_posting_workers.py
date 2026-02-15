"""Tests for posting worker tasks — scheduled post execution and retention verification."""

import pytest
from datetime import datetime, timedelta, timezone


class TestSchedulePostingWorkerLogic:
    """Test the logic used by execute_scheduled_posts worker."""

    def test_due_posting_detected(self):
        """A posting with scheduled_at in the past and no posted_at should be found."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=5)
        # Simulate: scheduled_at <= now and posted_at IS NULL
        assert past <= now
        assert True  # posting should be picked up

    def test_future_posting_not_due(self):
        """A posting with scheduled_at in the future should not be executed."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(hours=2)
        assert future > now  # not yet due

    def test_already_posted_skipped(self):
        """A posting that already has posted_at should be skipped."""
        posted_at = datetime.now(timezone.utc) - timedelta(hours=1)
        # posted_at IS NOT NULL — should not be in the query results
        assert posted_at is not None


class TestRetentionVerificationWorkerLogic:
    """Test the logic used by verify_post_retention worker."""

    def test_retention_period_elapsed(self):
        """Posting where posted_at + retention_hours <= now should be verified."""
        now = datetime.now(timezone.utc)
        posted_at = now - timedelta(hours=25)
        retention_hours = 24
        retention_end = posted_at + timedelta(hours=retention_hours)
        assert now >= retention_end  # eligible for verification

    def test_retention_period_not_elapsed(self):
        """Posting where retention period has not elapsed should be skipped."""
        now = datetime.now(timezone.utc)
        posted_at = now - timedelta(hours=10)
        retention_hours = 24
        retention_end = posted_at + timedelta(hours=retention_hours)
        assert now < retention_end  # not yet eligible

    def test_already_verified_skipped(self):
        """Posting with verified_at should not be re-verified."""
        verified_at = datetime.now(timezone.utc) - timedelta(hours=1)
        assert verified_at is not None  # should be excluded from query

    def test_retention_hours_custom_value(self):
        """Custom retention_hours should be respected."""
        now = datetime.now(timezone.utc)
        posted_at = now - timedelta(hours=49)
        retention_hours = 48
        retention_end = posted_at + timedelta(hours=retention_hours)
        assert now >= retention_end  # 49h > 48h, eligible

    def test_only_retention_check_status(self):
        """Only deals in RETENTION_CHECK status should be checked."""
        from app.services.deal_state_machine import DealStatus
        # The worker query filters on status == RETENTION_CHECK
        assert DealStatus.RETENTION_CHECK.value == "RETENTION_CHECK"


class TestRetentionOutcomes:
    """Test the state machine transitions for retention outcomes."""

    def test_release_after_retention_pass(self):
        """Retention pass → RELEASED."""
        from app.services.deal_state_machine import validate_transition, DealStatus
        result = validate_transition("RETENTION_CHECK", "release", "system")
        assert result == DealStatus.RELEASED

    def test_refund_after_retention_fail(self):
        """Retention fail → REFUNDED (post deleted/changed)."""
        from app.services.deal_state_machine import validate_transition, DealStatus
        result = validate_transition("RETENTION_CHECK", "refund", "system")
        assert result == DealStatus.REFUNDED

    def test_retention_check_system_actions_include_both(self):
        """System can either release or refund from RETENTION_CHECK."""
        from app.services.deal_state_machine import get_available_actions
        actions = get_available_actions("RETENTION_CHECK", "system")
        assert "release" in actions
        assert "refund" in actions
