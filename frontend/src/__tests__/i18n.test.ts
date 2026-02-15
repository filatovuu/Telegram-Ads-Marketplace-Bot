import { describe, it, expect } from "vitest";
import en from "@/i18n/locales/en/common.json";
import ru from "@/i18n/locales/ru/common.json";

const REQUIRED_KEYS = [
  "app_name",
  "loading",
  "role_owner",
  "role_advertiser",
  "nav_deals",
  "nav_search",
  "nav_profile",
  "nav_channels",
  "nav_listings",
  "nav_campaigns",
  "empty_deals",
  "empty_channels",
  "empty_listings",
  "empty_campaigns",
  "deal_status_draft",
  "deal_status_negotiation",
  "deal_status_released",
  "deal_status_refunded",
  "deal_status_cancelled",
  "deal_status_expired",
  "deal_action_send",
  "deal_action_accept",
  "deal_action_cancel",
  "escrow_title",
  "creative_title",
  "error_network",
];

describe("i18n translations", () => {
  it("EN locale has all required keys", () => {
    for (const key of REQUIRED_KEYS) {
      expect(en).toHaveProperty(key);
      expect((en as Record<string, string>)[key]).toBeTruthy();
    }
  });

  it("RU locale has all required keys", () => {
    for (const key of REQUIRED_KEYS) {
      expect(ru).toHaveProperty(key);
      expect((ru as Record<string, string>)[key]).toBeTruthy();
    }
  });

  it("EN and RU have the same set of keys", () => {
    const enKeys = Object.keys(en).sort();
    const ruKeys = Object.keys(ru).sort();
    expect(enKeys).toEqual(ruKeys);
  });

  it("no EN value is empty string", () => {
    for (const [key, value] of Object.entries(en)) {
      expect(value, `EN key "${key}" is empty`).not.toBe("");
    }
  });

  it("no RU value is empty string", () => {
    for (const [key, value] of Object.entries(ru)) {
      expect(value, `RU key "${key}" is empty`).not.toBe("");
    }
  });
});
