import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useTheme } from "@/context/ThemeContext";
import { searchListings } from "@/api/listings";
import type { Listing, ListingFilter } from "@/api/types";
import { SkeletonList } from "@/ui/Skeleton";
import EmptyState from "@/ui/EmptyState";
import ErrorMessage from "@/ui/ErrorMessage";

function Search() {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<ListingFilter>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setListings(await searchListings(filters));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [filters, t]);

  useEffect(() => { load(); }, [load]);

  const filtered = query.trim()
    ? listings.filter((li) => {
        const q = query.toLowerCase();
        return (
          li.title.toLowerCase().includes(q) ||
          (li.description?.toLowerCase().includes(q) ?? false) ||
          li.channel.title.toLowerCase().includes(q) ||
          (li.channel.username?.toLowerCase().includes(q) ?? false) ||
          (li.channel.description?.toLowerCase().includes(q) ?? false)
        );
      })
    : listings;

  const MAX_FILTER_VALUE = 999_999_999;

  const handleFilterChange = (key: keyof ListingFilter, value: string) => {
    if (value === "") {
      setFilters((prev) => ({ ...prev, [key]: undefined }));
      return;
    }
    if (key === "language" || key === "category" || key === "format") {
      setFilters((prev) => ({ ...prev, [key]: value }));
      return;
    }
    const num = Number(value.replace(",", "."));
    if (isNaN(num) || num < 0) return;
    setFilters((prev) => ({ ...prev, [key]: Math.min(num, MAX_FILTER_VALUE) }));
  };

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "8px 10px",
    fontSize: 14,
    borderRadius: 8,
    border: `1px solid ${theme.border}`,
    backgroundColor: theme.bgSecondary,
    color: theme.text,
    outline: "none",
    boxSizing: "border-box",
  };

  return (
    <div style={{ paddingTop: 8, paddingBottom: 16 }}>
      {/* Search bar */}
      <div
        style={{
          backgroundColor: theme.bgSecondary,
          borderRadius: 12,
          padding: "6px 10px",
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 12,
        }}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={theme.textSecondary} strokeWidth="2" strokeLinecap="round" style={{ flexShrink: 0 }}>
          <circle cx="11" cy="11" r="7" /><path d="M21 21l-4.35-4.35" />
        </svg>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("search_placeholder")}
          style={{
            flex: 1,
            border: "none",
            outline: "none",
            background: "transparent",
            color: theme.text,
            fontSize: 15,
            padding: "6px 0",
          }}
        />
        <button
          onClick={() => setShowFilters(!showFilters)}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 32,
            height: 32,
            borderRadius: 8,
            border: "none",
            backgroundColor: showFilters ? `${theme.accent}18` : "transparent",
            cursor: "pointer",
            flexShrink: 0,
          }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={showFilters ? theme.accent : theme.textSecondary} strokeWidth="2" strokeLinecap="round">
            <line x1="4" y1="6" x2="20" y2="6" /><line x1="6" y1="12" x2="18" y2="12" /><line x1="9" y1="18" x2="15" y2="18" />
          </svg>
        </button>
      </div>

      {/* Filters */}
      {showFilters && (
        <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 12, padding: 14, marginBottom: 16, display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <div>
              <label style={{ fontSize: 12, color: theme.textSecondary, display: "block", marginBottom: 4 }}>{t("filter_min_price")}</label>
              <input
                type="text"
                inputMode="decimal"
                value={filters.min_price ?? ""}
                onChange={(e) => handleFilterChange("min_price", e.target.value)}
                placeholder="0"
                style={inputStyle}
              />
            </div>
            <div>
              <label style={{ fontSize: 12, color: theme.textSecondary, display: "block", marginBottom: 4 }}>{t("filter_max_price")}</label>
              <input
                type="text"
                inputMode="decimal"
                value={filters.max_price ?? ""}
                onChange={(e) => handleFilterChange("max_price", e.target.value)}
                placeholder={t("filter_any")}
                style={inputStyle}
              />
            </div>
          </div>
          <div>
            <label style={{ fontSize: 12, color: theme.textSecondary, display: "block", marginBottom: 4 }}>{t("filter_language")}</label>
            <select
              value={filters.language ?? ""}
              onChange={(e) => handleFilterChange("language", e.target.value)}
              style={{ ...inputStyle, appearance: "auto" }}
            >
              <option value="">{t("filter_any")}</option>
              <option value="en">English</option>
              <option value="ru">Russian</option>
            </select>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <div>
              <label style={{ fontSize: 12, color: theme.textSecondary, display: "block", marginBottom: 4 }}>{t("filter_min_subscribers")}</label>
              <input
                type="text"
                inputMode="numeric"
                value={filters.min_subscribers ?? ""}
                onChange={(e) => handleFilterChange("min_subscribers", e.target.value)}
                placeholder="0"
                style={inputStyle}
              />
            </div>
            <div>
              <label style={{ fontSize: 12, color: theme.textSecondary, display: "block", marginBottom: 4 }}>{t("filter_min_avg_views")}</label>
              <input
                type="text"
                inputMode="numeric"
                value={filters.min_avg_views ?? ""}
                onChange={(e) => handleFilterChange("min_avg_views", e.target.value)}
                placeholder="0"
                style={inputStyle}
              />
            </div>
          </div>
          <div>
            <label style={{ fontSize: 12, color: theme.textSecondary, display: "block", marginBottom: 4 }}>{t("filter_min_growth")}</label>
            <input
              type="text"
              inputMode="decimal"
              value={filters.min_growth_pct_7d ?? ""}
              onChange={(e) => handleFilterChange("min_growth_pct_7d", e.target.value)}
              placeholder="0"
              style={inputStyle}
            />
          </div>
        </div>
      )}

      {/* Results */}
      {loading ? (
        <SkeletonList count={4} />
      ) : error ? (
        <ErrorMessage message={error} onRetry={load} />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={"\u{1F50D}"}
          title={t("empty_search")}
          description={t("empty_search_description")}
        />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {filtered.map((li) => (
            <div
              key={li.id}
              onClick={() => navigate(`/search/${li.id}`)}
              style={{
                backgroundColor: theme.bgSecondary,
                borderRadius: 14,
                padding: "14px 16px",
                cursor: "pointer",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <span style={{ fontWeight: 600, fontSize: 15, color: theme.text }}>{li.title}</span>
                <span style={{ fontWeight: 700, fontSize: 15, color: theme.accent }}>
                  {Number(li.price).toFixed(2)} {li.currency}
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ color: theme.textSecondary, fontSize: 13 }}>{li.channel.title}</span>
                  {li.channel.username && <span style={{ color: theme.textSecondary, fontSize: 12 }}>@{li.channel.username}</span>}
                </div>
                <span style={{ color: theme.textSecondary, fontSize: 12 }}>
                  {li.channel.subscribers.toLocaleString()} {t("channel_subscribers")}
                </span>
              </div>
              {li.description && (
                <p style={{ color: theme.textSecondary, fontSize: 13, marginTop: 6, lineHeight: 1.3 }}>
                  {li.description.length > 50 ? li.description.slice(0, 50) + "\u2026" : li.description}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default Search;
