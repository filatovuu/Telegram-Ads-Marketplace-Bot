"""Platform wallet management — derives keypair from mnemonic, signs messages."""

import logging

from tonsdk.boc import Cell
from tonsdk.contract.wallet import WalletVersionEnum, Wallets
from tonsdk.utils import bytes_to_b64str

from app.core.config import settings

logger = logging.getLogger(__name__)


class PlatformWallet:
    """Manages the platform's TON wallet for signing escrow transactions."""

    def __init__(self) -> None:
        mnemonic = settings.ton_platform_mnemonic
        if not mnemonic:
            logger.warning("TON platform mnemonic not configured")
            self._wallet = None
            self._keypair = None
            return

        mnemonics = mnemonic.split()
        _mnemonics, _pub, _priv, wallet = Wallets.from_mnemonics(
            mnemonics, WalletVersionEnum.v4r2, workchain=0
        )
        self._wallet = wallet
        self._keypair = (_pub, _priv)

    @property
    def address(self) -> str | None:
        if self._wallet is None:
            return None
        return self._wallet.address.to_string(True, True, False)

    @property
    def configured(self) -> bool:
        return self._wallet is not None

    def create_transfer_boc(
        self, to_address: str, amount: int, payload: Cell | bytes | None = None, seqno: int = 0,
    ) -> str:
        """Create a signed transfer BOC (base64-encoded).

        Args:
            to_address: Destination address (raw or user-friendly).
            amount: Amount in nanoTON.
            payload: Optional message body (Cell for opcode payloads, bytes for text).
            seqno: Wallet sequence number.

        Returns:
            Base64-encoded BOC string ready for send_boc.
        """
        if not self._wallet:
            raise RuntimeError("Platform wallet not configured")

        query = self._wallet.create_transfer_message(
            to_addr=to_address,
            amount=amount,
            seqno=seqno,
            payload=payload,
        )
        boc = bytes_to_b64str(query["message"].to_boc(False))
        return boc
