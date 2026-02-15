import api from "@/api/client";
import type { CreativeVersion, Deal, DealAmendment, DealDetailWithActions, DealPosting, OwnerDealCreate, RetentionCheckResult } from "@/api/types";

export async function createDeal(data: {
  listing_id: number;
  price: number;
  currency?: string;
  brief?: string;
  publish_from?: string;
  publish_to?: string;
}): Promise<Deal> {
  return api.post<Deal>("/advertiser/deals", data);
}

export async function getMyDeals(): Promise<Deal[]> {
  return api.get<Deal[]>("/advertiser/deals");
}

export async function getOwnerDeals(): Promise<Deal[]> {
  return api.get<Deal[]>("/owner/deals");
}

export async function createOwnerDeal(data: OwnerDealCreate): Promise<Deal> {
  return api.post<Deal>("/owner/deals", data);
}

export async function getDeal(id: number, role: "advertiser" | "owner"): Promise<DealDetailWithActions> {
  const prefix = role === "owner" ? "/owner" : "/advertiser";
  return api.get<DealDetailWithActions>(`${prefix}/deals/${id}`);
}

export async function transitionDeal(
  id: number,
  action: string,
  role: "advertiser" | "owner",
): Promise<Deal> {
  const prefix = role === "owner" ? "/owner" : "/advertiser";
  return api.post<Deal>(`${prefix}/deals/${id}/transition`, { action });
}

export async function updateDealBrief(
  id: number,
  data: { brief?: string; publish_from?: string; publish_to?: string },
): Promise<Deal> {
  return api.patch<Deal>(`/advertiser/deals/${id}`, data);
}

export async function resolveAmendment(
  dealId: number,
  amendmentId: number,
  action: "accept" | "reject",
): Promise<DealAmendment> {
  return api.post<DealAmendment>(
    `/advertiser/deals/${dealId}/amendments/${amendmentId}/resolve`,
    { action },
  );
}

export async function submitCreative(
  id: number,
  data: { text: string; entities_json?: string; media_items?: { file_id: string; type: string }[] },
): Promise<CreativeVersion> {
  return api.post<CreativeVersion>(`/owner/deals/${id}/creative`, data);
}

export async function approveCreative(id: number): Promise<CreativeVersion> {
  return api.post<CreativeVersion>(`/advertiser/deals/${id}/creative/approve`, {});
}

export async function requestCreativeChanges(
  id: number,
  feedback: string,
): Promise<CreativeVersion> {
  return api.post<CreativeVersion>(`/advertiser/deals/${id}/creative/request-changes`, { feedback });
}

export async function getCreativeHistory(
  id: number,
  role: "advertiser" | "owner",
): Promise<CreativeVersion[]> {
  const prefix = role === "owner" ? "/owner" : "/advertiser";
  return api.get<CreativeVersion[]>(`${prefix}/deals/${id}/creative`);
}

export async function schedulePost(
  id: number,
  scheduled_at: string,
): Promise<DealPosting> {
  return api.post<DealPosting>(`/owner/deals/${id}/schedule`, { scheduled_at });
}

export async function updateDealWallet(
  dealId: number,
  walletAddress: string,
): Promise<Deal> {
  return api.patch<Deal>(`/owner/deals/${dealId}/wallet`, { wallet_address: walletAddress });
}

export async function confirmDealWallet(dealId: number): Promise<Deal> {
  return api.post<Deal>(`/owner/deals/${dealId}/wallet/confirm`, {});
}

export async function checkRetention(
  id: number,
  role: "advertiser" | "owner",
): Promise<RetentionCheckResult> {
  const prefix = role === "owner" ? "/owner" : "/advertiser";
  return api.post<RetentionCheckResult>(`${prefix}/deals/${id}/posting/check`, {}, { timeout: 60_000 });
}
