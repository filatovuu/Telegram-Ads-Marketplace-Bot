"""Tests for posting service — schedule, auto-post, retention verification."""

import pytest
from app.services.deal_state_machine import DealStatus, validate_transition, InvalidTransitionError


class TestScheduleTransitions:
    """Test scheduling state transitions."""

    def test_owner_can_schedule_from_approved(self):
        result = validate_transition("CREATIVE_APPROVED", "schedule", "owner")
        assert result == DealStatus.SCHEDULED

    def test_system_can_schedule(self):
        result = validate_transition("CREATIVE_APPROVED", "schedule", "system")
        assert result == DealStatus.SCHEDULED

    def test_advertiser_cannot_schedule(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition("CREATIVE_APPROVED", "schedule", "advertiser")

    def test_cannot_schedule_from_wrong_status(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition("CREATIVE_SUBMITTED", "schedule", "owner")


class TestPostTransitions:
    """Test posting state transitions."""

    def test_system_mark_posted(self):
        result = validate_transition("SCHEDULED", "mark_posted", "system")
        assert result == DealStatus.POSTED

    def test_non_system_cannot_mark_posted(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition("SCHEDULED", "mark_posted", "owner")

    def test_system_start_retention(self):
        result = validate_transition("POSTED", "start_retention", "system")
        assert result == DealStatus.RETENTION_CHECK

    def test_non_system_cannot_start_retention(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition("POSTED", "start_retention", "owner")


class TestRetentionTransitions:
    """Test retention verification transitions."""

    def test_system_release(self):
        result = validate_transition("RETENTION_CHECK", "release", "system")
        assert result == DealStatus.RELEASED

    def test_non_system_cannot_release(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition("RETENTION_CHECK", "release", "owner")

    def test_system_refund_from_scheduled(self):
        """System can refund from SCHEDULED (timeout)."""
        result = validate_transition("SCHEDULED", "refund", "system")
        assert result == DealStatus.REFUNDED


class TestFullPostingLifecycle:
    """Test the complete posting lifecycle through state machine."""

    def test_full_posting_cycle(self):
        """CREATIVE_APPROVED → SCHEDULED → POSTED → RETENTION_CHECK → RELEASED."""
        status = validate_transition("CREATIVE_APPROVED", "schedule", "owner")
        assert status == DealStatus.SCHEDULED

        status = validate_transition(status, "mark_posted", "system")
        assert status == DealStatus.POSTED

        status = validate_transition(status, "start_retention", "system")
        assert status == DealStatus.RETENTION_CHECK

        status = validate_transition(status, "release", "system")
        assert status == DealStatus.RELEASED

    def test_escrow_funded_to_release(self):
        """Full path from ESCROW_FUNDED through creative and posting to RELEASED."""
        status = validate_transition("ESCROW_FUNDED", "request_creative", "system")
        assert status == DealStatus.CREATIVE_PENDING_OWNER

        status = validate_transition(status, "submit_creative", "owner")
        assert status == DealStatus.CREATIVE_SUBMITTED

        status = validate_transition(status, "approve_creative", "advertiser")
        assert status == DealStatus.CREATIVE_APPROVED

        status = validate_transition(status, "schedule", "owner")
        assert status == DealStatus.SCHEDULED

        status = validate_transition(status, "mark_posted", "system")
        assert status == DealStatus.POSTED

        status = validate_transition(status, "start_retention", "system")
        assert status == DealStatus.RETENTION_CHECK

        status = validate_transition(status, "release", "system")
        assert status == DealStatus.RELEASED


class TestPostingAvailableActions:
    """Test available actions for posting-related statuses."""

    def test_scheduled_system_actions(self):
        from app.services.deal_state_machine import get_available_actions
        actions = get_available_actions("SCHEDULED", "system")
        assert "mark_posted" in actions
        assert "refund" in actions

    def test_posted_system_actions(self):
        from app.services.deal_state_machine import get_available_actions
        actions = get_available_actions("POSTED", "system")
        assert "start_retention" in actions

    def test_retention_check_system_actions(self):
        from app.services.deal_state_machine import get_available_actions
        actions = get_available_actions("RETENTION_CHECK", "system")
        assert "release" in actions

    def test_scheduled_owner_no_system_actions(self):
        from app.services.deal_state_machine import get_available_actions
        actions = get_available_actions("SCHEDULED", "owner")
        assert "mark_posted" not in actions

    def test_posted_advertiser_no_system_actions(self):
        from app.services.deal_state_machine import get_available_actions
        actions = get_available_actions("POSTED", "advertiser")
        assert "start_retention" not in actions
