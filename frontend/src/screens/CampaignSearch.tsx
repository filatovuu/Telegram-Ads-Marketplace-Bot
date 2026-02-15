import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useTheme } from "@/context/ThemeContext";
import { searchCampaigns } from "@/api/campaigns";
import type { CampaignPublic, CampaignFilter } from "@/api/types";
import { SkeletonList } from "@/ui/Skeleton";
import EmptyState from "@/ui/EmptyState";
import ErrorMessage from "@/ui/ErrorMessage";

const MAX_FILTER_VALUE = 999_999_999;

function CampaignSearch() {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();
  const [campaigns, setCampaigns] = useState<CampaignPublic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<CampaignFilter>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setCampaigns(await searchCampaigns(filters));
    } catch (err) {
      setError(err instanceof Error ? err.message : typeof err === "string" ? err : t("error"));
    } finally {
      setLoading(false);
    }
  }, [filters, t]);

  useEffect(() => { load(); }, [load]);

  const filtered = query.trim()
    ? campaigns.filter((c) => {
        const q = query.toLowerCase();
        return (
          c.title.toLowerCase().includes(q) ||
          (c.brief?.toLowerCase().includes(q) ?? false) ||
          (c.category?.toLowerCase().includes(q) ?? false)
        );
      })
    : campaigns;

  const handleFilterChange = (key: keyof CampaignFilter, value: string) => {
    if (value === "") {
      setFilters((prev) => ({ ...prev, [key]: undefined }));
      return;
    }
    if (key === "category" || key === "target_language") {
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
          placeholder={t("campaign_search_placeholder")}
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
              <label style={{ fontSize: 12, color: theme.textSecondary, display: "block", marginBottom: 4 }}>{t("campaign_filter_min_budget")}</label>
              <input
                type="text"
                inputMode="decimal"
                value={filters.min_budget ?? ""}
                onChange={(e) => handleFilterChange("min_budget", e.target.value)}
                placeholder="0"
                style={inputStyle}
              />
            </div>
            <div>
              <label style={{ fontSize: 12, color: theme.textSecondary, display: "block", marginBottom: 4 }}>{t("campaign_filter_max_budget")}</label>
              <input
                type="text"
                inputMode="decimal"
                value={filters.max_budget ?? ""}
                onChange={(e) => handleFilterChange("max_budget", e.target.value)}
                placeholder={t("filter_any")}
                style={inputStyle}
              />
            </div>
          </div>
          <div>
            <label style={{ fontSize: 12, color: theme.textSecondary, display: "block", marginBottom: 4 }}>{t("campaign_filter_category")}</label>
            <select
              value={filters.category ?? ""}
              onChange={(e) => handleFilterChange("category", e.target.value)}
              style={{ ...inputStyle, appearance: "auto" }}
            >
              <option value="">{t("filter_any")}</option>
              <option value="crypto">Crypto</option>
              <option value="finance">Finance</option>
              <option value="tech">Tech</option>
              <option value="lifestyle">Lifestyle</option>
              <option value="news">News</option>
              <option value="education">Education</option>
              <option value="entertainment">Entertainment</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div>
            <label style={{ fontSize: 12, color: theme.textSecondary, display: "block", marginBottom: 4 }}>{t("campaign_filter_language")}</label>
            <select
              value={filters.target_language ?? ""}
              onChange={(e) => handleFilterChange("target_language", e.target.value)}
              style={{ ...inputStyle, appearance: "auto" }}
            >
              <option value="">{t("filter_any")}</option>
              <option value="en">English</option>
              <option value="ru">Russian</option>
            </select>
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
          icon={"\u{1F4E2}"}
          title={t("campaign_search_empty")}
          description={t("campaign_search_empty_description")}
        />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {filtered.map((c) => (
            <div
              key={c.id}
              onClick={() => navigate(`/campaign-search/${c.id}`)}
              style={{
                backgroundColor: theme.bgSecondary,
                borderRadius: 14,
                padding: "14px 16px",
                cursor: "pointer",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <span style={{ fontWeight: 600, fontSize: 15, color: theme.text }}>{c.title}</span>
                <span style={{ fontWeight: 700, fontSize: 14, color: theme.accent }}>
                  {Number(c.budget_min).toFixed(1)}&ndash;{Number(c.budget_max).toFixed(1)} TON
                </span>
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 6 }}>
                {c.category && (
                  <span style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: theme.accent,
                    backgroundColor: `${theme.accent}15`,
                    borderRadius: 6,
                    padding: "2px 8px",
                  }}>
                    {c.category}
                  </span>
                )}
                {c.target_language && (
                  <span style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: theme.textSecondary,
                    backgroundColor: theme.bgTertiary,
                    borderRadius: 6,
                    padding: "2px 8px",
                  }}>
                    {c.target_language.toUpperCase()}
                  </span>
                )}
              </div>
              {c.brief && (
                <p style={{ color: theme.textSecondary, fontSize: 13, marginTop: 2, lineHeight: 1.3 }}>
                  {c.brief.length > 80 ? c.brief.slice(0, 80) + "\u2026" : c.brief}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default CampaignSearch;
