from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    CampaignCreate,
    CampaignResponse,
    CampaignUpdate,
    CreativeChangesRequest,
    CreativeVersionResponse,
    DealAmendmentAction,
    DealAmendmentResponse,
    DealCreate,
    DealDetailWithActionsResponse,
    DealMessageCreate,
    DealMessageResponse,
    DealPostingResponse,
    DealResponse,
    DealTransitionRequest,
    DealUpdate,
    EscrowResponse,
    RetentionCheckResponse,
)
from app.core.deps import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services import amendment as amendment_svc
from app.services import campaign as campaign_svc
from app.services import creative as creative_svc
from app.services import deal as deal_svc
from app.services.ton.escrow_service import EscrowService

_escrow_svc = EscrowService()


def _escrow_with_state_init(escrow) -> EscrowResponse:
    """Build EscrowResponse with computed state_init_boc."""
    resp = EscrowResponse.model_validate(escrow)
    resp.state_init_boc = _escrow_svc.get_state_init_boc_b64(escrow)
    return resp


router = APIRouter(prefix="/advertiser", tags=["advertiser"])


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------


@router.post("/campaigns", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    body: CampaignCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await campaign_svc.create_campaign(db, user, body)


@router.get("/campaigns", response_model=list[CampaignResponse])
async def list_campaigns(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await campaign_svc.get_campaigns_by_advertiser(
        db, user.id, offset=offset, limit=limit
    )


@router.get("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await campaign_svc.get_campaign(db, campaign_id, user.id)


@router.patch("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: int,
    body: CampaignUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    campaign = await campaign_svc.get_campaign(db, campaign_id, user.id)
    return await campaign_svc.update_campaign(db, campaign, body)


@router.delete("/campaigns/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    campaign = await campaign_svc.get_campaign(db, campaign_id, user.id)
    await campaign_svc.delete_campaign(db, campaign)


# ---------------------------------------------------------------------------
# Deals
# ---------------------------------------------------------------------------


@router.post("/deals", response_model=DealResponse, status_code=201)
async def create_deal(
    body: DealCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await deal_svc.create_deal_from_listing(db, user, body)


@router.get("/deals", response_model=list[DealResponse])
async def list_deals(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await deal_svc.get_deals_by_user(
        db, user.id, role="advertiser", offset=offset, limit=limit
    )


@router.get("/deals/{deal_id}", response_model=DealDetailWithActionsResponse)
async def get_deal(
    deal_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    detail = await deal_svc.get_deal_detail(db, deal_id, user.id)
    deal = detail["deal"]
    pending = detail.get("pending_amendment")
    escrow = detail.get("escrow")
    current_creative = detail.get("current_creative")
    creative_history = detail.get("creative_history", [])
    posting = detail.get("posting")
    return DealDetailWithActionsResponse(
        id=deal.id,
        listing_id=deal.listing_id,
        campaign_id=deal.campaign_id,
        advertiser_id=deal.advertiser_id,
        owner_id=deal.owner_id,
        status=deal.status,
        price=deal.price,
        currency=deal.currency,
        escrow_address=deal.escrow_address,
        owner_wallet_address=deal.owner_wallet_address,
        owner_wallet_confirmed=deal.owner_wallet_confirmed,
        brief=deal.brief,
        publish_from=deal.publish_from,
        publish_to=deal.publish_to,
        created_at=deal.created_at,
        updated_at=deal.updated_at,
        listing=deal.listing,
        messages=detail["messages"],
        available_actions=detail["available_actions"],
        can_manage_wallet=detail["can_manage_wallet"],
        pending_amendment=DealAmendmentResponse.model_validate(pending)
        if pending
        else None,
        escrow=_escrow_with_state_init(escrow) if escrow else None,
        current_creative=CreativeVersionResponse.model_validate(current_creative)
        if current_creative
        else None,
        creative_history=[
            CreativeVersionResponse.model_validate(c) for c in creative_history
        ],
        posting=DealPostingResponse.model_validate(posting) if posting else None,
    )


@router.post(
    "/deals/{deal_id}/creative/approve", response_model=CreativeVersionResponse
)
async def approve_creative(
    deal_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await creative_svc.approve_creative(db, deal_id, user)


@router.post(
    "/deals/{deal_id}/creative/request-changes", response_model=CreativeVersionResponse
)
async def request_creative_changes(
    deal_id: int,
    body: CreativeChangesRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await creative_svc.request_changes(db, deal_id, user, body.feedback)


@router.get("/deals/{deal_id}/creative", response_model=list[CreativeVersionResponse])
async def get_creative_history(
    deal_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await deal_svc.get_deal(db, deal_id, user.id)  # ownership check
    return await creative_svc.get_creative_history(db, deal_id)


@router.patch("/deals/{deal_id}", response_model=DealResponse)
async def update_deal_brief(
    deal_id: int,
    body: DealUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await deal_svc.update_deal_brief(db, deal_id, user, body)


@router.post(
    "/deals/{deal_id}/amendments/{amendment_id}/resolve",
    response_model=DealAmendmentResponse,
)
async def resolve_amendment(
    deal_id: int,
    amendment_id: int,
    body: DealAmendmentAction,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await amendment_svc.resolve_amendment(
        db, deal_id, amendment_id, user, body.action
    )


@router.post("/deals/{deal_id}/posting/check", response_model=RetentionCheckResponse)
async def manual_check_retention(
    deal_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manual retention check — verifies post integrity."""
    from app.services import posting as posting_svc

    result = await posting_svc.check_retention(db, deal_id, user.id)
    return RetentionCheckResponse(
        ok=result["ok"],
        elapsed=result["elapsed"],
        finalized=result["finalized"],
        error=result["error"],
        posting=DealPostingResponse.model_validate(result["posting"]),
    )


@router.post("/deals/{deal_id}/transition", response_model=DealResponse)
async def transition_deal(
    deal_id: int,
    body: DealTransitionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await deal_svc.transition_deal(db, deal_id, body.action, user)


@router.post(
    "/deals/{deal_id}/messages", response_model=DealMessageResponse, status_code=201
)
async def send_deal_message(
    deal_id: int,
    body: DealMessageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    media_items = (
        [item.model_dump() for item in body.media_items] if body.media_items else None
    )
    return await deal_svc.add_deal_message(
        db, deal_id, user, body.text, media_items=media_items
    )


@router.get("/deals/{deal_id}/messages", response_model=list[DealMessageResponse])
async def list_deal_messages(
    deal_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await deal_svc.get_deal_messages(db, deal_id, user.id, limit, offset)
