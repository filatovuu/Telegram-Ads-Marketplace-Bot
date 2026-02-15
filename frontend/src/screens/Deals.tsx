import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useTheme } from "@/context/ThemeContext";
import { useAuth } from "@/context/AuthContext";
import { getMyDeals, getOwnerDeals } from "@/api/deals";
import type { Deal } from "@/api/types";
import { SkeletonList } from "@/ui/Skeleton";
import EmptyState from "@/ui/EmptyState";
import ErrorMessage from "@/ui/ErrorMessage";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "#8E8E93",
  NEGOTIATION: "#FF9500",
  OWNER_ACCEPTED: "#34C759",
  AWAITING_ESCROW_PAYMENT: "#FF9500",
  ESCROW_FUNDED: "#007AFF",
  CREATIVE_PENDING_OWNER: "#FF9500",
  CREATIVE_SUBMITTED: "#007AFF",
  CREATIVE_CHANGES_REQUESTED: "#FF3B30",
  CREATIVE_APPROVED: "#34C759",
  SCHEDULED: "#5856D6",
  POSTED: "#34C759",
  RETENTION_CHECK: "#FF9500",
  RELEASED: "#34C759",
  REFUNDED: "#FF3B30",
  CANCELLED: "#FF3B30",
  EXPIRED: "#8E8E93",
};

type FilterGroup = "all" | "active" | "scheduled" | "published" | "completed" | "drafts" | "cancelled";

const GROUP_COLORS: Record<FilterGroup, string> = {
  all: "#007AFF",
  active: "#FF9500",
  scheduled: "#5856D6",
  published: "#34C759",
  completed: "#34C759",
  drafts: "#8E8E93",
  cancelled: "#FF3B30",
};

const GROUP_STATUSES: Record<Exclude<FilterGroup, "all">, string[]> = {
  active: [
    "NEGOTIATION", "OWNER_ACCEPTED", "AWAITING_ESCROW_PAYMENT", "ESCROW_FUNDED",
    "CREATIVE_PENDING_OWNER", "CREATIVE_SUBMITTED", "CREATIVE_CHANGES_REQUESTED", "CREATIVE_APPROVED",
  ],
  scheduled: ["SCHEDULED"],
  published: ["POSTED", "RETENTION_CHECK"],
  completed: ["RELEASED"],
  drafts: ["DRAFT"],
  cancelled: ["CANCELLED", "EXPIRED", "REFUNDED"],
};

const GROUP_ORDER: FilterGroup[] = ["all", "active", "scheduled", "published", "completed", "drafts", "cancelled"];

function statusToGroup(status: string): Exclude<FilterGroup, "all"> | null {
  for (const [group, statuses] of Object.entries(GROUP_STATUSES)) {
    if (statuses.includes(status)) return group as Exclude<FilterGroup, "all">;
  }
  return null;
}

function Deals() {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [deals, setDeals] = useState<Deal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeGroup, setActiveGroup] = useState<FilterGroup>("active");
  const [activeStatus, setActiveStatus] = useState<string | null>(null);
  const [expandedGroup, setExpandedGroup] = useState<FilterGroup | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const isOwner = user?.active_role === "owner";
      setDeals(isOwner ? await getOwnerDeals() : await getMyDeals());
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error"));
    } finally {
      setLoading(false);
    }
  }, [user?.active_role, t]);

  useEffect(() => { load(); }, [load]);

  const groupCounts = useMemo(() => {
    const counts: Record<FilterGroup, number> = {
      all: deals.length, active: 0, scheduled: 0, published: 0, completed: 0, drafts: 0, cancelled: 0,
    };
    for (const deal of deals) {
      const g = statusToGroup(deal.status);
      if (g) counts[g]++;
    }
    return counts;
  }, [deals]);

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const deal of deals) {
      counts[deal.status] = (counts[deal.status] || 0) + 1;
    }
    return counts;
  }, [deals]);

  const filteredDeals = useMemo(() => {
    if (activeGroup === "all") return deals;
    const statuses = GROUP_STATUSES[activeGroup];
    if (activeStatus && statuses.includes(activeStatus)) {
      return deals.filter((d) => d.status === activeStatus);
    }
    return deals.filter((d) => statuses.includes(d.status));
  }, [deals, activeGroup, activeStatus]);

  // Reset filter to "all" if active group has no deals after load
  useEffect(() => {
    if (!loading && deals.length > 0 && activeGroup !== "all" && groupCounts[activeGroup] === 0) {
      setActiveGroup("all");
      setActiveStatus(null);
      setExpandedGroup(null);
    }
  }, [loading, deals.length, activeGroup, groupCounts]);

  const handleGroupTap = (group: FilterGroup) => {
    if (group === activeGroup) {
      // Toggle tier 2 expansion
      if (group === "all") return;
      setExpandedGroup(expandedGroup === group ? null : group);
    } else {
      setActiveGroup(group);
      setActiveStatus(null);
      setExpandedGroup(null);
    }
  };

  const handleStatusTap = (status: string) => {
    setActiveStatus(activeStatus === status ? null : status);
  };

  if (loading) {
    return <SkeletonList count={4} />;
  }

  if (error) {
    return <ErrorMessage message={error} onRetry={load} />;
  }

  if (deals.length === 0) {
    return (
      <EmptyState
        icon={"\u{1F91D}"}
        title={t("empty_deals")}
        description={t("empty_deals_description")}
      />
    );
  }

  const currentGroupStatuses = activeGroup !== "all" ? GROUP_STATUSES[activeGroup] : [];
  const showTier2 = expandedGroup !== null && expandedGroup === activeGroup && currentGroupStatuses.length > 1;

  return (
    <div style={{ paddingTop: 8, paddingBottom: 16 }}>
      <h2 style={{ fontSize: 20, fontWeight: 700, color: theme.text, marginBottom: 14 }}>{t("nav_deals")}</h2>

      {/* Tier 1 — Group chips */}
      <div style={{
        display: "flex", gap: 8, overflowX: "auto", paddingBottom: 8, marginBottom: 4,
        scrollbarWidth: "none", msOverflowStyle: "none",
      }}>
        {GROUP_ORDER.filter((g) => g === "all" || groupCounts[g] > 0).map((group) => {
          const isActive = group === activeGroup;
          const color = GROUP_COLORS[group];
          return (
            <button
              key={group}
              onClick={() => handleGroupTap(group)}
              style={{
                display: "inline-flex", alignItems: "center", gap: 6,
                borderRadius: 20, padding: "6px 14px", fontSize: 13, fontWeight: isActive ? 700 : 600,
                backgroundColor: isActive ? color + "22" : theme.bgSecondary,
                color: isActive ? color : theme.textSecondary,
                border: "none", cursor: "pointer", whiteSpace: "nowrap", flexShrink: 0,
              }}
            >
              {t(`deals_filter_${group}`)}
              <span style={{
                borderRadius: 10, padding: "1px 6px", fontSize: 11,
                backgroundColor: isActive ? color + "33" : theme.bgSecondary,
                color: isActive ? color : theme.textSecondary,
              }}>
                {groupCounts[group]}
              </span>
            </button>
          );
        })}
      </div>

      {/* Tier 2 — Individual status chips */}
      {showTier2 && (
        <div style={{
          display: "flex", gap: 6, overflowX: "auto", paddingBottom: 8, marginBottom: 4,
          scrollbarWidth: "none", msOverflowStyle: "none",
        }}>
          {currentGroupStatuses.filter((s) => (statusCounts[s] || 0) > 0).map((status) => {
            const isActive = status === activeStatus;
            const color = GROUP_COLORS[activeGroup];
            return (
              <button
                key={status}
                onClick={() => handleStatusTap(status)}
                style={{
                  display: "inline-flex", alignItems: "center", gap: 5,
                  borderRadius: 16, padding: "4px 12px", fontSize: 12, fontWeight: isActive ? 700 : 500,
                  backgroundColor: isActive ? color + "22" : theme.bgSecondary,
                  color: isActive ? color : theme.textSecondary,
                  border: "none", cursor: "pointer", whiteSpace: "nowrap", flexShrink: 0,
                }}
              >
                {t(`deals_status_${status}`)}
                <span style={{ fontSize: 10, opacity: 0.8 }}>{statusCounts[status]}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* Deal list or filtered empty state */}
      {filteredDeals.length === 0 ? (
        <EmptyState
          icon={"\u{1F50D}"}
          title={t("deals_empty_filtered")}
          description={t("deals_empty_filtered_description")}
        />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {filteredDeals.map((deal) => {
            const statusColor = STATUS_COLORS[deal.status] || theme.textSecondary;
            return (
              <div
                key={deal.id}
                onClick={() => navigate(`/deals/${deal.id}`)}
                style={{
                  backgroundColor: theme.bgSecondary,
                  borderRadius: 14,
                  padding: "14px 16px",
                  cursor: "pointer",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <span style={{ fontWeight: 600, fontSize: 15, color: theme.text }}>
                    {t("nav_deals")} #{deal.id}
                  </span>
                  <span style={{
                    fontSize: 11,
                    fontWeight: 600,
                    padding: "2px 8px",
                    borderRadius: 6,
                    backgroundColor: statusColor + "22",
                    color: statusColor,
                  }}>
                    {t(`deals_status_${deal.status}`)}
                  </span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ color: theme.textSecondary, fontSize: 13 }}>
                    {new Date(deal.created_at).toLocaleDateString()}
                  </span>
                  <span style={{ fontWeight: 700, fontSize: 15, color: theme.accent }}>
                    {Number(deal.price).toFixed(2)} {deal.currency}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default Deals;
