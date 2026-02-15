"""One-time script: retry failed refund for a deal.

The old code sent b"Refund" (ASCII) instead of the Tact opcode 0xAD7C3ADD,
so the contract rejected the message while the DB was updated optimistically.

This script:
1. Resets escrow.on_chain_state from "refunded" back to "funded"
2. Clears escrow.refunded_at
3. Re-sends the refund with the correct opcode
4. Updates the DB on success

Usage:
    cd backend
    python -m scripts.retry_refund 37
"""

import asyncio
import sys

from sqlalchemy import select

from app.db.session import async_session_factory, engine
from app.models.escrow import Escrow
from app.services.ton.escrow_service import EscrowService


async def retry_refund(deal_id: int, force: bool = False) -> None:
    async with async_session_factory() as db:
        result = await db.execute(
            select(Escrow).where(Escrow.deal_id == deal_id)
        )
        escrow = result.scalar_one_or_none()

        if not escrow:
            print(f"No escrow found for deal_id={deal_id}")
            return

        print(f"Escrow for deal #{deal_id}:")
        print(f"  contract_address: {escrow.contract_address}")
        print(f"  amount:           {escrow.amount} TON")
        print(f"  on_chain_state:   {escrow.on_chain_state}")
        print(f"  refunded_at:      {escrow.refunded_at}")
        print()

        svc = EscrowService()

        # Step 1: verify on-chain state is still "funded" (state=1)
        on_chain = await svc.get_on_chain_state(escrow.contract_address)
        print(f"On-chain state: {on_chain} (1=funded, 2=released, 3=refunded)")

        if on_chain is None and not force:
            print("WARNING: Could not query on-chain state (API timeout?).")
            print("Use --force to skip this check if you verified manually.")
            return

        if on_chain is None and force:
            print("WARNING: Getter unavailable, but --force specified. Proceeding...")

        if on_chain == 3:
            print("Contract is already refunded on-chain. Syncing DB...")
            escrow.on_chain_state = "refunded"
            await db.commit()
            print("Done — DB synced.")
            return

        if on_chain is not None and on_chain != 1:
            print(f"Unexpected on-chain state {on_chain}. Aborting.")
            return

        # Step 2: reset DB state so trigger_refund() will proceed
        if escrow.on_chain_state != "funded":
            print(f"Resetting escrow DB state from '{escrow.on_chain_state}' to 'funded'...")
            escrow.on_chain_state = "funded"
            escrow.refunded_at = None
            await db.commit()
        else:
            print("DB state is already 'funded', proceeding...")

        # Step 3: re-send refund with correct opcode
        print("Sending refund with correct opcode (0xAD7C3ADD)...")
        success = await svc.trigger_refund(db, escrow)

        if success:
            print(f"Refund sent successfully! escrow.on_chain_state={escrow.on_chain_state}")
        else:
            print("Refund failed. Check logs for details.")
            # Restore the state so we don't lie
            escrow.on_chain_state = "funded"
            escrow.refunded_at = None
            await db.commit()
            print("DB state restored to 'funded' — retry later.")

    await engine.dispose()


def main() -> None:
    args = sys.argv[1:]
    force = "--force" in args
    args = [a for a in args if a != "--force"]

    if len(args) != 1:
        print("Usage: python -m scripts.retry_refund [--force] <deal_id>")
        sys.exit(1)

    deal_id = int(args[0])
    print(f"=== Retrying refund for Deal #{deal_id} ===")
    if force:
        print("(--force mode: skipping on-chain getter check)")
    print()
    asyncio.run(retry_refund(deal_id, force=force))


if __name__ == "__main__":
    main()
