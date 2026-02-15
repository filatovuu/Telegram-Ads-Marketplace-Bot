"""Unit tests for EscrowService with mocked TonClient."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ton.escrow_service import CHAIN_STATE_MAP, EscrowService


class FakeDeal:
    def __init__(self, id=1, price=Decimal("10.0"), currency="TON"):
        self.id = id
        self.price = price
        self.currency = currency
        self.escrow_address = None


class FakeEscrow:
    def __init__(
        self,
        deal_id=1,
        contract_address="EQTest123",
        amount=10.0,
        on_chain_state="init",
    ):
        self.deal_id = deal_id
        self.contract_address = contract_address
        self.advertiser_address = "EQAdv"
        self.owner_address = "EQOwn"
        self.platform_address = "EQPlat"
        self.amount = amount
        self.on_chain_state = on_chain_state
        self.deadline = None
        self.funded_at = None
        self.released_at = None
        self.refunded_at = None
        self.deposit_tx_hash = None
        self.release_tx_hash = None
        self.refund_tx_hash = None


class TestChainStateMap:
    def test_state_map_values(self):
        assert CHAIN_STATE_MAP[0] == "init"
        assert CHAIN_STATE_MAP[1] == "funded"
        assert CHAIN_STATE_MAP[2] == "released"
        assert CHAIN_STATE_MAP[3] == "refunded"


class TestGetOnChainState:
    @pytest.fixture
    def svc(self):
        return EscrowService()

    @pytest.mark.asyncio
    async def test_returns_none_for_pending_address(self, svc):
        result = await svc.get_on_chain_state("pending-deal-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_empty_address(self, svc):
        result = await svc.get_on_chain_state("")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_state_from_getter(self, svc):
        with patch.object(
            svc.client,
            "run_get_method",
            new_callable=AsyncMock,
            return_value={"stack": [{"value": "1"}]},
        ):
            result = await svc.get_on_chain_state("EQTest123")
            assert result == 1

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self, svc):
        with patch.object(
            svc.client,
            "run_get_method",
            new_callable=AsyncMock,
            side_effect=Exception("network error"),
        ):
            result = await svc.get_on_chain_state("EQTest123")
            assert result is None


class TestVerifyDeposit:
    @pytest.fixture
    def svc(self):
        return EscrowService()

    @pytest.mark.asyncio
    async def test_verify_deposit_via_deployed_contract(self, svc):
        """Deposit verified via getter when contract is deployed and funded."""
        escrow = FakeEscrow(amount=10.0)
        db = AsyncMock()

        with patch.object(
            svc.client,
            "get_account_state",
            new_callable=AsyncMock,
            return_value={"balance": "20000000000", "status": "active"},
        ), patch.object(
            svc, "get_on_chain_state", new_callable=AsyncMock, return_value=1
        ):
            result = await svc.verify_deposit(db, escrow)

        assert result is True
        assert escrow.on_chain_state == "funded"
        assert escrow.funded_at is not None
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_verify_deposit_balance_insufficient(self, svc):
        """Deposit not verified when balance is too low."""
        escrow = FakeEscrow(amount=10.0)
        db = AsyncMock()

        with patch.object(
            svc.client,
            "get_account_state",
            new_callable=AsyncMock,
            return_value={"balance": "100", "status": "uninit"},
        ):
            result = await svc.verify_deposit(db, escrow)

        assert result is False
        assert escrow.on_chain_state == "init"

    @pytest.mark.asyncio
    async def test_verify_deposit_uninit_ignored(self, svc):
        """Deposit NOT verified when balance sufficient but contract not deployed."""
        escrow = FakeEscrow(amount=0.00001)
        db = AsyncMock()

        with patch.object(
            svc.client,
            "get_account_state",
            new_callable=AsyncMock,
            return_value={"balance": "20000", "status": "uninit"},
        ):
            result = await svc.verify_deposit(db, escrow)

        assert result is False
        assert escrow.on_chain_state == "init"

    @pytest.mark.asyncio
    async def test_verify_deposit_already_funded(self, svc):
        escrow = FakeEscrow(on_chain_state="funded")
        db = AsyncMock()

        result = await svc.verify_deposit(db, escrow)
        assert result is False  # already funded, no update needed


class TestTriggerRelease:
    @pytest.fixture
    def svc(self):
        s = EscrowService()
        s.wallet = MagicMock()
        s.wallet.configured = True
        s.wallet.create_transfer_boc = MagicMock(return_value="base64boc")
        return s

    @pytest.mark.asyncio
    async def test_release_success_first_attempt(self, svc):
        escrow = FakeEscrow(on_chain_state="funded")
        db = AsyncMock()

        with (
            patch.object(svc.client, "send_boc", new_callable=AsyncMock, return_value={}),
            patch.object(svc, "_check_trigger_confirmed", new_callable=AsyncMock, return_value=True),
            patch("app.services.ton.escrow_service.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await svc.trigger_release(db, escrow)

        assert result is True
        assert escrow.on_chain_state == "release_sent"

    @pytest.mark.asyncio
    async def test_release_retries_on_failure(self, svc):
        """First attempt fails, second succeeds with higher gas."""
        escrow = FakeEscrow(on_chain_state="funded")
        db = AsyncMock()

        with (
            patch.object(svc.client, "send_boc", new_callable=AsyncMock, return_value={}) as mock_send,
            patch.object(
                svc, "_check_trigger_confirmed",
                new_callable=AsyncMock,
                side_effect=[False, True],  # fail, then succeed
            ),
            patch("app.services.ton.escrow_service.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await svc.trigger_release(db, escrow)
            assert mock_send.await_count == 2

        assert result is True
        assert escrow.on_chain_state == "release_sent"

    @pytest.mark.asyncio
    async def test_release_fails_if_not_funded(self, svc):
        escrow = FakeEscrow(on_chain_state="init")
        db = AsyncMock()

        result = await svc.trigger_release(db, escrow)
        assert result is False

    @pytest.mark.asyncio
    async def test_release_fails_if_wallet_not_configured(self):
        svc = EscrowService()
        svc.wallet = MagicMock()
        svc.wallet.configured = False

        escrow = FakeEscrow(on_chain_state="funded")
        db = AsyncMock()

        result = await svc.trigger_release(db, escrow)
        assert result is False


class TestTriggerRefund:
    @pytest.fixture
    def svc(self):
        s = EscrowService()
        s.wallet = MagicMock()
        s.wallet.configured = True
        s.wallet.create_transfer_boc = MagicMock(return_value="base64boc")
        return s

    @pytest.mark.asyncio
    async def test_refund_success_first_attempt(self, svc):
        escrow = FakeEscrow(on_chain_state="funded")
        db = AsyncMock()

        with (
            patch.object(svc.client, "send_boc", new_callable=AsyncMock, return_value={}),
            patch.object(svc, "_check_trigger_confirmed", new_callable=AsyncMock, return_value=True),
            patch("app.services.ton.escrow_service.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await svc.trigger_refund(db, escrow)

        assert result is True
        assert escrow.on_chain_state == "refund_sent"

    @pytest.mark.asyncio
    async def test_refund_retries_then_exhausts(self, svc):
        """All 3 attempts fail — still marks as refund_sent for monitor."""
        escrow = FakeEscrow(on_chain_state="funded")
        db = AsyncMock()

        with (
            patch.object(svc.client, "send_boc", new_callable=AsyncMock, return_value={}) as mock_send,
            patch.object(
                svc, "_check_trigger_confirmed",
                new_callable=AsyncMock,
                return_value=False,  # always fails
            ),
            patch("app.services.ton.escrow_service.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await svc.trigger_refund(db, escrow)
            assert mock_send.await_count == 3  # 0.1, 0.15, 0.2

        assert result is False
        assert escrow.on_chain_state == "refund_sent"  # still marked for monitor

    @pytest.mark.asyncio
    async def test_refund_fails_if_not_funded(self, svc):
        escrow = FakeEscrow(on_chain_state="init")
        db = AsyncMock()

        result = await svc.trigger_refund(db, escrow)
        assert result is False
