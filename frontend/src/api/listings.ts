import api from "@/api/client";
import type { ChannelPublicStats, Listing, ListingFilter, PlatformConfig } from "@/api/types";

export async function getMyListings(): Promise<Listing[]> {
  return api.get<Listing[]>("/owner/listings");
}

export async function createListing(data: {
  channel_id: number;
  title: string;
  description?: string;
  price: number;
  currency?: string;
  format?: string;
}): Promise<Listing> {
  return api.post<Listing>("/owner/listings", data);
}

export async function updateListing(
  id: number,
  data: {
    title?: string;
    description?: string;
    price?: number;
    currency?: string;
    format?: string;
    is_active?: boolean;
  },
): Promise<Listing> {
  return api.patch<Listing>(`/owner/listings/${id}`, data);
}

export async function deleteListing(id: number): Promise<void> {
  return api.delete(`/owner/listings/${id}`);
}

interface PaginatedListings {
  items: Listing[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

export async function searchListings(filters: ListingFilter = {}): Promise<Listing[]> {
  const params = new URLSearchParams();
  if (filters.min_price != null) params.set("min_price", String(filters.min_price));
  if (filters.max_price != null) params.set("max_price", String(filters.max_price));
  if (filters.language) params.set("language", filters.language);
  if (filters.min_subscribers != null) params.set("min_subscribers", String(filters.min_subscribers));
  if (filters.min_avg_views != null) params.set("min_avg_views", String(filters.min_avg_views));
  if (filters.min_growth_pct_7d != null) params.set("min_growth_pct_7d", String(filters.min_growth_pct_7d));
  const qs = params.toString();
  const resp = await api.get<PaginatedListings>(`/market/listings${qs ? `?${qs}` : ""}`);
  return resp.items;
}

export async function getMarketListing(id: number): Promise<Listing> {
  return api.get<Listing>(`/market/listings/${id}`);
}

export async function getPublicChannelStats(channelId: number): Promise<ChannelPublicStats> {
  return api.get<ChannelPublicStats>(`/market/channels/${channelId}/stats`);
}

export async function getPlatformConfig(): Promise<PlatformConfig> {
  return api.get<PlatformConfig>("/config/public");
}
