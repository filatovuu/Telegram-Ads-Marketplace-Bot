export type Role = "owner" | "advertiser";

export interface User {
  id: number;
  telegram_id: number;
  username?: string;
  first_name?: string;
  last_name?: string;
  photo_url?: string;
  active_role: Role;
  locale: string;
  timezone: string;
  wallet_address?: string;
  created_at: string;
}

export type ChannelTeamRole = "owner" | "manager" | "viewer";

export interface Channel {
  id: number;
  telegram_channel_id: number;
  username?: string;
  title: string;
  description?: string;
  invite_link?: string;
  subscribers: number;
  avg_views: number;
  language?: string;
  language_manual: boolean;
  is_verified: boolean;
  bot_is_admin: boolean;
  owner_id: number;
  user_role?: ChannelTeamRole;
  created_at: string;
}

export interface ChannelTeamMember {
  id: number;
  user_id: number;
  channel_id: number;
  role: ChannelTeamRole;
  can_accept_deals: boolean;
  can_post: boolean;
  can_payout: boolean;
  is_telegram_admin?: boolean;
  user: User;
}

export interface Listing {
  id: number;
  channel_id: number;
  title: string;
  description?: string;
  price: number;
  currency: string;
  format: string;
  language?: string;
  is_active: boolean;
  channel: Channel;
  created_at: string;
}

export interface ListingFilter {
  min_price?: number;
  max_price?: number;
  language?: string;
  category?: string;
  format?: string;
  min_subscribers?: number;
  min_avg_views?: number;
  min_growth_pct_7d?: number;
}

export interface ChannelStats {
  channel_id: number;
  subscribers: number;
  subscribers_growth_7d: number | null;
  subscribers_growth_30d: number | null;
  subscribers_growth_pct_7d: number | null;
  subscribers_growth_pct_30d: number | null;
  avg_views: number | null;
  avg_views_10: number | null;
  avg_views_30: number | null;
  avg_views_50: number | null;
  median_views: number | null;
  reach_pct: number | null;
  posts_per_week: number | null;
  posts_tracked: number;
  reactions_per_views: number | null;
  forwards_per_views: number | null;
  velocity_1h_ratio: number | null;
  posts_7d: number | null;
  posts_30d: number | null;
  posts_per_day_7d: number | null;
  posts_per_day_30d: number | null;
  edit_rate: number | null;
  source: string;
  collected_at: string;
}

export interface StatsDataPoint {
  timestamp: string;
  subscribers: number;
}

export interface ChannelStatsHistory {
  channel_id: number;
  data_points: StatsDataPoint[];
}

export interface ChannelPublicStats {
  channel_id: number;
  subscribers: number;
  subscribers_growth_pct_7d: number | null;
  subscribers_growth_pct_30d: number | null;
  avg_views: number | null;
  median_views: number | null;
  reach_pct: number | null;
  posts_per_week: number | null;
  reactions_per_views: number | null;
  forwards_per_views: number | null;
  velocity_1h_ratio: number | null;
  posts_per_day_7d: number | null;
  edit_rate: number | null;
  source: string;
  collected_at: string;
}

export interface Campaign {
  id: number;
  advertiser_id: number;
  title: string;
  brief?: string;
  category?: string;
  target_language?: string;
  budget_min: number;
  budget_max: number;
  publish_from?: string;
  publish_to?: string;
  links?: string;
  restrictions?: string;
  is_active: boolean;
  created_at: string;
}

export interface CampaignCreate {
  title: string;
  brief?: string;
  category?: string;
  target_language?: string;
  budget_min: number;
  budget_max: number;
  publish_from?: string;
  publish_to?: string;
  links?: string;
  restrictions?: string;
}

export type DealStatus =
  | "DRAFT"
  | "NEGOTIATION"
  | "OWNER_ACCEPTED"
  | "AWAITING_ESCROW_PAYMENT"
  | "ESCROW_FUNDED"
  | "CREATIVE_PENDING_OWNER"
  | "CREATIVE_SUBMITTED"
  | "CREATIVE_CHANGES_REQUESTED"
  | "CREATIVE_APPROVED"
  | "SCHEDULED"
  | "POSTED"
  | "RETENTION_CHECK"
  | "RELEASED"
  | "REFUNDED"
  | "CANCELLED"
  | "EXPIRED";

export interface Deal {
  id: number;
  listing_id: number | null;
  campaign_id: number | null;
  advertiser_id: number;
  owner_id: number;
  status: DealStatus;
  price: number;
  currency: string;
  escrow_address?: string;
  owner_wallet_address?: string;
  owner_wallet_confirmed?: boolean;
  brief?: string;
  publish_from?: string;
  publish_to?: string;
  created_at: string;
  updated_at: string;
}

export interface DealDetail extends Deal {
  listing: Listing | null;
}

export interface DealMessage {
  id: number;
  deal_id: number;
  sender_user_id: number | null;
  text: string;
  message_type: "text" | "system";
  created_at: string;
}

export interface DealAmendment {
  id: number;
  deal_id: number;
  proposed_by_user_id: number;
  proposed_price?: number;
  proposed_publish_date?: string;
  proposed_description?: string;
  status: "pending" | "accepted" | "rejected";
  created_at: string;
}

export interface Escrow {
  id: number;
  deal_id: number;
  contract_address?: string;
  advertiser_address?: string;
  owner_address?: string;
  platform_address?: string;
  amount: number;
  deadline?: string;
  on_chain_state: "init" | "funded" | "released" | "refunded";
  fee_percent: number;
  deploy_tx_hash?: string;
  deposit_tx_hash?: string;
  release_tx_hash?: string;
  refund_tx_hash?: string;
  funded_at?: string;
  released_at?: string;
  refunded_at?: string;
  state_init_boc?: string;
}

export interface MediaItem {
  file_id: string;
  type: "photo" | "video" | "document" | "animation";
}

export interface CreativeVersion {
  id: number;
  deal_id: number;
  version: number;
  text: string;
  entities_json?: string;
  media_items?: MediaItem[];
  status: "submitted" | "approved" | "changes_requested";
  feedback?: string;
  is_current: boolean;
  created_at: string;
}

export interface DealPosting {
  id: number;
  deal_id: number;
  channel_id: number;
  telegram_message_id?: number;
  posted_at?: string;
  scheduled_at?: string;
  retention_hours: number;
  verified_at?: string;
  retained?: boolean;
  verification_error?: string;
  created_at: string;
}

export interface RetentionCheckResult {
  ok: boolean;
  elapsed: boolean;
  finalized: boolean;
  error?: string;
  posting: DealPosting;
}

export interface DealDetailWithActions extends Deal {
  listing: Listing | null;
  messages: DealMessage[];
  available_actions: string[];
  can_manage_wallet?: boolean;
  pending_amendment?: DealAmendment;
  escrow?: Escrow;
  current_creative?: CreativeVersion;
  creative_history?: CreativeVersion[];
  posting?: DealPosting;
}

export interface AuthResponse {
  access_token: string;
  user: User;
}

export interface PlatformConfig {
  platform_fee_percent: number;
  escrow_gas_ton: number;
  min_price_ton: number;
  ton_network?: string;
}

export interface CampaignPublic {
  id: number;
  advertiser_id: number;
  title: string;
  brief?: string;
  category?: string;
  target_language?: string;
  budget_min: number;
  budget_max: number;
  publish_from?: string;
  publish_to?: string;
  restrictions?: string;
  is_active: boolean;
  created_at: string;
}

export interface CampaignFilter {
  min_budget?: number;
  max_budget?: number;
  category?: string;
  target_language?: string;
}

export interface OwnerDealCreate {
  campaign_id: number;
  listing_id: number;
  price: number;
  currency?: string;
  brief?: string;
  publish_from?: string;
  publish_to?: string;
}
