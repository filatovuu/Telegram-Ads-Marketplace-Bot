"""Tests for creative version management service."""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.deal_state_machine import DealStatus


class FakeDeal:
    def __init__(self, id=1, status="CREATIVE_PENDING_OWNER", advertiser_id=10, owner_id=20):
        self.id = id
        self.status = status
        self.advertiser_id = advertiser_id
        self.owner_id = owner_id
        self.listing_id = 1
        self.price = 100
        self.currency = "TON"
        self.escrow_address = None
        self.brief = "Test"
        self.publish_date = None
        self.description = None
        self.retention_hours = 24
        self.last_activity_at = None
        self.listing = None
        self.advertiser = None
        self.owner = None


class FakeUser:
    def __init__(self, id=20):
        self.id = id


class FakeCreativeVersion:
    def __init__(self, id=1, deal_id=1, version=1, text="Hello", status="submitted",
                 is_current=True, feedback=None):
        self.id = id
        self.deal_id = deal_id
        self.version = version
        self.text = text
        self.entities_json = None
        self.media_items = None
        self.status = status
        self.feedback = feedback
        self.is_current = is_current


class TestCreativeSubmission:
    """Test creative submission flow."""

    def test_state_machine_allows_submit_from_pending(self):
        """Owner can submit creative from CREATIVE_PENDING_OWNER."""
        from app.services.deal_state_machine import validate_transition
        result = validate_transition("CREATIVE_PENDING_OWNER", "submit_creative", "owner")
        assert result == DealStatus.CREATIVE_SUBMITTED

    def test_state_machine_allows_submit_from_changes_requested(self):
        """Owner can resubmit from CREATIVE_CHANGES_REQUESTED."""
        from app.services.deal_state_machine import validate_transition
        result = validate_transition("CREATIVE_CHANGES_REQUESTED", "submit_creative", "owner")
        assert result == DealStatus.CREATIVE_SUBMITTED

    def test_advertiser_cannot_submit_creative(self):
        """Advertiser cannot submit creative."""
        from app.services.deal_state_machine import validate_transition, InvalidTransitionError
        with pytest.raises(InvalidTransitionError):
            validate_transition("CREATIVE_PENDING_OWNER", "submit_creative", "advertiser")


class TestCreativeApproval:
    """Test creative approval flow."""

    def test_state_machine_allows_approve(self):
        """Advertiser can approve creative from CREATIVE_SUBMITTED."""
        from app.services.deal_state_machine import validate_transition
        result = validate_transition("CREATIVE_SUBMITTED", "approve_creative", "advertiser")
        assert result == DealStatus.CREATIVE_APPROVED

    def test_owner_cannot_approve(self):
        """Owner cannot approve creative."""
        from app.services.deal_state_machine import validate_transition, InvalidTransitionError
        with pytest.raises(InvalidTransitionError):
            validate_transition("CREATIVE_SUBMITTED", "approve_creative", "owner")


class TestCreativeRequestChanges:
    """Test request changes flow."""

    def test_state_machine_allows_request_changes(self):
        """Advertiser can request changes from CREATIVE_SUBMITTED."""
        from app.services.deal_state_machine import validate_transition
        result = validate_transition("CREATIVE_SUBMITTED", "request_changes", "advertiser")
        assert result == DealStatus.CREATIVE_CHANGES_REQUESTED

    def test_owner_cannot_request_changes(self):
        """Owner cannot request changes."""
        from app.services.deal_state_machine import validate_transition, InvalidTransitionError
        with pytest.raises(InvalidTransitionError):
            validate_transition("CREATIVE_SUBMITTED", "request_changes", "owner")

    def test_full_revision_cycle(self):
        """Full revision cycle: submit → request_changes → resubmit → approve."""
        from app.services.deal_state_machine import validate_transition

        status = validate_transition("CREATIVE_PENDING_OWNER", "submit_creative", "owner")
        assert status == DealStatus.CREATIVE_SUBMITTED

        status = validate_transition(status, "request_changes", "advertiser")
        assert status == DealStatus.CREATIVE_CHANGES_REQUESTED

        status = validate_transition(status, "submit_creative", "owner")
        assert status == DealStatus.CREATIVE_SUBMITTED

        status = validate_transition(status, "approve_creative", "advertiser")
        assert status == DealStatus.CREATIVE_APPROVED


class TestCreativeActions:
    """Test get_available_actions for creative statuses."""

    def test_creative_pending_owner_actions(self):
        from app.services.deal_state_machine import get_available_actions
        owner_actions = get_available_actions("CREATIVE_PENDING_OWNER", "owner")
        assert "submit_creative" in owner_actions

        advertiser_actions = get_available_actions("CREATIVE_PENDING_OWNER", "advertiser")
        assert "submit_creative" not in advertiser_actions

    def test_creative_submitted_actions(self):
        from app.services.deal_state_machine import get_available_actions
        advertiser_actions = get_available_actions("CREATIVE_SUBMITTED", "advertiser")
        assert "approve_creative" in advertiser_actions
        assert "request_changes" in advertiser_actions

        owner_actions = get_available_actions("CREATIVE_SUBMITTED", "owner")
        assert "approve_creative" not in owner_actions
        assert "request_changes" not in owner_actions

    def test_creative_changes_requested_actions(self):
        from app.services.deal_state_machine import get_available_actions
        owner_actions = get_available_actions("CREATIVE_CHANGES_REQUESTED", "owner")
        assert "submit_creative" in owner_actions

    def test_creative_approved_actions(self):
        from app.services.deal_state_machine import get_available_actions
        owner_actions = get_available_actions("CREATIVE_APPROVED", "owner")
        assert "schedule" in owner_actions

        system_actions = get_available_actions("CREATIVE_APPROVED", "system")
        assert "schedule" in system_actions
