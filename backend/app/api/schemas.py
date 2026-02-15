from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_serializer


def _to_friendly(addr: str | None) -> str | None:
    """Convert a TON address to user-friendly base64 format if needed."""
    if not addr or not addr.startswith("0:"):
        return addr  # already friendly or empty
    try:
        from pytoniq_core import Address as TonAddress
        from app.core.config import settings

        is_testnet = settings.ton_network == "testnet"
        return TonAddress(addr).to_str(is_bounceable=True, is_test_only=is_testnet)
    except Exception:
        return addr


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TelegramAuthRequest(BaseModel):
    init_data: str
    timezone: str | None = None


class UserResponse(BaseModel):
    id: int
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    photo_url: str | None
    locale: str
    timezone: str
    active_role: Literal["advertiser", "owner"]
    wallet_address: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("wallet_address")
    @classmethod
    def _friendly_wallet(cls, v: str | None) -> str | None:
        return _to_friendly(v)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class RoleSwitchRequest(BaseModel):
    role: Literal["advertiser", "owner"]


class LocaleUpdateRequest(BaseModel):
    locale: Literal["en", "ru"]


# ---------------------------------------------------------------------------
# Channel
# ---------------------------------------------------------------------------


class ChannelCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)


class ChannelUpdate(BaseModel):
    description: str | None = None
    invite_link: str | None = None
    language: str | None = None
    language_manual: bool | None = None


class ChannelResponse(BaseModel):
    id: int
    telegram_channel_id: int
    username: str | None
    title: str
    description: str | None
    invite_link: str | None
    subscribers: int
    avg_views: int
    language: str | None
    language_manual: bool = False
    is_verified: bool
    bot_is_admin: bool
    owner_id: int
    user_role: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChannelDeletePreview(BaseModel):
    active_deals_count: int


# ---------------------------------------------------------------------------
# Channel Team
# ---------------------------------------------------------------------------


class TeamMemberAdd(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)
    role: Literal["manager", "viewer"] = "manager"
    can_accept_deals: bool = False
    can_post: bool = False
    can_payout: bool = False


class TeamMemberUpdate(BaseModel):
    role: Literal["manager", "viewer"] | None = None
    can_accept_deals: bool | None = None
    can_post: bool | None = None
    can_payout: bool | None = None


class TeamMemberResponse(BaseModel):
    id: int
    user_id: int
    channel_id: int
    role: str
    can_accept_deals: bool
    can_post: bool
    can_payout: bool
    is_telegram_admin: bool | None = None
    user: UserResponse

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


class ListingCreate(BaseModel):
    channel_id: int
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    price: Decimal = Field(..., ge=Decimal("0.5"))
    currency: str = "TON"
    format: str = "post"


class ListingUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    price: Decimal | None = Field(default=None, ge=Decimal("0.5"))
    currency: str | None = None
    format: str | None = None
    is_active: bool | None = None


class ListingResponse(BaseModel):
    id: int
    channel_id: int
    title: str
    description: str | None
    price: Decimal
    currency: str
    format: str
    language: str | None
    is_active: bool
    channel: ChannelResponse
    created_at: datetime

    model_config = {"from_attributes": True}


class ListingFilter(BaseModel):
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    language: str | None = None
    category: str | None = None
    format: str | None = None
    min_subscribers: int | None = None
    min_avg_views: int | None = None
    min_growth_pct_7d: float | None = None


# ---------------------------------------------------------------------------
# Campaign
# ---------------------------------------------------------------------------


class CampaignCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    brief: str | None = None
    category: str | None = None
    target_language: str | None = None
    budget_min: Decimal = Field(..., ge=0)
    budget_max: Decimal = Field(..., ge=0)
    publish_from: datetime | None = None
    publish_to: datetime | None = None
    links: str | None = None
    restrictions: str | None = None


class CampaignUpdate(BaseModel):
    title: str | None = None
    brief: str | None = None
    category: str | None = None
    target_language: str | None = None
    budget_min: Decimal | None = Field(default=None, ge=0)
    budget_max: Decimal | None = Field(default=None, ge=0)
    publish_from: datetime | None = None
    publish_to: datetime | None = None
    links: str | None = None
    restrictions: str | None = None
    is_active: bool | None = None


class CampaignResponse(BaseModel):
    id: int
    advertiser_id: int
    title: str
    brief: str | None
    category: str | None
    target_language: str | None
    budget_min: Decimal
    budget_max: Decimal
    publish_from: datetime | None
    publish_to: datetime | None
    links: str | None
    restrictions: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CampaignPublicResponse(BaseModel):
    id: int
    advertiser_id: int
    title: str
    brief: str | None
    category: str | None
    target_language: str | None
    budget_min: Decimal
    budget_max: Decimal
    publish_from: datetime | None
    publish_to: datetime | None
    restrictions: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Deal
# ---------------------------------------------------------------------------


class DealCreate(BaseModel):
    listing_id: int
    price: Decimal = Field(..., ge=Decimal("0.5"))
    currency: str = "TON"
    brief: str | None = None
    publish_from: datetime | None = None
    publish_to: datetime | None = None


class OwnerDealCreate(BaseModel):
    campaign_id: int
    listing_id: int
    price: Decimal = Field(..., ge=Decimal("0.5"))
    currency: str = "TON"
    brief: str | None = None
    publish_from: datetime | None = None
    publish_to: datetime | None = None


class DealUpdate(BaseModel):
    brief: str | None = None
    publish_from: datetime | None = None
    publish_to: datetime | None = None


class DealResponse(BaseModel):
    id: int
    listing_id: int | None
    campaign_id: int | None
    advertiser_id: int
    owner_id: int
    status: str
    price: Decimal
    currency: str
    escrow_address: str | None
    owner_wallet_address: str | None = None
    owner_wallet_confirmed: bool = False
    brief: str | None = None
    publish_from: datetime | None = None
    publish_to: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DealDetailResponse(DealResponse):
    listing: ListingResponse | None = None


class DealTransitionRequest(BaseModel):
    action: str


class MediaItem(BaseModel):
    file_id: str = Field(..., min_length=1, max_length=1024)
    type: str = Field(..., pattern="^(photo|video|document|animation)$")


class DealMessageCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    media_items: list[MediaItem] | None = None


class DealMessageResponse(BaseModel):
    id: int
    deal_id: int
    sender_user_id: int | None
    text: str
    message_type: str
    media_items: list[dict] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DealAmendmentResponse(BaseModel):
    id: int
    deal_id: int
    proposed_by_user_id: int
    proposed_price: Decimal | None = None
    proposed_publish_date: datetime | None = None
    proposed_description: str | None = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DealAmendmentCreate(BaseModel):
    proposed_price: Decimal | None = Field(default=None, ge=Decimal("0.5"))
    proposed_publish_date: datetime | None = None
    proposed_description: str | None = None


class DealAmendmentAction(BaseModel):
    action: Literal["accept", "reject"]


class EscrowResponse(BaseModel):
    id: int
    deal_id: int
    contract_address: str | None
    advertiser_address: str | None
    owner_address: str | None
    platform_address: str | None
    amount: Decimal
    deadline: datetime | None
    on_chain_state: str
    fee_percent: int = 0
    deploy_tx_hash: str | None = None
    deposit_tx_hash: str | None = None
    release_tx_hash: str | None = None
    refund_tx_hash: str | None = None
    funded_at: datetime | None = None
    released_at: datetime | None = None
    refunded_at: datetime | None = None
    state_init_boc: str | None = None

    model_config = {"from_attributes": True}

    @field_serializer(
        "contract_address",
        "advertiser_address",
        "owner_address",
        "platform_address",
    )
    @classmethod
    def _friendly_addr(cls, v: str | None) -> str | None:
        return _to_friendly(v)


class CreateEscrowRequest(BaseModel):
    advertiser_address: str = Field(..., min_length=1, max_length=128)
    owner_address: str | None = Field(default=None, max_length=128)


class WalletUpdateRequest(BaseModel):
    wallet_address: str | None = Field(default=None, max_length=128)


class DealOwnerWalletUpdate(BaseModel):
    wallet_address: str = Field(..., min_length=1, max_length=128)


class WalletDisconnectResponse(BaseModel):
    disconnected: bool
    active_deal_count: int = 0
    cancelled_deal_count: int = 0
    warning: str | None = None


# ---------------------------------------------------------------------------
# Creative
# ---------------------------------------------------------------------------


class CreativeSubmitRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    entities_json: str | None = None
    media_items: list[MediaItem] | None = None


class CreativeChangesRequest(BaseModel):
    feedback: str = Field(..., min_length=1, max_length=5000)


class CreativeVersionResponse(BaseModel):
    id: int
    deal_id: int
    version: int
    text: str
    entities_json: str | None = None
    media_items: list[dict] | None = None
    status: str
    feedback: str | None = None
    is_current: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Schedule / Posting
# ---------------------------------------------------------------------------


class SchedulePostRequest(BaseModel):
    scheduled_at: datetime


class DealPostingResponse(BaseModel):
    id: int
    deal_id: int
    channel_id: int
    telegram_message_id: int | None = None
    posted_at: datetime | None = None
    scheduled_at: datetime | None = None
    retention_hours: int
    verified_at: datetime | None = None
    retained: bool | None = None
    verification_error: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RetentionCheckResponse(BaseModel):
    ok: bool
    elapsed: bool
    finalized: bool
    error: str | None = None
    posting: DealPostingResponse


class DealDetailWithActionsResponse(DealResponse):
    listing: ListingResponse | None = None
    messages: list[DealMessageResponse] = []
    available_actions: list[str] = []
    can_manage_wallet: bool = False
    pending_amendment: DealAmendmentResponse | None = None
    escrow: EscrowResponse | None = None
    current_creative: CreativeVersionResponse | None = None
    creative_history: list[CreativeVersionResponse] = []
    posting: DealPostingResponse | None = None


# ---------------------------------------------------------------------------
# Internal Bot requests
# ---------------------------------------------------------------------------


class BotRegisterChannelRequest(BaseModel):
    telegram_channel_id: int
    title: str
    username: str | None = None
    admin_telegram_id: int


class BotUpdateChannelBotStatusRequest(BaseModel):
    telegram_channel_id: int
    bot_is_admin: bool


class BotDealTransitionRequest(BaseModel):
    user_id: int
    action: str


class BotDealMessageCreate(BaseModel):
    user_id: int
    text: str = Field(..., min_length=1, max_length=2000)
    media_items: list[MediaItem] | None = None


class BotDealUpdate(BaseModel):
    user_id: int
    brief: str | None = None
    publish_from: datetime | None = None
    publish_to: datetime | None = None


class BotDealAmendmentCreate(BaseModel):
    user_id: int
    proposed_price: Decimal | None = Field(default=None, ge=Decimal("0.5"))
    proposed_publish_date: datetime | None = None
    proposed_description: str | None = None


class BotDealAmendmentAction(BaseModel):
    user_id: int
    action: Literal["accept", "reject"]


class BotCreativeSubmitRequest(BaseModel):
    user_id: int
    text: str = Field(..., min_length=1, max_length=10000)
    entities_json: str | None = None
    media_items: list[MediaItem] | None = None


class BotCreativeChangesRequest(BaseModel):
    user_id: int
    feedback: str = Field(..., min_length=1, max_length=5000)


class BotSchedulePostRequest(BaseModel):
    user_id: int
    scheduled_at: datetime


# ---------------------------------------------------------------------------
# Channel Stats
# ---------------------------------------------------------------------------


class StatsDataPoint(BaseModel):
    timestamp: datetime
    subscribers: int


class ChannelStatsResponse(BaseModel):
    channel_id: int
    subscribers: int
    subscribers_growth_7d: int | None
    subscribers_growth_30d: int | None
    subscribers_growth_pct_7d: float | None
    subscribers_growth_pct_30d: float | None
    avg_views: int | None
    avg_views_10: int | None
    avg_views_30: int | None
    avg_views_50: int | None
    median_views: int | None
    reach_pct: float | None
    posts_per_week: float | None
    posts_tracked: int
    reactions_per_views: float | None
    forwards_per_views: float | None
    velocity_1h_ratio: float | None
    posts_7d: int | None
    posts_30d: int | None
    posts_per_day_7d: float | None
    posts_per_day_30d: float | None
    edit_rate: float | None
    source: str
    collected_at: datetime

    @classmethod
    def from_snapshot(cls, snapshot) -> "ChannelStatsResponse":
        return cls(
            channel_id=snapshot.channel_id,
            subscribers=snapshot.subscribers,
            subscribers_growth_7d=snapshot.subscribers_growth_7d,
            subscribers_growth_30d=snapshot.subscribers_growth_30d,
            subscribers_growth_pct_7d=snapshot.subscribers_growth_pct_7d,
            subscribers_growth_pct_30d=snapshot.subscribers_growth_pct_30d,
            avg_views=snapshot.avg_views,
            avg_views_10=snapshot.avg_views_10,
            avg_views_30=snapshot.avg_views_30,
            avg_views_50=snapshot.avg_views_50,
            median_views=snapshot.median_views,
            reach_pct=snapshot.reach_pct,
            posts_per_week=snapshot.posts_per_week,
            posts_tracked=snapshot.posts_tracked,
            reactions_per_views=snapshot.reactions_per_views,
            forwards_per_views=snapshot.forwards_per_views,
            velocity_1h_ratio=snapshot.velocity_1h_ratio,
            posts_7d=snapshot.posts_7d,
            posts_30d=snapshot.posts_30d,
            posts_per_day_7d=snapshot.posts_per_day_7d,
            posts_per_day_30d=snapshot.posts_per_day_30d,
            edit_rate=snapshot.edit_rate,
            source=snapshot.source,
            collected_at=snapshot.created_at,
        )


class ChannelPublicStatsResponse(BaseModel):
    channel_id: int
    subscribers: int
    subscribers_growth_pct_7d: float | None
    subscribers_growth_pct_30d: float | None
    avg_views: int | None
    median_views: int | None
    reach_pct: float | None
    posts_per_week: float | None
    reactions_per_views: float | None
    forwards_per_views: float | None
    velocity_1h_ratio: float | None
    posts_per_day_7d: float | None
    edit_rate: float | None
    source: str
    collected_at: datetime

    @classmethod
    def from_snapshot(cls, snapshot) -> "ChannelPublicStatsResponse":
        return cls(
            channel_id=snapshot.channel_id,
            subscribers=snapshot.subscribers,
            subscribers_growth_pct_7d=snapshot.subscribers_growth_pct_7d,
            subscribers_growth_pct_30d=snapshot.subscribers_growth_pct_30d,
            avg_views=snapshot.avg_views,
            median_views=snapshot.median_views,
            reach_pct=snapshot.reach_pct,
            posts_per_week=snapshot.posts_per_week,
            reactions_per_views=snapshot.reactions_per_views,
            forwards_per_views=snapshot.forwards_per_views,
            velocity_1h_ratio=snapshot.velocity_1h_ratio,
            posts_per_day_7d=snapshot.posts_per_day_7d,
            edit_rate=snapshot.edit_rate,
            source=snapshot.source,
            collected_at=snapshot.created_at,
        )


class ChannelStatsHistoryResponse(BaseModel):
    channel_id: int
    data_points: list[StatsDataPoint]


# ---------------------------------------------------------------------------
# Paginated Responses
# ---------------------------------------------------------------------------


class PaginatedListingResponse(BaseModel):
    items: list[ListingResponse]
    total: int
    offset: int
    limit: int
    has_more: bool


class PaginatedDealResponse(BaseModel):
    items: list[DealResponse]
    total: int
    offset: int
    limit: int
    has_more: bool


class PaginatedChannelResponse(BaseModel):
    items: list[ChannelResponse]
    total: int
    offset: int
    limit: int
    has_more: bool


class PaginatedCampaignResponse(BaseModel):
    items: list[CampaignResponse]
    total: int
    offset: int
    limit: int
    has_more: bool


class PaginatedCampaignPublicResponse(BaseModel):
    items: list[CampaignPublicResponse]
    total: int
    offset: int
    limit: int
    has_more: bool
