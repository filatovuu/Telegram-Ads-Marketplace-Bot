import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useTheme } from "@/context/ThemeContext";
import { getMyListings } from "@/api/listings";
import type { Listing } from "@/api/types";
import { SkeletonList } from "@/ui/Skeleton";
import EmptyState from "@/ui/EmptyState";
import ErrorMessage from "@/ui/ErrorMessage";

function Listings() {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setListings(await getMyListings());
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

  if (listings.length === 0) {
    return (
      <EmptyState
        icon={"\u{1F4B0}"}
        title={t("empty_listings")}
        description={t("empty_listings_description")}
        action={{ label: t("action_create_listing"), onClick: () => navigate("/listings/new") }}
      />
    );
  }

  return (
    <div style={{ paddingTop: 8, paddingBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: theme.text }}>{t("nav_listings")}</h2>
        <button
          onClick={() => navigate("/listings/new")}
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
          + {t("action_create_listing")}
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {listings.map((li) => (
          <div
            key={li.id}
            onClick={() => navigate(`/listings/${li.id}/edit`)}
            style={{
              backgroundColor: theme.bgSecondary,
              borderRadius: 14,
              padding: "14px 16px",
              cursor: "pointer",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <span style={{ fontWeight: 600, fontSize: 15, color: theme.text }}>{li.title}</span>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  padding: "2px 8px",
                  borderRadius: 6,
                  backgroundColor: li.is_active ? "#34c75920" : "#ff3b3020",
                  color: li.is_active ? "#34c759" : "#ff3b30",
                }}
              >
                {li.is_active ? t("listing_active") : t("listing_inactive")}
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ color: theme.textSecondary, fontSize: 13 }}>{li.channel.title}</span>
              <span style={{ fontWeight: 700, fontSize: 15, color: theme.accent }}>
                {Number(li.price).toFixed(2)} {li.currency}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default Listings;
