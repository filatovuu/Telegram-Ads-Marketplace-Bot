import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useTheme } from "@/context/ThemeContext";
import { getMyChannels } from "@/api/channels";
import type { Channel } from "@/api/types";
import { SkeletonList } from "@/ui/Skeleton";
import EmptyState from "@/ui/EmptyState";
import ErrorMessage from "@/ui/ErrorMessage";

function Channels() {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setChannels(await getMyChannels());
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

  if (channels.length === 0) {
    return (
      <EmptyState
        icon={"\u{1F4E2}"}
        title={t("empty_channels")}
        description={t("empty_channels_description")}
        action={{ label: t("action_add_channel"), onClick: () => navigate("/channels/add") }}
      />
    );
  }

  return (
    <div style={{ paddingTop: 8, paddingBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: theme.text }}>{t("nav_channels")}</h2>
        <button
          onClick={() => navigate("/channels/add")}
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
          + {t("action_add_channel")}
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {channels.map((ch) => (
          <div
            key={ch.id}
            onClick={() => navigate(`/channels/${ch.id}`)}
            style={{
              backgroundColor: theme.bgSecondary,
              borderRadius: 14,
              padding: "14px 16px",
              cursor: "pointer",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                <span style={{ fontWeight: 600, fontSize: 15, color: theme.text }}>{ch.title}</span>
                {ch.is_verified && ch.bot_is_admin && <span style={{ fontSize: 12 }}>{"\u2705"}</span>}
                {!ch.bot_is_admin && <span style={{ fontSize: 12 }}>{"\u26A0\uFE0F"}</span>}
                {ch.user_role && ch.user_role !== "owner" && (
                  <span style={{
                    fontSize: 11,
                    fontWeight: 600,
                    padding: "2px 8px",
                    borderRadius: 6,
                    backgroundColor: ch.user_role === "manager" ? "#007AFF18" : "#8E8E9318",
                    color: ch.user_role === "manager" ? "#007AFF" : "#8E8E93",
                  }}>
                    {t(`team_role_${ch.user_role}`)}
                  </span>
                )}
              </div>
              {ch.username && (
                <span style={{ color: theme.textSecondary, fontSize: 13 }}>@{ch.username}</span>
              )}
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: theme.text }}>
                {ch.subscribers.toLocaleString()}
              </div>
              <div style={{ fontSize: 12, color: theme.textSecondary }}>{t("channel_subscribers")}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default Channels;
