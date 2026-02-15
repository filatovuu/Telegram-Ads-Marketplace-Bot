import api from "@/api/client";
import type { Channel, ChannelStats, ChannelStatsHistory, ChannelTeamMember } from "@/api/types";

export async function getMyChannels(): Promise<Channel[]> {
  return api.get<Channel[]>("/owner/channels");
}

export async function addChannel(username: string): Promise<Channel> {
  return api.post<Channel>("/owner/channels", { username });
}

export async function getChannel(id: number): Promise<Channel> {
  return api.get<Channel>(`/owner/channels/${id}`);
}

export async function updateChannel(
  id: number,
  data: { description?: string; invite_link?: string; language?: string; language_manual?: boolean },
): Promise<Channel> {
  return api.patch<Channel>(`/owner/channels/${id}`, data);
}

export async function getChannelDeletePreview(id: number): Promise<{ active_deals_count: number }> {
  return api.get<{ active_deals_count: number }>(`/owner/channels/${id}/delete-preview`);
}

export async function deleteChannel(id: number): Promise<void> {
  return api.delete(`/owner/channels/${id}`);
}

export async function refreshChannelStats(id: number): Promise<Channel> {
  return api.post<Channel>(`/owner/channels/${id}/refresh`, {});
}

export async function getTeamMembers(channelId: number): Promise<ChannelTeamMember[]> {
  return api.get<ChannelTeamMember[]>(`/owner/channels/${channelId}/team`);
}

export async function addTeamMember(
  channelId: number,
  data: { username: string; role?: string; can_accept_deals: boolean; can_post: boolean; can_payout: boolean },
): Promise<ChannelTeamMember> {
  return api.post<ChannelTeamMember>(`/owner/channels/${channelId}/team`, data);
}

export async function updateTeamMember(
  channelId: number,
  memberId: number,
  data: { role?: string; can_accept_deals?: boolean; can_post?: boolean; can_payout?: boolean },
): Promise<ChannelTeamMember> {
  return api.patch<ChannelTeamMember>(`/owner/channels/${channelId}/team/${memberId}`, data);
}

export async function removeTeamMember(channelId: number, memberId: number): Promise<void> {
  return api.delete(`/owner/channels/${channelId}/team/${memberId}`);
}

export async function getChannelStats(channelId: number): Promise<ChannelStats> {
  return api.get<ChannelStats>(`/owner/channels/${channelId}/stats`);
}

export async function getChannelStatsHistory(
  channelId: number,
  days = 30,
): Promise<ChannelStatsHistory> {
  return api.get<ChannelStatsHistory>(`/owner/channels/${channelId}/stats/history?days=${days}`);
}

export async function refreshChannelStatsSnapshot(channelId: number): Promise<ChannelStats> {
  return api.post<ChannelStats>(`/owner/channels/${channelId}/stats/refresh`, {});
}
