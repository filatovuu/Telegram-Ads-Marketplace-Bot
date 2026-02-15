"""Escrow API endpoints — create, status, confirm deposit."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    CreateEscrowRequest,
    EscrowResponse,
)
from app.core.config import settings
from app.core.deps import get_db
from app.core.rate_limit import limiter
from app.core.security import get_current_user
from app.models.user import User
from app.services import deal as deal_svc
from app.services.ton.escrow_service import EscrowService

router = APIRouter(prefix="/escrow", tags=["escrow"])

escrow_service = EscrowService()


@router.post("/deals/{deal_id}/create", response_model=EscrowResponse, status_code=201)
@limiter.limit(settings.rate_limit_escrow)
async def create_escrow(
    request: Request,
    deal_id: int,
    body: CreateEscrowRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deploy escrow contract for a deal. Transitions deal to AWAITING_ESCROW_PAYMENT."""
    from app.core.idempotency import check_idempotency

    is_new = await check_idempotency(f"escrow:create:{deal_id}:{user.id}", ttl=60)
    if not is_new:
        # Duplicate request — return existing escrow if any
        existing = await escrow_service.get_escrow_for_deal(db, deal_id)
        if existing:
            resp = EscrowResponse.model_validate(existing)
            resp.state_init_boc = escrow_service.get_state_init_boc_b64(existing)
            return resp

    deal = await deal_svc.get_deal(db, deal_id, user.id)

    if deal.advertiser_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the advertiser can create an escrow",
        )

    # Check if escrow already exists for this deal
    existing = await escrow_service.get_escrow_for_deal(db, deal.id)
    if existing:
        resp = EscrowResponse.model_validate(existing)
        resp.state_init_boc = escrow_service.get_state_init_boc_b64(existing)
        return resp

    # If deal is already in AWAITING_ESCROW_PAYMENT, just create the escrow record
    # (this happens when the transition was triggered via bot without wallet addresses)
    already_awaiting = deal.status == "AWAITING_ESCROW_PAYMENT"

    if not already_awaiting:
        # Transition deal to AWAITING_ESCROW_PAYMENT
        from app.services.deal_state_machine import InvalidTransitionError, validate_transition

        actor = "advertiser"
        try:
            new_status = validate_transition(deal.status, "request_escrow", actor)
        except InvalidTransitionError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    else:
        from app.services.deal_state_machine import DealStatus
        new_status = DealStatus.AWAITING_ESCROW_PAYMENT

    # Resolve owner's wallet address: explicit request param > per-deal wallet > profile wallet
    owner_address = body.owner_address
    if not owner_address and deal.owner_wallet_address:
        owner_address = deal.owner_wallet_address
    if not owner_address and deal.owner and deal.owner.wallet_address:
        owner_address = deal.owner.wallet_address
    if not owner_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Channel owner has not connected their TON wallet yet. "
            "The owner must connect a wallet before escrow can be created.",
        )

    try:
        escrow = await escrow_service.create_escrow_for_deal(
            db, deal, body.advertiser_address, owner_address,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    # Update deal status + add system message (only if status actually changed)
    from datetime import datetime, timezone

    from app.models.deal_message import DealMessage

    if not already_awaiting:
        deal.status = new_status.value
        deal.last_activity_at = datetime.now(timezone.utc)
        sys_msg = DealMessage(
            deal_id=deal.id,
            sender_user_id=None,
            text=f"Status changed to {new_status.value} by advertiser. Escrow created.",
            message_type="system",
        )
        db.add(sys_msg)
    else:
        deal.last_activity_at = datetime.now(timezone.utc)
        sys_msg = DealMessage(
            deal_id=deal.id,
            sender_user_id=None,
            text="Escrow contract created by advertiser.",
            message_type="system",
        )
        db.add(sys_msg)

    await db.commit()
    await db.refresh(deal)
    await db.refresh(escrow)

    if not already_awaiting:
        from app.services.notification import notify_deal_status_change

        await notify_deal_status_change(deal)

    # Audit log
    from app.services.audit import log_audit

    await log_audit(
        db, action="escrow_create", entity_type="escrow", entity_id=escrow.id,
        user_id=user.id, details={"deal_id": deal_id},
    )
    await db.commit()

    resp = EscrowResponse.model_validate(escrow)
    resp.state_init_boc = escrow_service.get_state_init_boc_b64(escrow)
    return resp


@router.get("/deals/{deal_id}", response_model=EscrowResponse)
async def get_escrow_status(
    deal_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get escrow status for a deal."""
    await deal_svc.get_deal(db, deal_id, user.id)  # access check
    escrow = await escrow_service.get_escrow_for_deal(db, deal_id)
    if not escrow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No escrow found for this deal",
        )
    resp = EscrowResponse.model_validate(escrow)
    resp.state_init_boc = escrow_service.get_state_init_boc_b64(escrow)
    return resp


@router.post("/deals/{deal_id}/confirm-deposit", response_model=EscrowResponse)
async def confirm_deposit(
    deal_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Frontend hint that deposit was sent — triggers on-chain verification."""
    deal = await deal_svc.get_deal(db, deal_id, user.id)
    escrow = await escrow_service.get_escrow_for_deal(db, deal_id)
    if not escrow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No escrow found for this deal",
        )

    if escrow.on_chain_state != "init":
        resp = EscrowResponse.model_validate(escrow)
        resp.state_init_boc = escrow_service.get_state_init_boc_b64(escrow)
        return resp

    verified = await escrow_service.verify_deposit(db, escrow)
    if verified:
        # Transition deal to ESCROW_FUNDED via system
        try:
            await deal_svc.system_transition_deal(db, deal_id, "confirm_escrow")
        except Exception:
            pass  # transition may fail if already transitioned

    await db.refresh(escrow)
    resp = EscrowResponse.model_validate(escrow)
    resp.state_init_boc = escrow_service.get_state_init_boc_b64(escrow)
    return resp
