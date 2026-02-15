from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    ChannelCreate,
    ChannelDeletePreview,
    ChannelResponse,
    ChannelStatsHistoryResponse,
    ChannelStatsResponse,
    ChannelUpdate,
    CreativeSubmitRequest,
    CreativeVersionResponse,
    DealAmendmentCreate,
    DealAmendmentResponse,
    DealDetailWithActionsResponse,
    DealMessageCreate,
    DealMessageResponse,
    DealOwnerWalletUpdate,
    DealPostingResponse,
    DealResponse,
    DealTransitionRequest,
    EscrowResponse,
    OwnerDealCreate,
    RetentionCheckResponse,
    ListingCreate,
    ListingResponse,
    ListingUpdate,
    SchedulePostRequest,
    StatsDataPoint,
    TeamMemberAdd,
    TeamMemberResponse,
    TeamMemberUpdate,
    _to_friendly,
)
from app.services.team_permissions import (
    check_telegram_admin_cached,
    get_team_membership,
    get_user_role_for_channel,
    has_permission,
)
from app.core.deps import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services import amendment as amendment_svc
from app.services import channel as channel_svc
from app.services import creative as creative_svc
from app.services import deal as deal_svc
from app.services import listing as listing_svc
from app.services import posting as posting_svc
from app.services import stats as stats_svc
from app.services.ton.escrow_service import EscrowService

_escrow_svc = EscrowService()


def _escrow_with_state_init(escrow) -> EscrowResponse:
    """Build EscrowResponse with computed state_init_boc."""
    resp = EscrowResponse.model_validate(escrow)
    resp.state_init_boc = _escrow_svc.get_state_init_boc_b64(escrow)
    return resp


router = APIRouter(prefix="/owner", tags=["owner"])


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------


@router.post(
    "/channels", response_model=ChannelResponse, status_code=201, deprecated=True
)
async def add_channel(
    body: ChannelCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await channel_svc.create_channel(db, user, body.username)


@router.get("/channels", response_model=list[ChannelResponse])
async def list_channels(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    channels = await channel_svc.get_channels_by_owner(
        db, user.id, offset=offset, limit=limit
    )
    results = []
    for ch in channels:
        resp = ChannelResponse.model_validate(ch)
        role, _ = await get_user_role_for_channel(db, ch, user.id)
        resp.user_role = role
        results.append(resp)
    return results


@router.get("/channels/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    channel_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ch = await channel_svc.get_channel(db, channel_id, user.id)
    resp = ChannelResponse.model_validate(ch)
    role, _ = await get_user_role_for_channel(db, ch, user.id)
    resp.user_role = role
    return resp


@router.patch("/channels/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: int,
    body: ChannelUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    channel = await channel_svc.get_channel(db, channel_id, user.id, owner_only=True)
    return await channel_svc.update_channel(db, channel, body)


@router.get(
    "/channels/{channel_id}/delete-preview", response_model=ChannelDeletePreview
)
async def delete_channel_preview(
    channel_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await channel_svc.get_channel(db, channel_id, user.id, owner_only=True)
    count = await channel_svc.count_active_deals_for_channel(db, channel_id)
    return ChannelDeletePreview(active_deals_count=count)


@router.delete("/channels/{channel_id}", status_code=204)
async def delete_channel(
    channel_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    channel = await channel_svc.get_channel(db, channel_id, user.id, owner_only=True)
    await channel_svc.delete_channel_with_deals(db, channel)


@router.post("/channels/{channel_id}/refresh", response_model=ChannelResponse)
async def refresh_channel(
    channel_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Legacy refresh — kept for backward compatibility. Use stats/refresh instead."""
    channel = await channel_svc.get_channel(db, channel_id, user.id)
    await stats_svc.collect_snapshot(db, channel)
    await db.refresh(channel)
    return channel


# ---------------------------------------------------------------------------
# Channel Stats
# ---------------------------------------------------------------------------


@router.get("/channels/{channel_id}/stats", response_model=ChannelStatsResponse)
async def get_channel_stats(
    channel_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await channel_svc.get_channel(db, channel_id, user.id)  # ownership check
    snapshot = await stats_svc.get_latest_snapshot(db, channel_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No stats available yet. Try refreshing the channel first.",
        )
    return ChannelStatsResponse.from_snapshot(snapshot)


@router.get(
    "/channels/{channel_id}/stats/history",
    response_model=ChannelStatsHistoryResponse,
)
async def get_channel_stats_history(
    channel_id: int,
    days: int = Query(default=30, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await channel_svc.get_channel(db, channel_id, user.id)  # ownership check
    snapshots = await stats_svc.get_snapshot_history(db, channel_id, days=days)
    return ChannelStatsHistoryResponse(
        channel_id=channel_id,
        data_points=[
            StatsDataPoint(timestamp=s.created_at, subscribers=s.subscribers)
            for s in snapshots
        ],
    )


@router.post(
    "/channels/{channel_id}/stats/refresh", response_model=ChannelStatsResponse
)
async def refresh_channel_stats_snapshot(
    channel_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Single unified refresh: fetches subscribers, chat metadata, bot admin status,
    computes growth + all post-based metrics, creates a stats snapshot."""
    channel = await channel_svc.get_channel(db, channel_id, user.id)
    # Rate limit: 1 snapshot per hour
    latest = await stats_svc.get_latest_snapshot(db, channel_id)
    if latest is not None:
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=0.0001)
        if latest.created_at > one_hour_ago:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Stats can only be refreshed once per hour.",
            )
    snapshot = await stats_svc.collect_snapshot(db, channel)
    return ChannelStatsResponse.from_snapshot(snapshot)


# ---------------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------------


@router.get("/channels/{channel_id}/team", response_model=list[TeamMemberResponse])
async def list_team(
    channel_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    channel = await channel_svc.get_channel(
        db, channel_id, user.id
    )  # any team member can view
    members = await channel_svc.get_team_members(db, channel_id)
    results = []
    for m in members:
        resp = TeamMemberResponse.model_validate(m)
        try:
            resp.is_telegram_admin = await check_telegram_admin_cached(
                channel.telegram_channel_id, m.user.telegram_id
            )
        except Exception:
            resp.is_telegram_admin = None
        results.append(resp)
    return results


@router.post(
    "/channels/{channel_id}/team", response_model=TeamMemberResponse, status_code=201
)
async def add_team_member(
    channel_id: int,
    body: TeamMemberAdd,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    channel = await channel_svc.get_channel(db, channel_id, user.id, owner_only=True)
    return await channel_svc.add_team_member(db, channel, body)


@router.patch(
    "/channels/{channel_id}/team/{member_id}", response_model=TeamMemberResponse
)
async def update_team_member(
    channel_id: int,
    member_id: int,
    body: TeamMemberUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    channel = await channel_svc.get_channel(db, channel_id, user.id, owner_only=True)
    return await channel_svc.update_team_member(db, channel, member_id, body)


@router.delete("/channels/{channel_id}/team/{member_id}", status_code=204)
async def remove_team_member(
    channel_id: int,
    member_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    channel = await channel_svc.get_channel(db, channel_id, user.id, owner_only=True)
    await channel_svc.remove_team_member(db, channel, member_id)


# ---------------------------------------------------------------------------
# Listings
# ---------------------------------------------------------------------------


@router.post("/listings", response_model=ListingResponse, status_code=201)
async def create_listing(
    body: ListingCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await listing_svc.create_listing(db, user, body)


@router.get("/listings", response_model=list[ListingResponse])
async def list_listings(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await listing_svc.get_listings_by_owner(
        db, user.id, offset=offset, limit=limit
    )


@router.patch("/listings/{listing_id}", response_model=ListingResponse)
async def update_listing(
    listing_id: int,
    body: ListingUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    listing = await listing_svc.get_listing(db, listing_id)
    if listing.channel.owner_id != user.id:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your listing"
        )
    return await listing_svc.update_listing(db, listing, body)


@router.delete("/listings/{listing_id}", status_code=204)
async def delete_listing(
    listing_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    listing = await listing_svc.get_listing(db, listing_id)
    if listing.channel.owner_id != user.id:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your listing"
        )
    await listing_svc.delete_listing(db, listing)


# ---------------------------------------------------------------------------
# Deals (owner view)
# ---------------------------------------------------------------------------


@router.post("/deals", response_model=DealResponse, status_code=201)
async def create_owner_deal(
    body: OwnerDealCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await deal_svc.create_deal_from_campaign(db, user, body)


@router.get("/deals", response_model=list[DealResponse])
async def list_owner_deals(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await deal_svc.get_deals_by_user(
        db, user.id, role="owner", offset=offset, limit=limit
    )


@router.get("/deals/{deal_id}", response_model=DealDetailWithActionsResponse)
async def get_owner_deal(
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


async def _check_wallet_permission(db: AsyncSession, deal, user: User) -> None:
    """Verify that the user can manage the payout wallet for this deal.

    Owner always allowed.  Team members need role != viewer, can_payout flag,
    and active Telegram admin status.
    """
    if user.id == deal.owner_id:
        return

    if not deal.listing_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to manage the payout wallet for this deal.",
        )

    from sqlalchemy import select
    from app.models.listing import Listing
    from app.models.channel import Channel

    listing_result = await db.execute(
        select(Listing).where(Listing.id == deal.listing_id)
    )
    listing = listing_result.scalar_one_or_none()
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to manage the payout wallet for this deal.",
        )

    member = await get_team_membership(db, listing.channel_id, user.id)
    if member is None or member.role == "viewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to manage the payout wallet for this deal.",
        )

    if not has_permission(member.role, member, "can_payout"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to manage the payout wallet for this deal.",
        )

    channel_result = await db.execute(
        select(Channel).where(Channel.id == listing.channel_id)
    )
    channel = channel_result.scalar_one_or_none()
    if channel:
        is_admin = await check_telegram_admin_cached(
            channel.telegram_channel_id, user.telegram_id
        )
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are no longer an admin of this channel in Telegram.",
            )


@router.patch("/deals/{deal_id}/wallet", response_model=DealResponse)
async def update_deal_wallet(
    deal_id: int,
    body: DealOwnerWalletUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set/update per-deal payout wallet for the owner.

    Allowed until escrow is funded. If escrow exists but is unfunded (init),
    the old escrow record is deleted and a new one is auto-created.
    """
    deal = await deal_svc.get_deal(db, deal_id, user.id)

    await _check_wallet_permission(db, deal, user)

    # Block if escrow contract already exists (address is deterministic)
    existing_escrow = await _escrow_svc.get_escrow_for_deal(db, deal.id)
    if existing_escrow:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot change wallet after escrow contract has been created",
        )

    new_wallet = _to_friendly(body.wallet_address)
    deal.owner_wallet_address = new_wallet
    deal.owner_wallet_confirmed = True
    deal.wallet_notification_sent = (
        False  # wallet state changed — allow re-notification
    )
    await db.commit()
    await db.refresh(deal)

    # If deal is awaiting escrow, try to auto-create now
    if deal.status == "AWAITING_ESCROW_PAYMENT":
        from app.services.escrow_auto import try_auto_create_escrow

        await try_auto_create_escrow(db, deal)

    return deal


@router.post("/deals/{deal_id}/wallet/confirm", response_model=DealResponse)
async def confirm_deal_wallet(
    deal_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm the current wallet (profile or per-deal) for this deal.

    Used when the owner wants to use their profile wallet without
    manually re-entering it.
    """
    deal = await deal_svc.get_deal(db, deal_id, user.id)

    await _check_wallet_permission(db, deal, user)

    existing_escrow = await _escrow_svc.get_escrow_for_deal(db, deal.id)
    if existing_escrow:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot change wallet after escrow contract has been created",
        )

    # If no per-deal wallet set, copy from the *owner's* profile wallet
    if not deal.owner_wallet_address:
        from app.services.user import get_user_by_id

        owner = (
            await get_user_by_id(db, deal.owner_id)
            if user.id != deal.owner_id
            else user
        )
        wallet_source = owner.wallet_address if owner else None
        if not wallet_source:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No wallet connected. Please connect a TON wallet first.",
            )
        deal.owner_wallet_address = _to_friendly(wallet_source)

    deal.owner_wallet_confirmed = True
    deal.wallet_notification_sent = (
        False  # wallet state changed — allow re-notification
    )
    await db.commit()
    await db.refresh(deal)

    if deal.status == "AWAITING_ESCROW_PAYMENT":
        from app.services.escrow_auto import try_auto_create_escrow

        await try_auto_create_escrow(db, deal)

    return deal


@router.post(
    "/deals/{deal_id}/creative", response_model=CreativeVersionResponse, status_code=201
)
async def submit_creative(
    deal_id: int,
    body: CreativeSubmitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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


@router.get("/deals/{deal_id}/creative", response_model=list[CreativeVersionResponse])
async def get_creative_history(
    deal_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await deal_svc.get_deal(db, deal_id, user.id)  # ownership check
    return await creative_svc.get_creative_history(db, deal_id)


@router.post(
    "/deals/{deal_id}/schedule", response_model=DealPostingResponse, status_code=201
)
async def schedule_post(
    deal_id: int,
    body: SchedulePostRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await posting_svc.schedule_post(db, deal_id, user, body.scheduled_at)


@router.post("/deals/{deal_id}/posting/check", response_model=RetentionCheckResponse)
async def manual_check_retention(
    deal_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manual retention check — verifies post integrity."""
    result = await posting_svc.check_retention(db, deal_id, user.id)
    return RetentionCheckResponse(
        ok=result["ok"],
        elapsed=result["elapsed"],
        finalized=result["finalized"],
        error=result["error"],
        posting=DealPostingResponse.model_validate(result["posting"]),
    )


@router.post(
    "/deals/{deal_id}/amendments", response_model=DealAmendmentResponse, status_code=201
)
async def propose_amendment(
    deal_id: int,
    body: DealAmendmentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await amendment_svc.create_amendment(
        db,
        deal_id,
        user,
        proposed_price=body.proposed_price,
        proposed_publish_date=body.proposed_publish_date,
        proposed_description=body.proposed_description,
    )


@router.post("/deals/{deal_id}/transition", response_model=DealResponse)
async def transition_owner_deal(
    deal_id: int,
    body: DealTransitionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await deal_svc.transition_deal(db, deal_id, body.action, user)


@router.post(
    "/deals/{deal_id}/messages", response_model=DealMessageResponse, status_code=201
)
async def send_owner_deal_message(
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
async def list_owner_deal_messages(
    deal_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await deal_svc.get_deal_messages(db, deal_id, user.id, limit, offset)
