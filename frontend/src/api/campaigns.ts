import api from "@/api/client";
import type { Campaign, CampaignCreate, CampaignFilter, CampaignPublic } from "@/api/types";

export async function getMyCampaigns(): Promise<Campaign[]> {
  return api.get<Campaign[]>("/advertiser/campaigns");
}

export async function getCampaign(id: number): Promise<Campaign> {
  return api.get<Campaign>(`/advertiser/campaigns/${id}`);
}

export async function createCampaign(data: CampaignCreate): Promise<Campaign> {
  return api.post<Campaign>("/advertiser/campaigns", data);
}

export async function updateCampaign(
  id: number,
  data: Partial<CampaignCreate & { is_active: boolean }>,
): Promise<Campaign> {
  return api.patch<Campaign>(`/advertiser/campaigns/${id}`, data);
}

export async function deleteCampaign(id: number): Promise<void> {
  return api.delete(`/advertiser/campaigns/${id}`);
}

interface PaginatedCampaigns {
  items: CampaignPublic[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

export async function searchCampaigns(filters: CampaignFilter = {}): Promise<CampaignPublic[]> {
  const params = new URLSearchParams();
  if (filters.min_budget != null) params.set("min_budget", String(filters.min_budget));
  if (filters.max_budget != null) params.set("max_budget", String(filters.max_budget));
  if (filters.category) params.set("category", filters.category);
  if (filters.target_language) params.set("target_language", filters.target_language);
  const qs = params.toString();
  const resp = await api.get<PaginatedCampaigns>(`/market/campaigns${qs ? `?${qs}` : ""}`);
  return resp.items;
}

export async function getMarketCampaign(id: number): Promise<CampaignPublic> {
  return api.get<CampaignPublic>(`/market/campaigns/${id}`);
}
