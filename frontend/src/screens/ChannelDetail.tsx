import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useTheme } from "@/context/ThemeContext";
import { useBackButton } from "@/hooks/useBackButton";
import {
  getChannel,
  updateChannel,
  getTeamMembers,
  addTeamMember,
  updateTeamMember,
  removeTeamMember,
  getChannelStats,
  getChannelStatsHistory,
  refreshChannelStatsSnapshot,
  getChannelDeletePreview,
  deleteChannel,
} from "@/api/channels";
import type { Channel, ChannelStats, ChannelStatsHistory, ChannelTeamMember, ChannelTeamRole } from "@/api/types";
import SubscribersChart from "@/ui/SubscribersChart";
import { SkeletonDetail } from "@/ui/Skeleton";
import ErrorMessage from "@/ui/ErrorMessage";

/** Reusable metric tile */
function MetricTile({
  value,
  label,
  color,
  bg,
}: {
  value: string;
  label: string;
  color: string;
  bg: string;
}) {
  return (
    <div style={{ backgroundColor: bg, borderRadius: 10, padding: "10px 12px" }}>
      <div style={{ fontSize: 17, fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: 11, color: "#8E8E93", marginTop: 2 }}>{label}</div>
    </div>
  );
}

/** Growth badge */
function GrowthBadge({ value, label }: { value: number | null; label: string }) {
  if (value == null) return null;
  const positive = value >= 0;
  return (
    <span
      style={{
        display: "inline-block",
        fontSize: 12,
        fontWeight: 600,
        color: positive ? "#34c759" : "#ff3b30",
        backgroundColor: positive ? "#34c75915" : "#ff3b3015",
        borderRadius: 6,
        padding: "3px 8px",
      }}
    >
      {positive ? "+" : ""}
      {value}% {label}
    </span>
  );
}

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

function ChannelDetail() {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  useBackButton(-1);

  const [channel, setChannel] = useState<Channel | null>(null);
  const [team, setTeam] = useState<ChannelTeamMember[]>([]);
  const [stats, setStats] = useState<ChannelStats | null>(null);
  const [history, setHistory] = useState<ChannelStatsHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  // Team add form
  const [showAddTeam, setShowAddTeam] = useState(false);
  const [teamUsername, setTeamUsername] = useState("");
  const [teamRole, setTeamRole] = useState<ChannelTeamRole>("manager");
  const [teamRights, setTeamRights] = useState({ can_accept_deals: false, can_post: false, can_payout: false });
  const [teamError, setTeamError] = useState<string | null>(null);

  // Team member editing
  const [editingMemberId, setEditingMemberId] = useState<number | null>(null);
  const [editMemberRole, setEditMemberRole] = useState<ChannelTeamRole>("manager");
  const [editMemberRights, setEditMemberRights] = useState({ can_accept_deals: false, can_post: false, can_payout: false });

  // Language picker
  const [showLangPicker, setShowLangPicker] = useState(false);

  // Delete flow
  const [deleting, setDeleting] = useState(false);

  const channelId = Number(id);

  const load = useCallback(async () => {
    try {
      const [ch, members] = await Promise.all([
        getChannel(channelId),
        getTeamMembers(channelId),
      ]);
      setChannel(ch);
      setTeam(members);
      try {
        const [s, h] = await Promise.all([
          getChannelStats(channelId),
          getChannelStatsHistory(channelId),
        ]);
        setStats(s);
        setHistory(h);
      } catch {
        /* no stats yet */
      }
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [channelId]);

  useEffect(() => { load(); }, [load]);

  /** Single unified refresh — collects subscribers, views, metadata, computes everything */
  const handleRefresh = async () => {
    setRefreshing(true);
    setRefreshError(null);
    try {
      const s = await refreshChannelStatsSnapshot(channelId);
      setStats(s);
      // Refresh channel data and history in parallel
      const [ch, h] = await Promise.all([
        getChannel(channelId),
        getChannelStatsHistory(channelId),
      ]);
      setChannel(ch);
      setHistory(h);
    } catch (err) {
      setRefreshError(err instanceof Error ? err.message : t("stats_rate_limited"));
    } finally {
      setRefreshing(false);
    }
  };

  const handleAddTeam = async () => {
    if (!teamUsername.trim()) return;
    setTeamError(null);
    try {
      await addTeamMember(channelId, { username: teamUsername.trim(), role: teamRole, ...teamRights });
      setTeamUsername("");
      setTeamRole("manager");
      setTeamRights({ can_accept_deals: false, can_post: false, can_payout: false });
      setShowAddTeam(false);
      const members = await getTeamMembers(channelId);
      setTeam(members);
    } catch (err) {
      setTeamError(err instanceof Error ? err.message : t("error"));
    }
  };

  const handleEditMember = (m: ChannelTeamMember) => {
    setEditingMemberId(m.id);
    setEditMemberRole(m.role);
    setEditMemberRights({ can_accept_deals: m.can_accept_deals, can_post: m.can_post, can_payout: m.can_payout });
  };

  const handleSaveMember = async (memberId: number) => {
    const member = team.find((m) => m.id === memberId);
    const canPayout = member?.is_telegram_admin ? editMemberRights.can_payout : false;
    try {
      await updateTeamMember(channelId, memberId, {
        role: editMemberRole,
        can_accept_deals: editMemberRights.can_accept_deals,
        can_post: editMemberRights.can_post,
        can_payout: canPayout,
      });
      setEditingMemberId(null);
      const members = await getTeamMembers(channelId);
      setTeam(members);
    } catch {
      /* ignore */
    }
  };

  const handleRemoveTeam = async (memberId: number) => {
    try {
      await removeTeamMember(channelId, memberId);
      setTeam((prev) => prev.filter((m) => m.id !== memberId));
    } catch {
      /* ignore */
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      const preview = await getChannelDeletePreview(channelId);
      const count = preview.active_deals_count;

      let message = t("channel_delete_confirm");
      if (count > 0) {
        message += "\n\n" + t("channel_delete_active_deals", { count });
      }

      if (!window.confirm(message)) {
        setDeleting(false);
        return;
      }

      await deleteChannel(channelId);
      window.alert(t("channel_delete_bot_hint"));
      navigate("/channels");
    } catch {
      setDeleting(false);
    }
  };

  if (loading) {
    return <SkeletonDetail />;
  }

  if (!channel) {
    return <ErrorMessage message={t("error")} onRetry={load} />;
  }

  const isChannelOwner = !channel.user_role || channel.user_role === "owner";

  return (
    <div style={{ paddingTop: 8, paddingBottom: 16 }}>
      {/* Bot admin warning */}
      {!channel.bot_is_admin && (
        <div style={{
          backgroundColor: "#ff3b3015",
          border: "1px solid #ff3b3040",
          borderRadius: 12,
          padding: "12px 14px",
          marginBottom: 12,
        }}>
          <div style={{ fontWeight: 600, fontSize: 14, color: theme.danger, marginBottom: 4 }}>
            {t("channel_bot_not_admin_title")}
          </div>
          <p style={{ color: theme.text, fontSize: 13, lineHeight: 1.4, margin: 0 }}>
            {t("channel_bot_not_admin_hint")}
          </p>
        </div>
      )}

      {/* Channel header */}
      <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: 16, marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: theme.text, margin: 0 }}>{channel.title}</h2>
        </div>
        {channel.username && (
          <p style={{ color: theme.textSecondary, fontSize: 14, margin: "4px 0 8px" }}>@{channel.username}</p>
        )}
        {channel.description && (
          <p style={{ color: theme.text, fontSize: 14, lineHeight: 1.4, margin: 0 }}>{channel.description}</p>
        )}
        <div style={{ marginTop: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ color: theme.textSecondary, fontSize: 13 }}>
              {t("channel_language")}:
            </span>
            <span style={{ fontSize: 13, fontWeight: 600, color: theme.text }}>
              {{ en: "English", ru: "Русский" }[channel.language ?? "en"] ?? channel.language}
            </span>
            {!channel.language_manual && (
              <span style={{ fontSize: 11, color: theme.textSecondary }}>({t("channel_language_auto")})</span>
            )}
            {isChannelOwner && (
              <button
                onClick={() => setShowLangPicker(!showLangPicker)}
                style={{ background: "none", border: "none", color: theme.accent, fontSize: 13, fontWeight: 600, cursor: "pointer", padding: 0 }}
              >
                {t("channel_language_change")}
              </button>
            )}
          </div>

          {showLangPicker && (
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
              {[
                { code: "en", label: "English" },
                { code: "ru", label: "Русский" },
              ].map((lang) => (
                <button
                  key={lang.code}
                  onClick={async () => {
                    const updated = await updateChannel(channelId, { language: lang.code, language_manual: true });
                    setChannel(updated);
                    setShowLangPicker(false);
                  }}
                  style={{
                    padding: "6px 14px",
                    borderRadius: 8,
                    border: channel.language === lang.code ? `2px solid ${theme.accent}` : `1px solid ${theme.border}`,
                    backgroundColor: channel.language === lang.code ? `${theme.accent}18` : "transparent",
                    color: channel.language === lang.code ? theme.accent : theme.text,
                    fontWeight: 600,
                    fontSize: 13,
                    cursor: "pointer",
                  }}
                >
                  {lang.label}
                </button>
              ))}
              {channel.language_manual && (
                <button
                  onClick={async () => {
                    const updated = await updateChannel(channelId, { language_manual: false });
                    setChannel(updated);
                    setShowLangPicker(false);
                  }}
                  style={{
                    padding: "6px 14px",
                    borderRadius: 8,
                    border: "none",
                    backgroundColor: "#FF3B3018",
                    color: "#FF3B30",
                    fontWeight: 600,
                    fontSize: 13,
                    cursor: "pointer",
                  }}
                >
                  {t("channel_language_reset_auto")}
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Analytics dashboard */}
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

            {/* Chart */}
            {history && history.data_points.length >= 2 && (
              <div style={{ marginBottom: 14 }}>
                <SubscribersChart data={history.data_points} width={280} height={100} color={theme.accent} />
              </div>
            )}

            {/* Views metrics grid */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 10 }}>
              <MetricTile value={fmt(stats.avg_views)} label={t("stats_avg_views")} color={theme.text} bg={theme.bgTertiary} />
              <MetricTile value={fmt(stats.median_views)} label={t("stats_median")} color={theme.text} bg={theme.bgTertiary} />
              <MetricTile value={stats.reach_pct != null ? `${stats.reach_pct}%` : "\u2014"} label={t("stats_reach")} color={theme.text} bg={theme.bgTertiary} />
            </div>

            {/* Avg views breakdown */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 10 }}>
              <MetricTile value={fmt(stats.avg_views_10)} label={t("stats_last_10")} color={theme.text} bg={theme.bgTertiary} />
              <MetricTile value={fmt(stats.avg_views_30)} label={t("stats_last_30")} color={theme.text} bg={theme.bgTertiary} />
              <MetricTile value={fmt(stats.avg_views_50)} label={t("stats_last_50")} color={theme.text} bg={theme.bgTertiary} />
            </div>

            {/* Engagement row */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 10 }}>
              <MetricTile value={fmtPct(stats.reactions_per_views)} label={t("stats_reactions")} color={theme.text} bg={theme.bgTertiary} />
              <MetricTile value={fmtPct(stats.forwards_per_views)} label={t("stats_forwards")} color={theme.text} bg={theme.bgTertiary} />
              <MetricTile value={fmtRatio(stats.velocity_1h_ratio)} label={t("stats_velocity")} color={theme.text} bg={theme.bgTertiary} />
            </div>

            {/* Enhanced frequency row */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 8, marginBottom: 10 }}>
              <MetricTile value={fmt(stats.posts_7d)} label={t("stats_posts_7d")} color={theme.text} bg={theme.bgTertiary} />
              <MetricTile value={fmt(stats.posts_30d)} label={t("stats_posts_30d")} color={theme.text} bg={theme.bgTertiary} />
              <MetricTile value={stats.posts_per_day_7d != null ? stats.posts_per_day_7d.toFixed(1) : "\u2014"} label={t("stats_per_day_7d")} color={theme.text} bg={theme.bgTertiary} />
              <MetricTile value={stats.posts_per_day_30d != null ? stats.posts_per_day_30d.toFixed(1) : "\u2014"} label={t("stats_per_day_30d")} color={theme.text} bg={theme.bgTertiary} />
            </div>

            {/* Edit rate + tracked */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 4 }}>
              <MetricTile value={fmtPct(stats.edit_rate)} label={t("stats_edit_rate")} color={theme.text} bg={theme.bgTertiary} />
              <MetricTile
                value={String(stats.posts_tracked)}
                label={t("stats_tracked")}
                color={theme.text}
                bg={theme.bgTertiary}
              />
            </div>
          </>
        ) : (
          <p style={{ color: theme.textSecondary, fontSize: 13 }}>{t("stats_no_data")}</p>
        )}

        {refreshError && <p style={{ color: theme.danger, fontSize: 13, marginTop: 8 }}>{refreshError}</p>}

        {/* Single Refresh Stats button */}
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          style={{
            width: "100%",
            marginTop: 12,
            padding: "12px",
            fontSize: 15,
            fontWeight: 600,
            borderRadius: 10,
            border: "none",
            backgroundColor: theme.accent,
            color: "#fff",
            cursor: refreshing ? "default" : "pointer",
            opacity: refreshing ? 0.6 : 1,
          }}
        >
          {refreshing ? t("loading") : t("stats_refresh")}
        </button>
      </div>

      {/* Team */}
      <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: 16, marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: theme.text, margin: 0 }}>{t("team_title")}</h3>
          {isChannelOwner && (
            <button
              onClick={() => setShowAddTeam(!showAddTeam)}
              style={{ background: "none", border: "none", color: theme.accent, fontSize: 14, fontWeight: 600, cursor: "pointer", padding: 0 }}
            >
              {showAddTeam ? t("team_cancel") : t("team_add")}
            </button>
          )}
        </div>

        {showAddTeam && isChannelOwner && (
          <div style={{ marginBottom: 12, padding: 12, backgroundColor: theme.bgTertiary, borderRadius: 10 }}>
            <input
              value={teamUsername}
              onChange={(e) => setTeamUsername(e.target.value)}
              placeholder="@username"
              style={{
                width: "100%",
                padding: "10px 12px",
                fontSize: 14,
                borderRadius: 8,
                border: `1px solid ${theme.border}`,
                backgroundColor: theme.bgSecondary,
                color: theme.text,
                outline: "none",
                marginBottom: 8,
                boxSizing: "border-box",
              }}
            />
            {/* Role selector */}
            <div style={{ marginBottom: 8 }}>
              <label style={{ fontSize: 12, color: theme.textSecondary, display: "block", marginBottom: 4 }}>{t("team_role_select")}</label>
              <div style={{ display: "flex", gap: 8 }}>
                {(["manager", "viewer"] as const).map((r) => (
                  <button
                    key={r}
                    onClick={() => {
                      setTeamRole(r);
                      if (r === "viewer") setTeamRights({ can_accept_deals: false, can_post: false, can_payout: false });
                    }}
                    style={{
                      flex: 1,
                      padding: "8px 12px",
                      borderRadius: 8,
                      border: teamRole === r ? `2px solid ${theme.accent}` : `1px solid ${theme.border}`,
                      backgroundColor: teamRole === r ? `${theme.accent}18` : "transparent",
                      color: teamRole === r ? theme.accent : theme.text,
                      fontWeight: 600,
                      fontSize: 13,
                      cursor: "pointer",
                    }}
                  >
                    {t(`team_role_${r}`)}
                  </button>
                ))}
              </div>
            </div>
            {/* Permission checkboxes (disabled for viewer) */}
            <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 8 }}>
              {(["can_accept_deals", "can_post", "can_payout"] as const).map((right) => (
                <label key={right} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: teamRole === "viewer" ? theme.textSecondary : theme.text }}>
                  <input
                    type="checkbox"
                    checked={teamRights[right]}
                    disabled={teamRole === "viewer"}
                    onChange={(e) => setTeamRights((prev) => ({ ...prev, [right]: e.target.checked }))}
                  />
                  {t(`team_right_${right}`)}
                  {right === "can_payout" && (
                    <span style={{ fontSize: 11, color: theme.textSecondary }}>({t("team_payout_admin_required")})</span>
                  )}
                </label>
              ))}
            </div>
            {teamError && <p style={{ color: theme.danger, fontSize: 13, marginBottom: 8 }}>{teamError}</p>}
            <button
              onClick={handleAddTeam}
              style={{
                width: "100%",
                padding: "10px",
                fontSize: 14,
                fontWeight: 600,
                borderRadius: 8,
                border: "none",
                backgroundColor: theme.accent,
                color: "#fff",
                cursor: "pointer",
              }}
            >
              {t("team_add")}
            </button>
          </div>
        )}

        {team.length === 0 ? (
          <p style={{ color: theme.textSecondary, fontSize: 13 }}>{t("team_empty")}</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {team.map((m) => (
              <div key={m.id} style={{ backgroundColor: theme.bgTertiary, borderRadius: 10, padding: "10px 12px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                    <span style={{ fontWeight: 600, fontSize: 14, color: theme.text }}>
                      {m.user.first_name || m.user.username || `ID ${m.user_id}`}
                    </span>
                    <span style={{
                      fontSize: 11,
                      fontWeight: 600,
                      padding: "2px 6px",
                      borderRadius: 4,
                      backgroundColor: m.role === "manager" ? "#007AFF18" : "#8E8E9318",
                      color: m.role === "manager" ? "#007AFF" : "#8E8E93",
                    }}>
                      {t(`team_role_${m.role}`)}
                    </span>
                    {m.is_telegram_admin != null && (
                      <span style={{
                        fontSize: 11,
                        fontWeight: 600,
                        padding: "2px 6px",
                        borderRadius: 4,
                        backgroundColor: m.is_telegram_admin ? "#34C75918" : "#FF3B3018",
                        color: m.is_telegram_admin ? "#34C759" : "#FF3B30",
                      }}>
                        {m.is_telegram_admin ? t("team_tg_admin") : t("team_tg_not_admin")}
                      </span>
                    )}
                  </div>
                  {isChannelOwner && (
                    <div style={{ display: "flex", gap: 8 }}>
                      <button
                        onClick={() => editingMemberId === m.id ? setEditingMemberId(null) : handleEditMember(m)}
                        style={{ background: "none", border: "none", color: theme.accent, fontSize: 13, cursor: "pointer", padding: 0 }}
                      >
                        {editingMemberId === m.id ? t("team_cancel") : t("team_edit")}
                      </button>
                      <button
                        onClick={() => handleRemoveTeam(m.id)}
                        style={{ background: "none", border: "none", color: theme.danger, fontSize: 13, cursor: "pointer", padding: 0 }}
                      >
                        {t("team_remove")}
                      </button>
                    </div>
                  )}
                </div>

                {/* Inline edit form */}
                {editingMemberId === m.id && isChannelOwner && (
                  <div style={{ marginTop: 10, paddingTop: 10, borderTop: `1px solid ${theme.border}` }}>
                    <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                      {(["manager", "viewer"] as const).map((r) => (
                        <button
                          key={r}
                          onClick={() => {
                            setEditMemberRole(r);
                            if (r === "viewer") setEditMemberRights({ can_accept_deals: false, can_post: false, can_payout: false });
                          }}
                          style={{
                            flex: 1,
                            padding: "6px 10px",
                            borderRadius: 6,
                            border: editMemberRole === r ? `2px solid ${theme.accent}` : `1px solid ${theme.border}`,
                            backgroundColor: editMemberRole === r ? `${theme.accent}18` : "transparent",
                            color: editMemberRole === r ? theme.accent : theme.text,
                            fontWeight: 600,
                            fontSize: 12,
                            cursor: "pointer",
                          }}
                        >
                          {t(`team_role_${r}`)}
                        </button>
                      ))}
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 8 }}>
                      {(["can_accept_deals", "can_post", "can_payout"] as const).map((right) => {
                        const payoutBlocked = right === "can_payout" && !m.is_telegram_admin;
                        const disabled = editMemberRole === "viewer" || payoutBlocked;
                        return (
                          <label key={right} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: disabled ? theme.textSecondary : theme.text }}>
                            <input
                              type="checkbox"
                              checked={payoutBlocked ? false : editMemberRights[right]}
                              disabled={disabled}
                              onChange={(e) => setEditMemberRights((prev) => ({ ...prev, [right]: e.target.checked }))}
                            />
                            {t(`team_right_${right}`)}
                            {payoutBlocked && (
                              <span style={{ fontSize: 10, color: theme.danger }}>({t("team_payout_admin_required")})</span>
                            )}
                          </label>
                        );
                      })}
                    </div>
                    <button
                      onClick={() => handleSaveMember(m.id)}
                      style={{
                        width: "100%",
                        padding: "8px",
                        fontSize: 13,
                        fontWeight: 600,
                        borderRadius: 6,
                        border: "none",
                        backgroundColor: theme.accent,
                        color: "#fff",
                        cursor: "pointer",
                      }}
                    >
                      {t("team_save")}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create listing (owner only) */}
      {isChannelOwner && (
        <button
          onClick={() => navigate(`/listings/new?channel=${channelId}`)}
          style={{
            width: "100%",
            padding: "14px",
            fontSize: 15,
            fontWeight: 600,
            borderRadius: 12,
            border: "none",
            backgroundColor: theme.accent,
            color: "#fff",
            cursor: "pointer",
          }}
        >
          {t("action_create_listing")}
        </button>
      )}

      {/* Delete channel (owner only) */}
      {isChannelOwner && (
        <button
          onClick={handleDelete}
          disabled={deleting}
          style={{
            width: "100%",
            marginTop: 12,
            padding: "14px",
            fontSize: 15,
            fontWeight: 600,
            borderRadius: 12,
            border: "none",
            backgroundColor: theme.danger,
            color: "#fff",
            cursor: deleting ? "default" : "pointer",
            opacity: deleting ? 0.6 : 1,
          }}
        >
          {deleting ? t("loading") : t("channel_delete")}
        </button>
      )}
    </div>
  );
}

export default ChannelDetail;
