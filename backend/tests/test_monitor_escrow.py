"""Tests for monitor_escrow worker tasks with mocked dependencies."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.monitor_escrow import _monitor_completions, _monitor_deposits


class FakeEscrow:
    def __init__(self, deal_id=1, on_chain_state="init", contract_address="EQTest"):
        self.deal_id = deal_id
        self.on_chain_state = on_chain_state
        self.contract_address = contract_address
        self.amount = 10.0
        self.funded_at = None
        self.released_at = None
        self.refunded_at = None
        self.deposit_tx_hash = None
        self.deadline = None  # None means no expiry


class FakeListResult:
    """Mock result for queries returning a list via scalars().all()."""
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class FakeScalarResult:
    """Mock result for queries returning a single object via scalar_one_or_none()."""
    def __init__(self, item):
        self._item = item

    def scalar_one_or_none(self):
        return self._item


class TestMonitorDeposits:
    @pytest.mark.asyncio
    async def test_no_init_escrows(self):
        """Should do nothing when no init escrows exist."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeListResult([]))

        with patch(
            "app.workers.monitor_escrow.async_session_factory",
        ) as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            await _monitor_deposits()

    @pytest.mark.asyncio
    async def test_deposit_verified_triggers_transition(self):
        """Should verify deposit and transition deal."""
        escrow = FakeEscrow(deal_id=42)
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeListResult([escrow]))

        mock_svc = MagicMock()
        mock_svc.verify_deposit = AsyncMock(return_value=True)

        with (
            patch(
                "app.workers.monitor_escrow.async_session_factory",
            ) as mock_factory,
            patch(
                "app.services.ton.escrow_service.EscrowService",
                return_value=mock_svc,
            ),
            patch(
                "app.services.deal.system_transition_deal",
                new_callable=AsyncMock,
            ) as mock_transition,
        ):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            await _monitor_deposits()

            mock_svc.verify_deposit.assert_awaited_once_with(mock_db, escrow)
            mock_transition.assert_awaited_once_with(mock_db, 42, "confirm_escrow")


class TestMonitorCompletions:
    @pytest.mark.asyncio
    async def test_no_funded_escrows(self):
        """Should do nothing when no funded escrows exist."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeListResult([]))

        with patch(
            "app.workers.monitor_escrow.async_session_factory",
        ) as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            await _monitor_completions()

    @pytest.mark.asyncio
    async def test_released_on_chain(self):
        """Should detect on-chain release and update DB + send notification."""
        escrow = FakeEscrow(deal_id=99, on_chain_state="funded")

        fake_deal = MagicMock()
        fake_deal.id = 99

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[FakeListResult([escrow]), FakeScalarResult(fake_deal)]
        )

        mock_svc = MagicMock()
        mock_svc.get_on_chain_state = AsyncMock(return_value=2)

        with (
            patch(
                "app.workers.monitor_escrow.async_session_factory",
            ) as mock_factory,
            patch(
                "app.services.ton.escrow_service.EscrowService",
                return_value=mock_svc,
            ),
            patch(
                "app.services.notification.notify_escrow_confirmed",
                new_callable=AsyncMock,
            ) as mock_notify,
        ):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            await _monitor_completions()

            assert escrow.on_chain_state == "released"
            assert escrow.released_at is not None
            mock_db.commit.assert_awaited()
            mock_notify.assert_awaited_once_with(fake_deal, "released", 10.0)

    @pytest.mark.asyncio
    async def test_refund_sent_verified(self):
        """Should verify refund_sent and update DB + send notification."""
        escrow = FakeEscrow(deal_id=77, on_chain_state="refund_sent")

        fake_deal = MagicMock()
        fake_deal.id = 77

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[FakeListResult([escrow]), FakeScalarResult(fake_deal)]
        )

        mock_svc = MagicMock()
        mock_svc.verify_sent_transaction = AsyncMock(return_value="refunded")

        with (
            patch(
                "app.workers.monitor_escrow.async_session_factory",
            ) as mock_factory,
            patch(
                "app.services.ton.escrow_service.EscrowService",
                return_value=mock_svc,
            ),
            patch(
                "app.services.notification.notify_escrow_confirmed",
                new_callable=AsyncMock,
            ) as mock_notify,
        ):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            await _monitor_completions()

            assert escrow.on_chain_state == "refunded"
            assert escrow.refunded_at is not None
            mock_db.commit.assert_awaited()
            mock_notify.assert_awaited_once_with(fake_deal, "refunded", 10.0)

    @pytest.mark.asyncio
    async def test_skips_pending_addresses(self):
        """Should skip escrows with pending contract addresses."""
        escrow = FakeEscrow(
            deal_id=100, on_chain_state="funded", contract_address="pending-deal-100"
        )
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeListResult([escrow]))

        mock_svc = MagicMock()
        mock_svc.get_on_chain_state = AsyncMock()

        with (
            patch(
                "app.workers.monitor_escrow.async_session_factory",
            ) as mock_factory,
            patch(
                "app.services.ton.escrow_service.EscrowService",
                return_value=mock_svc,
            ),
        ):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            await _monitor_completions()

            mock_svc.get_on_chain_state.assert_not_awaited()
