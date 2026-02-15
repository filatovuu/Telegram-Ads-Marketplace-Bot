"""Deal state machine — pure logic, no DB dependency.

Defines the 16-status deal lifecycle, allowed transitions, actors,
and helper functions for validation and action discovery.
"""

from enum import StrEnum


class DealStatus(StrEnum):
    DRAFT = "DRAFT"
    NEGOTIATION = "NEGOTIATION"
    OWNER_ACCEPTED = "OWNER_ACCEPTED"
    AWAITING_ESCROW_PAYMENT = "AWAITING_ESCROW_PAYMENT"
    ESCROW_FUNDED = "ESCROW_FUNDED"
    CREATIVE_PENDING_OWNER = "CREATIVE_PENDING_OWNER"
    CREATIVE_SUBMITTED = "CREATIVE_SUBMITTED"
    CREATIVE_CHANGES_REQUESTED = "CREATIVE_CHANGES_REQUESTED"
    CREATIVE_APPROVED = "CREATIVE_APPROVED"
    SCHEDULED = "SCHEDULED"
    POSTED = "POSTED"
    RETENTION_CHECK = "RETENTION_CHECK"
    RELEASED = "RELEASED"
    REFUNDED = "REFUNDED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class DealAction(StrEnum):
    SEND = "send"
    ACCEPT = "accept"
    REQUEST_ESCROW = "request_escrow"
    CONFIRM_ESCROW = "confirm_escrow"
    REQUEST_CREATIVE = "request_creative"
    SUBMIT_CREATIVE = "submit_creative"
    APPROVE_CREATIVE = "approve_creative"
    REQUEST_CHANGES = "request_changes"
    SCHEDULE = "schedule"
    MARK_POSTED = "mark_posted"
    START_RETENTION = "start_retention"
    RELEASE = "release"
    REFUND = "refund"
    CANCEL = "cancel"
    EXPIRE = "expire"


class Actor(StrEnum):
    ADVERTISER = "advertiser"
    OWNER = "owner"
    SYSTEM = "system"
    ANY = "any"


class InvalidTransitionError(Exception):
    """Raised when a deal transition is not allowed."""

    def __init__(self, current: str, action: str, actor: str | None = None):
        self.current = current
        self.action = action
        self.actor = actor
        msg = f"Invalid transition: {current} + {action}"
        if actor:
            msg += f" by {actor}"
        super().__init__(msg)


# Mapping: (current_status, action) → (new_status, frozenset_of_allowed_actors)
TRANSITIONS: dict[tuple[DealStatus, DealAction], tuple[DealStatus, frozenset[Actor]]] = {
    # Happy path
    (DealStatus.DRAFT, DealAction.SEND): (
        DealStatus.NEGOTIATION,
        frozenset({Actor.ADVERTISER, Actor.OWNER}),
    ),
    (DealStatus.NEGOTIATION, DealAction.ACCEPT): (
        DealStatus.AWAITING_ESCROW_PAYMENT,
        frozenset({Actor.ADVERTISER, Actor.OWNER}),
    ),
    (DealStatus.OWNER_ACCEPTED, DealAction.REQUEST_ESCROW): (
        DealStatus.AWAITING_ESCROW_PAYMENT,
        frozenset({Actor.ADVERTISER, Actor.SYSTEM}),
    ),
    (DealStatus.AWAITING_ESCROW_PAYMENT, DealAction.CONFIRM_ESCROW): (
        DealStatus.ESCROW_FUNDED,
        frozenset({Actor.SYSTEM}),
    ),
    (DealStatus.ESCROW_FUNDED, DealAction.REQUEST_CREATIVE): (
        DealStatus.CREATIVE_PENDING_OWNER,
        frozenset({Actor.SYSTEM}),
    ),
    (DealStatus.CREATIVE_PENDING_OWNER, DealAction.SUBMIT_CREATIVE): (
        DealStatus.CREATIVE_SUBMITTED,
        frozenset({Actor.OWNER}),
    ),
    (DealStatus.CREATIVE_SUBMITTED, DealAction.APPROVE_CREATIVE): (
        DealStatus.CREATIVE_APPROVED,
        frozenset({Actor.ADVERTISER}),
    ),
    (DealStatus.CREATIVE_SUBMITTED, DealAction.REQUEST_CHANGES): (
        DealStatus.CREATIVE_CHANGES_REQUESTED,
        frozenset({Actor.ADVERTISER}),
    ),
    (DealStatus.CREATIVE_CHANGES_REQUESTED, DealAction.SUBMIT_CREATIVE): (
        DealStatus.CREATIVE_SUBMITTED,
        frozenset({Actor.OWNER}),
    ),
    (DealStatus.CREATIVE_APPROVED, DealAction.SCHEDULE): (
        DealStatus.SCHEDULED,
        frozenset({Actor.SYSTEM, Actor.OWNER}),
    ),
    (DealStatus.SCHEDULED, DealAction.MARK_POSTED): (
        DealStatus.POSTED,
        frozenset({Actor.SYSTEM}),
    ),
    (DealStatus.POSTED, DealAction.START_RETENTION): (
        DealStatus.RETENTION_CHECK,
        frozenset({Actor.SYSTEM}),
    ),
    (DealStatus.RETENTION_CHECK, DealAction.RELEASE): (
        DealStatus.RELEASED,
        frozenset({Actor.SYSTEM}),
    ),
    (DealStatus.RETENTION_CHECK, DealAction.REFUND): (
        DealStatus.REFUNDED,
        frozenset({Actor.SYSTEM}),
    ),
    # Cancellation — from pre-escrow states
    (DealStatus.DRAFT, DealAction.CANCEL): (
        DealStatus.CANCELLED,
        frozenset({Actor.ANY}),
    ),
    (DealStatus.NEGOTIATION, DealAction.CANCEL): (
        DealStatus.CANCELLED,
        frozenset({Actor.ANY}),
    ),
    (DealStatus.OWNER_ACCEPTED, DealAction.CANCEL): (
        DealStatus.CANCELLED,
        frozenset({Actor.ANY}),
    ),
    (DealStatus.AWAITING_ESCROW_PAYMENT, DealAction.CANCEL): (
        DealStatus.CANCELLED,
        frozenset({Actor.ANY}),
    ),
    # Expiration — from negotiation/waiting states
    (DealStatus.NEGOTIATION, DealAction.EXPIRE): (
        DealStatus.EXPIRED,
        frozenset({Actor.SYSTEM}),
    ),
    (DealStatus.OWNER_ACCEPTED, DealAction.EXPIRE): (
        DealStatus.EXPIRED,
        frozenset({Actor.SYSTEM}),
    ),
    (DealStatus.AWAITING_ESCROW_PAYMENT, DealAction.EXPIRE): (
        DealStatus.EXPIRED,
        frozenset({Actor.SYSTEM}),
    ),
    (DealStatus.CREATIVE_PENDING_OWNER, DealAction.EXPIRE): (
        DealStatus.EXPIRED,
        frozenset({Actor.SYSTEM}),
    ),
    (DealStatus.CREATIVE_CHANGES_REQUESTED, DealAction.EXPIRE): (
        DealStatus.EXPIRED,
        frozenset({Actor.SYSTEM}),
    ),
    # Refund — from post-escrow states
    (DealStatus.ESCROW_FUNDED, DealAction.REFUND): (
        DealStatus.REFUNDED,
        frozenset({Actor.SYSTEM}),
    ),
    (DealStatus.CREATIVE_PENDING_OWNER, DealAction.REFUND): (
        DealStatus.REFUNDED,
        frozenset({Actor.SYSTEM}),
    ),
    (DealStatus.CREATIVE_SUBMITTED, DealAction.REFUND): (
        DealStatus.REFUNDED,
        frozenset({Actor.SYSTEM}),
    ),
    (DealStatus.CREATIVE_CHANGES_REQUESTED, DealAction.REFUND): (
        DealStatus.REFUNDED,
        frozenset({Actor.SYSTEM}),
    ),
    (DealStatus.CREATIVE_APPROVED, DealAction.REFUND): (
        DealStatus.REFUNDED,
        frozenset({Actor.SYSTEM}),
    ),
    (DealStatus.SCHEDULED, DealAction.REFUND): (
        DealStatus.REFUNDED,
        frozenset({Actor.SYSTEM}),
    ),
}

TERMINAL_STATUSES: frozenset[DealStatus] = frozenset({
    DealStatus.RELEASED,
    DealStatus.REFUNDED,
    DealStatus.CANCELLED,
    DealStatus.EXPIRED,
})

# Statuses where negotiation messages are allowed
MESSAGING_STATUSES: frozenset[DealStatus] = frozenset({
    DealStatus.NEGOTIATION,
    DealStatus.OWNER_ACCEPTED,
    DealStatus.CREATIVE_PENDING_OWNER,
    DealStatus.CREATIVE_SUBMITTED,
    DealStatus.CREATIVE_CHANGES_REQUESTED,
})


def validate_transition(
    current: str, action: str, actor: str,
) -> DealStatus:
    """Validate and return the new status for a transition.

    Raises InvalidTransitionError if the transition is not allowed.
    """
    try:
        current_status = DealStatus(current)
        deal_action = DealAction(action)
    except ValueError:
        raise InvalidTransitionError(current, action, actor)

    key = (current_status, deal_action)
    if key not in TRANSITIONS:
        raise InvalidTransitionError(current, action, actor)

    new_status, allowed_actors = TRANSITIONS[key]

    if Actor.ANY not in allowed_actors and Actor(actor) not in allowed_actors:
        raise InvalidTransitionError(current, action, actor)

    return new_status


def get_available_actions(current: str, actor: str) -> list[str]:
    """Return list of action names available for the given status and actor."""
    try:
        current_status = DealStatus(current)
        actor_enum = Actor(actor)
    except ValueError:
        return []

    if current_status in TERMINAL_STATUSES:
        return []

    actions: list[str] = []
    for (status, action), (_, allowed_actors) in TRANSITIONS.items():
        if status != current_status:
            continue
        if Actor.ANY in allowed_actors or actor_enum in allowed_actors:
            actions.append(action.value)

    return actions
