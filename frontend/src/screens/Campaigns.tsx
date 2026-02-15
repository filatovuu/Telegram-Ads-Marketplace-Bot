import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useTheme } from "@/context/ThemeContext";
import { getMyCampaigns } from "@/api/campaigns";
import type { Campaign } from "@/api/types";
import { SkeletonList } from "@/ui/Skeleton";
import EmptyState from "@/ui/EmptyState";
import ErrorMessage from "@/ui/ErrorMessage";

function Campaigns() {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setCampaigns(await getMyCampaigns());
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return <SkeletonList count={3} />;
  }

  if (error) {
    return <ErrorMessage message={error} onRetry={load} />;
  }

  if (campaigns.length === 0) {
    return (
      <EmptyState
        icon={"\u{1F4CB}"}
        title={t("empty_campaigns")}
        description={t("empty_campaigns_description")}
        action={{ label: t("action_new_campaign"), onClick: () => navigate("/campaigns/new") }}
      />
    );
  }

  return (
    <div style={{ paddingTop: 8, paddingBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: theme.text, margin: 0 }}>{t("nav_campaigns")}</h2>
        <button
          onClick={() => navigate("/campaigns/new")}
          style={{
            backgroundColor: theme.accent,
            color: "#fff",
            border: "none",
            borderRadius: 10,
            padding: "8px 16px",
            fontSize: 14,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          {t("action_new_campaign")}
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {campaigns.map((c) => (
          <div
            key={c.id}
            onClick={() => navigate(`/campaigns/${c.id}`)}
            style={{
              backgroundColor: theme.bgSecondary,
              borderRadius: 14,
              padding: "14px 16px",
              cursor: "pointer",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <span style={{ fontWeight: 600, fontSize: 15, color: theme.text }}>{c.title}</span>
              <span style={{
                fontSize: 12,
                fontWeight: 600,
                padding: "2px 8px",
                borderRadius: 6,
                backgroundColor: c.is_active ? theme.accent + "22" : theme.danger + "22",
                color: c.is_active ? theme.accent : theme.danger,
              }}>
                {c.is_active ? t("listing_active") : t("listing_inactive")}
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ color: theme.textSecondary, fontSize: 13 }}>
                {Number(c.budget_min).toFixed(2)}–{Number(c.budget_max).toFixed(2)} TON
              </span>
              {c.category && (
                <span style={{ color: theme.textSecondary, fontSize: 12 }}>{c.category}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default Campaigns;
