import api from "@/api/client";
import type { AuthResponse, User } from "@/api/types";

export async function loginWithInitData(initData: string): Promise<AuthResponse> {
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return api.post<AuthResponse>("/auth/telegram", { init_data: initData, timezone });
}

export async function getMe(): Promise<User> {
  return api.get<User>("/me");
}

export async function switchRole(role: "advertiser" | "owner"): Promise<User> {
  return api.post<User>("/me/role", { role });
}

export async function updateLocale(locale: "en" | "ru"): Promise<User> {
  return api.patch<User>("/me/locale", { locale });
}
