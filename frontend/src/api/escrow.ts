import api from "./client";
import type { Escrow, User } from "./types";

export async function createEscrow(
  dealId: number,
  advertiserAddress: string,
  ownerAddress?: string,
): Promise<Escrow> {
  const body: Record<string, string> = { advertiser_address: advertiserAddress };
  if (ownerAddress) body.owner_address = ownerAddress;
  return api.post<Escrow>(`/escrow/deals/${dealId}/create`, body);
}

export async function getEscrowStatus(dealId: number): Promise<Escrow> {
  return api.get<Escrow>(`/escrow/deals/${dealId}`);
}

export async function confirmDeposit(dealId: number): Promise<Escrow> {
  return api.post<Escrow>(`/escrow/deals/${dealId}/confirm-deposit`, {});
}

export async function updateWallet(walletAddress: string | null): Promise<User> {
  return api.patch<User>("/me/wallet", { wallet_address: walletAddress });
}

export interface WalletDisconnectResult {
  disconnected: boolean;
  active_deal_count: number;
  cancelled_deal_count: number;
  warning?: string;
}

export async function disconnectWallet(
  confirm = false,
): Promise<WalletDisconnectResult> {
  return api.delete<WalletDisconnectResult>(
    `/me/wallet?confirm=${confirm}`,
  );
}
