"""Tests for deal state machine — transitions, role enforcement, terminal states."""

import pytest

from app.services.deal_state_machine import (
    DealAction,
    DealStatus,
    InvalidTransitionError,
    TERMINAL_STATUSES,
    get_available_actions,
    validate_transition,
)


class TestHappyPathLifecycle:
    """Full lifecycle: DRAFT → ... → RELEASED."""

    def test_full_happy_path(self):
        status = DealStatus.DRAFT

        status = validate_transition(status, "send", "advertiser")
        assert status == DealStatus.NEGOTIATION

        status = validate_transition(status, "accept", "owner")
        assert status == DealStatus.AWAITING_ESCROW_PAYMENT

        status = validate_transition(status, "confirm_escrow", "system")
        assert status == DealStatus.ESCROW_FUNDED

        status = validate_transition(status, "request_creative", "system")
        assert status == DealStatus.CREATIVE_PENDING_OWNER

        status = validate_transition(status, "submit_creative", "owner")
        assert status == DealStatus.CREATIVE_SUBMITTED

        status = validate_transition(status, "approve_creative", "advertiser")
        assert status == DealStatus.CREATIVE_APPROVED

        status = validate_transition(status, "schedule", "system")
        assert status == DealStatus.SCHEDULED

        status = validate_transition(status, "mark_posted", "system")
        assert status == DealStatus.POSTED

        status = validate_transition(status, "start_retention", "system")
        assert status == DealStatus.RETENTION_CHECK

        status = validate_transition(status, "release", "system")
        assert status == DealStatus.RELEASED

    def test_creative_revision_cycle(self):
        """Creative can go through request_changes → submit_creative loop."""
        status = DealStatus.CREATIVE_SUBMITTED

        status = validate_transition(status, "request_changes", "advertiser")
        assert status == DealStatus.CREATIVE_CHANGES_REQUESTED

        status = validate_transition(status, "submit_creative", "owner")
        assert status == DealStatus.CREATIVE_SUBMITTED

        status = validate_transition(status, "approve_creative", "advertiser")
        assert status == DealStatus.CREATIVE_APPROVED


class TestInvalidTransitions:
    def test_invalid_action_from_draft(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition("DRAFT", "accept", "owner")

    def test_invalid_action_string(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition("DRAFT", "nonexistent_action", "advertiser")

    def test_invalid_status_string(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition("INVALID_STATUS", "send", "advertiser")

    def test_cannot_transition_from_released(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition("RELEASED", "send", "advertiser")

    def test_cannot_transition_from_cancelled(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition("CANCELLED", "send", "advertiser")

    def test_skip_status_not_allowed(self):
        """Cannot jump from DRAFT to OWNER_ACCEPTED."""
        with pytest.raises(InvalidTransitionError):
            validate_transition("DRAFT", "accept", "owner")


class TestRoleRestrictions:
    def test_both_parties_can_send(self):
        """Both advertiser and owner can send a deal from DRAFT."""
        assert validate_transition("DRAFT", "send", "advertiser") == DealStatus.NEGOTIATION
        assert validate_transition("DRAFT", "send", "owner") == DealStatus.NEGOTIATION

    def test_both_parties_can_accept(self):
        """Both advertiser and owner can accept from NEGOTIATION."""
        assert validate_transition("NEGOTIATION", "accept", "advertiser") == DealStatus.AWAITING_ESCROW_PAYMENT
        assert validate_transition("NEGOTIATION", "accept", "owner") == DealStatus.AWAITING_ESCROW_PAYMENT

    def test_advertiser_cannot_submit_creative(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition("CREATIVE_PENDING_OWNER", "submit_creative", "advertiser")

    def test_owner_cannot_approve_creative(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition("CREATIVE_SUBMITTED", "approve_creative", "owner")

    def test_any_party_can_cancel_from_draft(self):
        assert validate_transition("DRAFT", "cancel", "advertiser") == DealStatus.CANCELLED
        assert validate_transition("DRAFT", "cancel", "owner") == DealStatus.CANCELLED

    def test_any_party_can_cancel_from_negotiation(self):
        assert validate_transition("NEGOTIATION", "cancel", "advertiser") == DealStatus.CANCELLED
        assert validate_transition("NEGOTIATION", "cancel", "owner") == DealStatus.CANCELLED

    def test_system_can_expire(self):
        assert validate_transition("NEGOTIATION", "expire", "system") == DealStatus.EXPIRED

    def test_non_system_cannot_expire(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition("NEGOTIATION", "expire", "advertiser")

    def test_system_can_refund_post_escrow(self):
        assert validate_transition("ESCROW_FUNDED", "refund", "system") == DealStatus.REFUNDED
        assert validate_transition("SCHEDULED", "refund", "system") == DealStatus.REFUNDED

    def test_owner_can_schedule(self):
        assert validate_transition("CREATIVE_APPROVED", "schedule", "owner") == DealStatus.SCHEDULED

    def test_system_request_escrow(self):
        assert validate_transition("OWNER_ACCEPTED", "request_escrow", "system") == DealStatus.AWAITING_ESCROW_PAYMENT


class TestTerminalStatuses:
    def test_terminal_statuses_set(self):
        assert DealStatus.RELEASED in TERMINAL_STATUSES
        assert DealStatus.REFUNDED in TERMINAL_STATUSES
        assert DealStatus.CANCELLED in TERMINAL_STATUSES
        assert DealStatus.EXPIRED in TERMINAL_STATUSES
        assert DealStatus.DRAFT not in TERMINAL_STATUSES

    def test_no_actions_from_terminal(self):
        for status in TERMINAL_STATUSES:
            assert get_available_actions(status, "advertiser") == []
            assert get_available_actions(status, "owner") == []
            assert get_available_actions(status, "system") == []


class TestGetAvailableActions:
    def test_draft_advertiser_actions(self):
        actions = get_available_actions("DRAFT", "advertiser")
        assert "send" in actions
        assert "cancel" in actions
        assert "accept" not in actions

    def test_draft_owner_actions(self):
        actions = get_available_actions("DRAFT", "owner")
        assert "cancel" in actions
        assert "send" in actions

    def test_negotiation_owner(self):
        actions = get_available_actions("NEGOTIATION", "owner")
        assert "accept" in actions
        assert "cancel" in actions

    def test_negotiation_advertiser(self):
        actions = get_available_actions("NEGOTIATION", "advertiser")
        assert "cancel" in actions
        assert "accept" in actions

    def test_creative_submitted_advertiser(self):
        actions = get_available_actions("CREATIVE_SUBMITTED", "advertiser")
        assert "approve_creative" in actions
        assert "request_changes" in actions

    def test_creative_submitted_owner(self):
        actions = get_available_actions("CREATIVE_SUBMITTED", "owner")
        assert actions == []

    def test_invalid_status(self):
        assert get_available_actions("BOGUS", "advertiser") == []

    def test_invalid_actor(self):
        assert get_available_actions("DRAFT", "bogus_role") == []


class TestEscrowTransitions:
    """Escrow-specific transition tests."""

    def test_advertiser_can_request_escrow(self):
        result = validate_transition("OWNER_ACCEPTED", "request_escrow", "advertiser")
        assert result == DealStatus.AWAITING_ESCROW_PAYMENT

    def test_system_can_request_escrow(self):
        result = validate_transition("OWNER_ACCEPTED", "request_escrow", "system")
        assert result == DealStatus.AWAITING_ESCROW_PAYMENT

    def test_owner_cannot_request_escrow(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition("OWNER_ACCEPTED", "request_escrow", "owner")

    def test_system_confirms_escrow(self):
        result = validate_transition("AWAITING_ESCROW_PAYMENT", "confirm_escrow", "system")
        assert result == DealStatus.ESCROW_FUNDED

    def test_advertiser_cannot_confirm_escrow(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition("AWAITING_ESCROW_PAYMENT", "confirm_escrow", "advertiser")

    def test_owner_cannot_confirm_escrow(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition("AWAITING_ESCROW_PAYMENT", "confirm_escrow", "owner")

    def test_system_refund_from_escrow_funded(self):
        result = validate_transition("ESCROW_FUNDED", "refund", "system")
        assert result == DealStatus.REFUNDED

    def test_anyone_can_cancel_awaiting_escrow(self):
        assert validate_transition("AWAITING_ESCROW_PAYMENT", "cancel", "advertiser") == DealStatus.CANCELLED
        assert validate_transition("AWAITING_ESCROW_PAYMENT", "cancel", "owner") == DealStatus.CANCELLED

    def test_system_expire_awaiting_escrow(self):
        assert validate_transition("AWAITING_ESCROW_PAYMENT", "expire", "system") == DealStatus.EXPIRED

    def test_full_escrow_to_release_path(self):
        """Full path from OWNER_ACCEPTED through escrow to RELEASED."""
        status = validate_transition("OWNER_ACCEPTED", "request_escrow", "advertiser")
        assert status == DealStatus.AWAITING_ESCROW_PAYMENT

        status = validate_transition(status, "confirm_escrow", "system")
        assert status == DealStatus.ESCROW_FUNDED

        status = validate_transition(status, "request_creative", "system")
        assert status == DealStatus.CREATIVE_PENDING_OWNER

    def test_escrow_actions_for_advertiser(self):
        actions = get_available_actions("OWNER_ACCEPTED", "advertiser")
        assert "request_escrow" in actions
        assert "cancel" in actions

    def test_escrow_actions_for_owner(self):
        actions = get_available_actions("OWNER_ACCEPTED", "owner")
        assert "request_escrow" not in actions
        assert "cancel" in actions

    def test_awaiting_escrow_actions_for_system(self):
        actions = get_available_actions("AWAITING_ESCROW_PAYMENT", "system")
        assert "confirm_escrow" in actions
        assert "expire" in actions
