import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useTheme } from "@/context/ThemeContext";
import { useBackButton } from "@/hooks/useBackButton";
import { getMarketListing, getPublicChannelStats } from "@/api/listings";
import { createDeal } from "@/api/deals";
import type { ChannelPublicStats, Listing } from "@/api/types";

function fmt(n: number | null | undefined): string {
  if (n == null) return "\u2014";
  return n.toLocaleString();
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return "\u2014";
  return `${(n * 100).toFixed(1)}%`;
}

function fmtRatio(n: number | null | undefined): string {
  if (n == null) return "\u2014";
  return n.toFixed(2);
}

function MetricTile({ value, label, color, bg }: { value: string; label: string; color: string; bg: string }) {
  return (
    <div style={{ backgroundColor: bg, borderRadius: 10, padding: "10px 12px" }}>
      <div style={{ fontSize: 17, fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: 11, color: "#8E8E93", marginTop: 2 }}>{label}</div>
    </div>
  );
}

function GrowthBadge({ value, label }: { value: number | null; label: string }) {
  if (value == null) return null;
  const positive = value >= 0;
  return (
    <span style={{
      display: "inline-block",
      fontSize: 12,
      fontWeight: 600,
      color: positive ? "#34c759" : "#ff3b30",
      backgroundColor: positive ? "#34c75915" : "#ff3b3015",
      borderRadius: 6,
      padding: "3px 8px",
    }}>
      {positive ? "+" : ""}{value}% {label}
    </span>
  );
}

function SearchDetail() {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  useBackButton(-1);
  const [listing, setListing] = useState<Listing | null>(null);
  const [stats, setStats] = useState<ChannelPublicStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const li = await getMarketListing(Number(id));
      setListing(li);
      try {
        setStats(await getPublicChannelStats(li.channel.id));
      } catch {
        /* no stats available */
      }
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const handleCreateDeal = async () => {
    if (!listing) return;
    setCreating(true);
    setError(null);
    try {
      const deal = await createDeal({
        listing_id: listing.id,
        price: listing.price,
        currency: listing.currency,
      });
      navigate(`/deals/${deal.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error"));
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return <p style={{ textAlign: "center", paddingTop: 40, color: theme.textSecondary }}>{t("loading")}</p>;
  }

  if (!listing) {
    return <p style={{ textAlign: "center", paddingTop: 40, color: theme.textSecondary }}>Listing not found</p>;
  }

  const ch = listing.channel;

  return (
    <div style={{ paddingTop: 8, paddingBottom: 16 }}>

      <h2 style={{ fontSize: 20, fontWeight: 700, color: theme.text, marginBottom: 4 }}>
        {listing.title}
      </h2>

      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 16 }}>
        <span style={{ color: theme.textSecondary, fontSize: 14 }}>{ch.title}</span>
        {ch.username && <span style={{ color: theme.textSecondary, fontSize: 13 }}>@{ch.username}</span>}
      </div>

      {/* Channel analytics */}
      <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: 16, marginBottom: 16 }}>
        <h3 style={{ fontSize: 16, fontWeight: 700, color: theme.text, margin: "0 0 14px" }}>{t("stats_title")}</h3>

        {stats ? (
          <>
            {/* Subscribers hero */}
            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 28, fontWeight: 700, color: theme.text, lineHeight: 1 }}>
                {stats.subscribers.toLocaleString()}
              </div>
              <div style={{ fontSize: 12, color: theme.textSecondary, marginTop: 4 }}>{t("stats_subscribers_label")}</div>
            </div>

            {/* Growth badges */}
            <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
              <GrowthBadge value={stats.subscribers_growth_pct_7d} label={t("stats_7d")} />
              <GrowthBadge value={stats.subscribers_growth_pct_30d} label={t("stats_30d")} />
            </div>

            {/* Views */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 10 }}>
              <MetricTile value={fmt(stats.avg_views)} label={t("stats_avg_views")} color={theme.text} bg={theme.bgTertiary} />
              <MetricTile value={fmt(stats.median_views)} label={t("stats_median")} color={theme.text} bg={theme.bgTertiary} />
              <MetricTile value={stats.reach_pct != null ? `${stats.reach_pct}%` : "\u2014"} label={t("stats_reach")} color={theme.text} bg={theme.bgTertiary} />
            </div>

            {/* Engagement */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 10 }}>
              <MetricTile value={fmtPct(stats.reactions_per_views)} label={t("stats_reactions")} color={theme.text} bg={theme.bgTertiary} />
              <MetricTile value={fmtPct(stats.forwards_per_views)} label={t("stats_forwards")} color={theme.text} bg={theme.bgTertiary} />
              <MetricTile value={fmtRatio(stats.velocity_1h_ratio)} label={t("stats_velocity")} color={theme.text} bg={theme.bgTertiary} />
            </div>

            {/* Frequency + reliability */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
              <MetricTile value={stats.posts_per_week != null ? stats.posts_per_week.toFixed(1) : "\u2014"} label={t("stats_frequency")} color={theme.text} bg={theme.bgTertiary} />
              <MetricTile value={stats.posts_per_day_7d != null ? stats.posts_per_day_7d.toFixed(1) : "\u2014"} label={t("stats_per_day_7d")} color={theme.text} bg={theme.bgTertiary} />
              <MetricTile value={fmtPct(stats.edit_rate)} label={t("stats_edit_rate")} color={theme.text} bg={theme.bgTertiary} />
            </div>
          </>
        ) : (
          /* Fallback: basic channel info when no stats snapshot exists */
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <div>
              <span style={{ fontSize: 12, color: theme.textSecondary }}>{t("channel_subscribers")}</span>
              <p style={{ fontWeight: 600, fontSize: 15, color: theme.text, margin: "4px 0 0" }}>{ch.subscribers.toLocaleString()}</p>
            </div>
            <div>
              <span style={{ fontSize: 12, color: theme.textSecondary }}>{t("channel_avg_views")}</span>
              <p style={{ fontWeight: 600, fontSize: 15, color: theme.text, margin: "4px 0 0" }}>{ch.avg_views.toLocaleString()}</p>
            </div>
          </div>
        )}
      </div>

      {/* Listing details */}
      <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: "14px 16px", marginBottom: 16 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          {ch.language && (
            <div>
              <span style={{ fontSize: 12, color: theme.textSecondary }}>{t("channel_language")}</span>
              <p style={{ fontWeight: 600, fontSize: 15, color: theme.text, margin: "4px 0 0" }}>{ch.language.toUpperCase()}</p>
            </div>
          )}
          <div>
            <span style={{ fontSize: 12, color: theme.textSecondary }}>{t("listing_format")}</span>
            <p style={{ fontWeight: 600, fontSize: 15, color: theme.text, margin: "4px 0 0" }}>{listing.format}</p>
          </div>
        </div>
      </div>

      {/* Description */}
      {listing.description && (
        <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: "14px 16px", marginBottom: 16 }}>
          <span style={{ fontSize: 12, color: theme.textSecondary }}>{t("listing_description")}</span>
          <p style={{ color: theme.text, fontSize: 14, margin: "6px 0 0", lineHeight: 1.4 }}>{listing.description}</p>
        </div>
      )}

      {/* Price */}
      <div style={{
        backgroundColor: theme.bgSecondary,
        borderRadius: 14,
        padding: "14px 16px",
        marginBottom: 20,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}>
        <span style={{ fontSize: 14, color: theme.textSecondary }}>{t("listing_price")}</span>
        <span style={{ fontWeight: 700, fontSize: 18, color: theme.accent }}>
          {Number(listing.price).toFixed(2)} {listing.currency}
        </span>
      </div>

      {error && <p style={{ color: theme.danger, fontSize: 13, marginBottom: 12 }}>{error}</p>}

      <button
        onClick={handleCreateDeal}
        disabled={creating}
        style={{
          width: "100%",
          padding: "14px",
          fontSize: 16,
          fontWeight: 600,
          borderRadius: 12,
          border: "none",
          backgroundColor: theme.accent,
          color: "#fff",
          cursor: "pointer",
          opacity: creating ? 0.5 : 1,
        }}
      >
        {creating ? t("loading") : t("search_create_deal")}
      </button>
    </div>
  );
}

export default SearchDetail;
