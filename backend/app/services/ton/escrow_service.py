"""Escrow lifecycle service — deploy, verify deposit, release, refund."""

import asyncio
import logging
from datetime import datetime, timezone

from pytoniq_core import Address as TonAddress
from pytoniq_core import Cell, StateInit, begin_cell
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tonsdk.boc import Cell as TonsdkCell

from app.core.config import settings
from app.models.deal import Deal
from app.models.escrow import Escrow
from app.services.ton.client import TonClient
from app.services.ton.contract_code import ESCROW_CONTRACT_CODE_HEX
from app.services.ton.wallet import PlatformWallet

logger = logging.getLogger(__name__)

# On-chain state mapping: getter returns int
CHAIN_STATE_MAP = {0: "init", 1: "funded", 2: "released", 3: "refunded"}

# Tact message opcodes (from compiled contract)
RELEASE_OPCODE = 0x5642A0B8
REFUND_OPCODE = 0xAD7C3ADD

# Trigger message gas settings (nanoTON).
# Must be >0 for contract to have gas credit (TVM requirement for internal msgs).
# The contract returns this to the platform via SendRemainingBalance.
# On failure (exit code), retries with +STEP up to MAX.
TRIGGER_MSG_VALUE = 100_000_000  # 0.1 TON — initial amount
TRIGGER_MSG_STEP = 50_000_000    # +0.05 TON per retry
TRIGGER_MSG_MAX = 200_000_000    # 0.2 TON — max amount
TRIGGER_VERIFY_DELAY = 10        # seconds to wait before verifying on-chain


def _opcode_payload(opcode: int) -> TonsdkCell:
    """Build a tonsdk Cell containing a 32-bit opcode (Tact message header)."""
    cell = TonsdkCell()
    cell.bits.write_uint(opcode, 32)
    return cell


class EscrowService:
    """Manages on-chain escrow lifecycle."""

    def __init__(self) -> None:
        self.client = TonClient()
        self.wallet = PlatformWallet()

    def _build_state_init(
        self,
        deal_id: int,
        advertiser_address: str,
        owner_address: str,
        platform_address: str,
        amount_nano: int,
        fee_percent: int,
    ) -> StateInit:
        """Build the state_init for the escrow contract.

        MUST match the Tact-generated init layout exactly
        (see contracts/output/escrow_Escrow.ts → Escrow_init / initEscrow_init_args):
            b_0: uint(0,1) | int(dealId,257) | address(advertiser) | address(owner)
                 ref → b_1: address(platform) | int(amount,257) | int(feePercent,257)
        """
        code_cell = Cell.one_from_boc(bytes.fromhex(ESCROW_CONTRACT_CODE_HEX))

        # b_1: platform, amount, feePercent
        b_1 = (
            begin_cell()
            .store_address(TonAddress(platform_address))
            .store_int(amount_nano, 257)
            .store_int(fee_percent, 257)
            .end_cell()
        )

        # b_0: flag(0,1), dealId(257), advertiser, owner, ref→b_1
        data = (
            begin_cell()
            .store_uint(0, 1)
            .store_int(deal_id, 257)
            .store_address(TonAddress(advertiser_address))
            .store_address(TonAddress(owner_address))
            .store_ref(b_1)
            .end_cell()
        )

        return StateInit(code=code_cell, data=data)

    def _compute_contract_address(
        self,
        deal_id: int,
        advertiser_address: str,
        owner_address: str,
        platform_address: str,
        amount_nano: int,
        fee_percent: int,
    ) -> str:
        """Compute the deterministic contract address from state_init."""
        si = self._build_state_init(
            deal_id, advertiser_address, owner_address,
            platform_address, amount_nano, fee_percent,
        )
        si_cell = si.serialize()
        is_testnet = settings.ton_network == "testnet"
        addr = TonAddress((0, si_cell.hash))
        return addr.to_str(is_bounceable=True, is_test_only=is_testnet)

    def get_state_init_boc_b64(self, escrow: Escrow) -> str | None:
        """Return the base64-encoded state_init BOC for frontend deployment."""
        import base64

        if not escrow.advertiser_address or not escrow.owner_address:
            return None
        try:
            amount_nano = int(escrow.amount * 1_000_000_000)
            si = self._build_state_init(
                deal_id=escrow.deal_id,
                advertiser_address=escrow.advertiser_address,
                owner_address=escrow.owner_address,
                platform_address=escrow.platform_address or "",
                amount_nano=amount_nano,
                fee_percent=escrow.fee_percent,
            )
            si_cell = si.serialize()
            return base64.b64encode(si_cell.to_boc()).decode()
        except Exception:
            logger.exception("Failed to build state_init for deal %s", escrow.deal_id)
            return None

    async def create_escrow_for_deal(
        self,
        db: AsyncSession,
        deal: Deal,
        advertiser_address: str,
        owner_address: str | None = None,
    ) -> Escrow:
        """Create an escrow record for a deal.

        Computes the contract address from deal parameters and stores it.
        Actual deployment happens when the advertiser sends the deposit
        (the contract is deployed via state_init attached to the deposit tx).
        """
        if not self.wallet.configured:
            raise ValueError(
                "Platform wallet not configured (TON_PLATFORM_MNEMONIC). "
                "Cannot create escrow — release/refund will be impossible."
            )

        # Check if escrow already exists
        result = await db.execute(
            select(Escrow).where(Escrow.deal_id == deal.id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        platform_address = self.wallet.address
        amount_nano = int(float(deal.price) * 1_000_000_000)
        fee_percent = settings.platform_fee_percent

        if not owner_address:
            raise ValueError(
                "Owner wallet address is required to create escrow. "
                "Channel owner must connect their TON wallet first."
            )
        effective_owner = owner_address

        contract_address = self._compute_contract_address(
            deal_id=deal.id,
            advertiser_address=advertiser_address,
            owner_address=effective_owner,
            platform_address=platform_address,
            amount_nano=amount_nano,
            fee_percent=fee_percent,
        )

        escrow = Escrow(
            deal_id=deal.id,
            contract_address=contract_address,
            advertiser_address=advertiser_address,
            owner_address=owner_address,
            platform_address=platform_address,
            amount=float(deal.price),
            fee_percent=fee_percent,
            on_chain_state="init",
        )
        db.add(escrow)

        deal.escrow_address = contract_address

        await db.commit()
        await db.refresh(escrow)

        logger.info(
            "Created escrow for deal %s: address=%s, amount=%s TON, fee=%s%%",
            deal.id, contract_address, deal.price, fee_percent,
        )
        return escrow

    async def get_escrow_for_deal(
        self, db: AsyncSession, deal_id: int,
    ) -> Escrow | None:
        """Get escrow record for a deal."""
        result = await db.execute(
            select(Escrow).where(Escrow.deal_id == deal_id)
        )
        return result.scalar_one_or_none()

    async def get_on_chain_state(self, contract_address: str) -> int | None:
        """Query the on-chain escrow state via getter.

        Returns: 0=init, 1=funded, 2=released, 3=refunded, or None on error.
        """
        if not contract_address or contract_address.startswith("pending-"):
            return None
        try:
            result = await self.client.run_get_method(
                contract_address, "escrowState"
            )
            stack = result.get("stack", [])
            if stack and len(stack) > 0:
                return int(stack[0].get("value", 0))
            return None
        except Exception:
            # Expected for undeployed contracts — don't spam ERROR logs
            logger.debug("get_on_chain_state failed for %s (contract may not be deployed yet)", contract_address)
            return None

    async def verify_deposit(
        self, db: AsyncSession, escrow: Escrow,
    ) -> bool:
        """Check if the escrow has been funded on-chain.

        Strategy: check account status first. For deployed (active) contracts,
        use the on-chain getter as the primary source of truth. Fall back to
        balance check with gas tolerance for edge cases.

        Returns True if deposit is verified and DB is updated.
        """
        if not escrow.contract_address or escrow.contract_address.startswith("pending-"):
            return False
        if escrow.on_chain_state != "init":
            return False

        try:
            account = await self.client.get_account_state(escrow.contract_address)
            balance = int(account.get("balance", 0))
            account_status = account.get("status", "")

            # Contract must be deployed for a valid deposit
            if account_status != "active":
                if balance > 0:
                    logger.debug(
                        "Contract not deployed for deal_id=%s (status=%s, balance=%s) — "
                        "waiting for stateInit deployment",
                        escrow.deal_id, account_status, balance,
                    )
                return False

            # Contract deployed — use getter for precise state (most reliable)
            state = await self.get_on_chain_state(escrow.contract_address)
            if state is not None and state >= 1:
                now = datetime.now(timezone.utc)
                escrow.on_chain_state = CHAIN_STATE_MAP.get(state, "funded")
                escrow.funded_at = now
                await db.commit()
                logger.info("Deposit verified via getter for deal_id=%s (state=%s)", escrow.deal_id, state)
                return True

            # Getter returned 0 (init) or failed — check balance with gas tolerance
            # After deployment + deposit, gas consumes ~2-5% of the amount
            expected_nano = int(escrow.amount * 1_000_000_000)
            gas_tolerance = int(expected_nano * 0.1)  # 10% tolerance for gas
            if balance >= (expected_nano - gas_tolerance):
                now = datetime.now(timezone.utc)
                escrow.on_chain_state = "funded"
                escrow.funded_at = now
                await db.commit()
                logger.info(
                    "Deposit verified via balance for deal_id=%s (balance=%s, expected=%s)",
                    escrow.deal_id, balance, expected_nano,
                )
                return True

            logger.debug(
                "Deposit not yet confirmed for deal_id=%s (state=%s, balance=%s, expected=%s)",
                escrow.deal_id, state, balance, expected_nano,
            )
            return False
        except Exception:
            logger.warning("Failed to verify deposit for deal %s (will retry next cycle)", escrow.deal_id)
            return False

    async def _check_deposit_via_transactions(
        self, db: AsyncSession, escrow: Escrow,
    ) -> bool:
        """Fallback: check if advertiser sent funds to escrow address via tx history."""
        if not escrow.contract_address:
            return False
        try:
            txs = await self.client.get_transactions(escrow.contract_address, limit=5)
            for tx in txs:
                in_msg = tx.get("in_msg", {})
                value = int(in_msg.get("value", 0))
                expected_nano = int(escrow.amount * 1_000_000_000)
                if value >= expected_nano:
                    now = datetime.now(timezone.utc)
                    escrow.on_chain_state = "funded"
                    escrow.funded_at = now
                    escrow.deposit_tx_hash = tx.get("hash", "")
                    await db.commit()
                    return True
        except Exception:
            logger.exception("Failed to check deposit txs for deal %s", escrow.deal_id)
        return False

    async def _get_wallet_seqno(self) -> int:
        """Fetch the current seqno of the platform wallet from chain."""
        if not self.wallet.address:
            return 0
        try:
            state = await self.client.get_account_state(self.wallet.address)
            if state.get("status") != "active":
                return 0  # uninit wallet → first tx uses seqno 0
            result = await self.client.run_get_method(self.wallet.address, "seqno")
            stack = result.get("stack", [])
            if stack:
                return int(stack[0].get("value", "0"), 0)
            return 0
        except Exception:
            logger.warning("Failed to fetch wallet seqno, using 0")
            return 0

    async def _check_trigger_confirmed(self, contract_address: str) -> bool:
        """Quick check: did the trigger tx change the contract state?

        Returns True if contract is destroyed or getter shows state >= 2.
        """
        try:
            account = await self.client.get_account_state(contract_address)
            status = account.get("status", "")
            balance = int(account.get("balance", 0))

            # Contract destroyed → operation completed
            if status in ("nonexist", "uninit") or (status != "active" and balance == 0):
                return True

            # Contract active → check getter
            if status == "active":
                state = await self.get_on_chain_state(contract_address)
                if state is not None and state >= 2:
                    return True

            return False
        except Exception:
            return False

    async def _trigger_with_retry(
        self,
        db: AsyncSession,
        escrow: Escrow,
        opcode: int,
        sent_state: str,
    ) -> bool:
        """Send trigger message with retry, increasing gas on failure.

        Starts at TRIGGER_MSG_VALUE (0.1 TON), steps by TRIGGER_MSG_STEP (+0.05),
        up to TRIGGER_MSG_MAX (0.2 TON). After each send, waits TRIGGER_VERIFY_DELAY
        seconds and checks on-chain state. The contract returns the trigger value
        to the platform via SendRemainingBalance.
        """
        amount = TRIGGER_MSG_VALUE
        attempt = 0

        while amount <= TRIGGER_MSG_MAX:
            attempt += 1
            try:
                seqno = await self._get_wallet_seqno()
                boc = self.wallet.create_transfer_boc(
                    to_address=escrow.contract_address,
                    amount=amount,
                    payload=_opcode_payload(opcode),
                    seqno=seqno,
                )
                await self.client.send_boc(boc)
                logger.info(
                    "%s tx sent for deal %s (attempt=%d, amount=%d nanoTON, seqno=%d)",
                    sent_state, escrow.deal_id, attempt, amount, seqno,
                )

                # Wait for on-chain processing
                await asyncio.sleep(TRIGGER_VERIFY_DELAY)

                # Check if contract state changed
                if await self._check_trigger_confirmed(escrow.contract_address):
                    escrow.on_chain_state = sent_state
                    await db.commit()
                    logger.info(
                        "%s confirmed for deal %s (attempt=%d, amount=%d nanoTON)",
                        sent_state, escrow.deal_id, attempt, amount,
                    )
                    return True

                # Not confirmed — retry with more gas
                amount += TRIGGER_MSG_STEP
                if amount <= TRIGGER_MSG_MAX:
                    logger.warning(
                        "%s not confirmed for deal %s (attempt=%d), "
                        "retrying with %d nanoTON",
                        sent_state, escrow.deal_id, attempt, amount,
                    )
            except Exception:
                logger.exception(
                    "Failed to send %s for deal %s (attempt=%d)",
                    sent_state, escrow.deal_id, attempt,
                )
                break

        # All attempts exhausted or error — mark as sent for monitor to track
        escrow.on_chain_state = sent_state
        await db.commit()
        logger.warning(
            "%s not confirmed after %d attempts for deal %s (monitor will track)",
            sent_state, attempt, escrow.deal_id,
        )
        return False

    async def trigger_release(
        self, db: AsyncSession, escrow: Escrow,
    ) -> bool:
        """Send release message from platform wallet to escrow contract."""
        if not self.wallet.configured:
            logger.error("Platform wallet not configured, cannot release")
            return False
        if not escrow.contract_address or escrow.on_chain_state != "funded":
            return False
        return await self._trigger_with_retry(db, escrow, RELEASE_OPCODE, "release_sent")

    async def trigger_refund(
        self, db: AsyncSession, escrow: Escrow,
    ) -> bool:
        """Send refund message from platform wallet to escrow contract."""
        if not self.wallet.configured:
            logger.error("Platform wallet not configured, cannot refund")
            return False
        if not escrow.contract_address or escrow.on_chain_state != "funded":
            return False
        return await self._trigger_with_retry(db, escrow, REFUND_OPCODE, "refund_sent")

    async def verify_sent_transaction(self, escrow: Escrow) -> str | None:
        """Check if a sent release/refund was confirmed on-chain.

        For destroyed contracts (nonexist/uninit): infer completion from DB intermediate state.
        For active contracts: use the on-chain getter.

        Returns "refunded" or "released" if confirmed, None if still pending.
        """
        if not escrow.contract_address:
            return None
        try:
            account = await self.client.get_account_state(escrow.contract_address)
            account_status = account.get("status", "")
            balance = int(account.get("balance", 0))

            # Contract destroyed (SendDestroyIfZero) → operation completed
            if account_status in ("nonexist", "uninit") or (account_status != "active" and balance == 0):
                if escrow.on_chain_state == "refund_sent":
                    return "refunded"
                if escrow.on_chain_state == "release_sent":
                    return "released"

            # Contract still active → check getter
            if account_status == "active":
                state = await self.get_on_chain_state(escrow.contract_address)
                if state is not None and state >= 2:
                    return CHAIN_STATE_MAP.get(state)
                # Getter returned 1 (funded) → tx was rejected by contract
                if state == 1:
                    logger.warning(
                        "On-chain state still 'funded' for deal %s — tx may have been rejected",
                        escrow.deal_id,
                    )

            return None
        except Exception:
            logger.debug("verify_sent_transaction failed for deal %s", escrow.deal_id)
            return None
