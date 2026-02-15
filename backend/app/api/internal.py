from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    BotCreativeChangesRequest,
    BotCreativeSubmitRequest,
    BotDealAmendmentAction,
    BotDealAmendmentCreate,
    BotDealMessageCreate,
    BotDealTransitionRequest,
    BotDealUpdate,
    BotRegisterChannelRequest,
    BotSchedulePostRequest,
    BotUpdateChannelBotStatusRequest,
    ChannelResponse,
    CreativeVersionResponse,
    DealAmendmentResponse,
    DealDetailWithActionsResponse,
    DealMessageResponse,
    DealPostingResponse,
    DealResponse,
    DealUpdate,
    EscrowResponse,
    UserResponse,
)
from app.core.deps import get_db
from app.services import amendment as amendment_svc
from app.services import channel as channel_svc
from app.services import creative as creative_svc
from app.services import deal as deal_svc
from app.services import posting as posting_svc
from app.services import stats as stats_svc
from app.services.user import get_user_by_id, upsert_user

router = APIRouter(prefix="/internal/bot", tags=["internal"])


class BotUpsertRequest(BaseModel):
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None


@router.post("/upsert-user", response_model=UserResponse)
async def bot_upsert_user(
    body: BotUpsertRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Internal endpoint for the bot to register/update users.

    Should only be accessible from the internal network (bot container).
    """
    user = await upsert_user(
        db,
        telegram_id=body.telegram_id,
        username=body.username,
        first_name=body.first_name,
        last_name=body.last_name,
        language_code=body.language_code,
    )
    return UserResponse.model_validate(user)


class ChannelPostRequest(BaseModel):
    telegram_channel_id: int
    telegram_message_id: int
    post_type: str = "text"
    views: int | None = None
    text_preview: str | None = None
    date: datetime | None = None
    edit_date: datetime | None = None
    has_media: bool = False
    media_group_id: str | None = None
    reactions_count: int | None = None
    forward_count: int | None = None


@router.post("/channel-post")
async def bot_store_channel_post(
    body: ChannelPostRequest,
    db: AsyncSession = Depends(get_db),
):
    """Internal endpoint for the bot to store/update channel posts."""
    post = await stats_svc.upsert_channel_post(
        db,
        telegram_channel_id=body.telegram_channel_id,
        telegram_message_id=body.telegram_message_id,
        post_type=body.post_type,
        views=body.views,
        text_preview=body.text_preview,
        date=body.date,
        edit_date=body.edit_date,
        has_media=body.has_media,
        media_group_id=body.media_group_id,
        reactions_count=body.reactions_count,
        forward_count=body.forward_count,
    )

    # If the post was edited, check if it's a deal post in retention check
    retention_failed = False
    if body.edit_date is not None:
        retention_failed = await posting_svc.fail_retention_on_edit(
            db,
            body.telegram_channel_id,
            body.telegram_message_id,
        )

    if post is None:
        return {"status": "skipped", "reason": "channel not registered"}
    return {
        "status": "ok",
        "post_id": post.id,
        "retention_failed": retention_failed,
    }


@router.post("/register-channel", response_model=ChannelResponse, status_code=201)
async def bot_register_channel(
    body: BotRegisterChannelRequest,
    db: AsyncSession = Depends(get_db),
):
    """Internal endpoint: bot detected it was added as admin to a channel."""
    channel = await channel_svc.create_channel_from_bot_event(
        db,
        telegram_channel_id=body.telegram_channel_id,
        title=body.title,
        username=body.username,
        admin_telegram_id=body.admin_telegram_id,
    )
    return channel


@router.post("/update-channel-bot-status")
async def bot_update_channel_bot_status(
    body: BotUpdateChannelBotStatusRequest,
    db: AsyncSession = Depends(get_db),
):
    """Internal endpoint: bot was removed/demoted from a channel."""
    await channel_svc.update_bot_admin_status(
        db,
        telegram_channel_id=body.telegram_channel_id,
        bot_is_admin=body.bot_is_admin,
    )
    return {"status": "ok"}


@router.get("/deals", response_model=list[DealResponse])
async def bot_get_user_deals(
    user_id: int = Query(...),
    role: str = Query(default="advertiser"),
    db: AsyncSession = Depends(get_db),
):
    """Internal endpoint for the bot to fetch a user's deals."""
    return await deal_svc.get_deals_by_user(db, user_id, role=role)


@router.get("/deals/{deal_id}")
async def bot_get_deal_detail(
    deal_id: int,
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Internal endpoint for the bot to fetch deal detail with actions."""
    detail = await deal_svc.get_deal_detail(db, deal_id, user_id)
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
        messages=[DealMessageResponse.model_validate(m) for m in detail["messages"]],
        available_actions=detail["available_actions"],
        can_manage_wallet=detail["can_manage_wallet"],
        pending_amendment=DealAmendmentResponse.model_validate(pending)
        if pending
        else None,
        escrow=EscrowResponse.model_validate(escrow) if escrow else None,
        current_creative=CreativeVersionResponse.model_validate(current_creative)
        if current_creative
        else None,
        creative_history=[
            CreativeVersionResponse.model_validate(c) for c in creative_history
        ],
        posting=DealPostingResponse.model_validate(posting) if posting else None,
    )


@router.patch("/deals/{deal_id}", response_model=DealResponse)
async def bot_update_deal_brief(
    deal_id: int,
    body: BotDealUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Internal endpoint for the bot to update deal brief fields."""
    user = await get_user_by_id(db, body.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return await deal_svc.update_deal_brief(
        db,
        deal_id,
        user,
        DealUpdate(
            brief=body.brief, publish_from=body.publish_from, publish_to=body.publish_to
        ),
    )


@router.post(
    "/deals/{deal_id}/amendments", response_model=DealAmendmentResponse, status_code=201
)
async def bot_propose_amendment(
    deal_id: int,
    body: BotDealAmendmentCreate,
    db: AsyncSession = Depends(get_db),
):
    """Internal endpoint for the bot to propose a deal amendment."""
    user = await get_user_by_id(db, body.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return await amendment_svc.create_amendment(
        db,
        deal_id,
        user,
        proposed_price=body.proposed_price,
        proposed_publish_date=body.proposed_publish_date,
        proposed_description=body.proposed_description,
    )


@router.post(
    "/deals/{deal_id}/amendments/{amendment_id}/resolve",
    response_model=DealAmendmentResponse,
)
async def bot_resolve_amendment(
    deal_id: int,
    amendment_id: int,
    body: BotDealAmendmentAction,
    db: AsyncSession = Depends(get_db),
):
    """Internal endpoint for the bot to resolve a deal amendment."""
    user = await get_user_by_id(db, body.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return await amendment_svc.resolve_amendment(
        db, deal_id, amendment_id, user, body.action
    )


@router.post("/deals/{deal_id}/transition", response_model=DealResponse)
async def bot_deal_transition(
    deal_id: int,
    body: BotDealTransitionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Internal endpoint for the bot to trigger a deal transition."""
    user = await get_user_by_id(db, body.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return await deal_svc.transition_deal(db, deal_id, body.action, user)


@router.post("/deals/{deal_id}/messages", response_model=DealMessageResponse)
async def bot_deal_message(
    deal_id: int,
    body: BotDealMessageCreate,
    db: AsyncSession = Depends(get_db),
):
    """Internal endpoint for the bot to send a deal message."""
    user = await get_user_by_id(db, body.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    media_items = (
        [item.model_dump() for item in body.media_items] if body.media_items else None
    )
    return await deal_svc.add_deal_message(
        db, deal_id, user, body.text, media_items=media_items
    )


@router.post(
    "/deals/{deal_id}/creative", response_model=CreativeVersionResponse, status_code=201
)
async def bot_submit_creative(
    deal_id: int,
    body: BotCreativeSubmitRequest,
    db: AsyncSession = Depends(get_db),
):
    """Internal endpoint for the bot to submit a creative."""
    user = await get_user_by_id(db, body.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    media_items = (
        [item.model_dump() for item in body.media_items] if body.media_items else None
    )
    return await creative_svc.submit_creative(
        db,
        deal_id,
        user,
        text=body.text,
        entities_json=body.entities_json,
        media_items=media_items,
    )


@router.post(
    "/deals/{deal_id}/creative/approve", response_model=CreativeVersionResponse
)
async def bot_approve_creative(
    deal_id: int,
    body: BotDealTransitionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Internal endpoint for the bot to approve a creative."""
    user = await get_user_by_id(db, body.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return await creative_svc.approve_creative(db, deal_id, user)


@router.post(
    "/deals/{deal_id}/creative/request-changes", response_model=CreativeVersionResponse
)
async def bot_request_creative_changes(
    deal_id: int,
    body: BotCreativeChangesRequest,
    db: AsyncSession = Depends(get_db),
):
    """Internal endpoint for the bot to request creative changes."""
    user = await get_user_by_id(db, body.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return await creative_svc.request_changes(db, deal_id, user, body.feedback)


@router.post(
    "/deals/{deal_id}/schedule", response_model=DealPostingResponse, status_code=201
)
async def bot_schedule_post(
    deal_id: int,
    body: BotSchedulePostRequest,
    db: AsyncSession = Depends(get_db),
):
    """Internal endpoint for the bot to schedule a post."""
    user = await get_user_by_id(db, body.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return await posting_svc.schedule_post(db, deal_id, user, body.scheduled_at)
