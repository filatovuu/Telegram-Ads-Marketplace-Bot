"""Business metrics endpoint — lightweight aggregates for monitoring."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.models.deal import Deal
from app.models.deal_posting import DealPosting
from app.models.escrow import Escrow

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def get_metrics(db: AsyncSession = Depends(get_db)) -> dict:
    # Deals by status
    deal_rows = (
        await db.execute(
            select(Deal.status, func.count()).group_by(Deal.status)
        )
    ).all()
    deals_by_status = {row[0]: row[1] for row in deal_rows}

    # Escrows by on_chain_state
    escrow_rows = (
        await db.execute(
            select(Escrow.on_chain_state, func.count()).group_by(Escrow.on_chain_state)
        )
    ).all()
    escrows_by_state = {row[0]: row[1] for row in escrow_rows}

    # Posting stats
    total_postings = (await db.execute(select(func.count(DealPosting.id)))).scalar() or 0
    posted = (
        await db.execute(
            select(func.count(DealPosting.id)).where(DealPosting.posted_at.is_not(None))
        )
    ).scalar() or 0
    verified = (
        await db.execute(
            select(func.count(DealPosting.id)).where(DealPosting.verified_at.is_not(None))
        )
    ).scalar() or 0
    retained = (
        await db.execute(
            select(func.count(DealPosting.id)).where(DealPosting.retained == True)  # noqa: E712
        )
    ).scalar() or 0
    failed = (
        await db.execute(
            select(func.count(DealPosting.id)).where(DealPosting.retained == False)  # noqa: E712
        )
    ).scalar() or 0

    return {
        "deals_by_status": deals_by_status,
        "deals_total": sum(deals_by_status.values()),
        "escrows_by_state": escrows_by_state,
        "escrows_total": sum(escrows_by_state.values()),
        "postings": {
            "total": total_postings,
            "posted": posted,
            "verified": verified,
            "retained": retained,
            "failed": failed,
        },
    }
