import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useTheme } from "@/context/ThemeContext";
import { useBackButton } from "@/hooks/useBackButton";
import { useAuth } from "@/context/AuthContext";
import {
  getDeal,
  transitionDeal,
  updateDealBrief,
  updateDealWallet,
  confirmDealWallet,
  resolveAmendment,
  submitCreative,
  approveCreative,
  requestCreativeChanges,
  schedulePost,
  checkRetention,
} from "@/api/deals";
import { getPlatformConfig } from "@/api/listings";
import { ApiError } from "@/api/client";
import { confirmDeposit } from "@/api/escrow";
import { useTonEscrow } from "@/hooks/useTonEscrow";
import type { DealDetailWithActions } from "@/api/types";
import { SkeletonDetail } from "@/ui/Skeleton";
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

const ACTION_COLORS: Record<string, string> = {
  send: "#007AFF",
  accept: "#34C759",
  request_escrow: "#007AFF",
  submit_creative: "#007AFF",
  approve_creative: "#34C759",
  request_changes: "#FF9500",
  schedule: "#5856D6",
  cancel: "#FF3B30",
};

const ESCROW_STATE_COLORS: Record<string, string> = {
  init: "#FF9500",
  funded: "#007AFF",
  released: "#34C759",
  refunded: "#FF3B30",
};

const DESTRUCTIVE_ACTIONS = new Set(["cancel"]);

function InfoRow({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  const theme = useTheme();
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0", borderBottom: `1px solid ${theme.border}` }}>
      <span style={{ fontSize: 14, color: theme.textSecondary }}>{label}</span>
      <span style={{ fontSize: 14, fontWeight: 600, color: accent ? theme.accent : theme.text }}>{value}</span>
    </div>
  );
}

function DealDetail() {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { id } = useParams<{ id: string }>();
  useBackButton(-1);
  const [deal, setDeal] = useState<DealDetailWithActions | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [escrowCreating] = useState(false);
  const [depositVerifying, setDepositVerifying] = useState(false);
  const verifyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Brief editing state (DRAFT only, advertiser)
  const [editBrief, setEditBrief] = useState("");
  const [editPublishFrom, setEditPublishFrom] = useState("");
  const [editPublishTo, setEditPublishTo] = useState("");
  const [briefSaving, setBriefSaving] = useState(false);

  // Creative submission state (owner)
  const [creativeText, setCreativeText] = useState("");
  const [creativeSaving, setCreativeSaving] = useState(false);

  // Creative review state (advertiser)
  const [feedbackText, setFeedbackText] = useState("");
  const [feedbackSaving, setFeedbackSaving] = useState(false);

  // Schedule state (owner)
  const [scheduleDate, setScheduleDate] = useState(() => {
    const d = new Date(Date.now() + 60_000);
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  });
  const [scheduleTime, setScheduleTime] = useState(() => {
    const d = new Date(Date.now() + 60_000);
    return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  });
  const [scheduleSaving, setScheduleSaving] = useState(false);

  // Owner per-deal wallet state
  const [ownerWallet, setOwnerWallet] = useState("");
  const [ownerWalletSaving, setOwnerWalletSaving] = useState(false);

  // Action error state
  const [actionError, setActionError] = useState<string | null>(null);

  // Retention check state
  const [retentionChecking, setRetentionChecking] = useState(false);
  const [retentionMessage, setRetentionMessage] = useState<{ text: string; color: string } | null>(null);

  // TON network for Tonscan links
  const [tonNetwork, setTonNetwork] = useState("testnet");

  const { walletAddress, connected, sendDeposit, sending } = useTonEscrow();
  const role = (user?.active_role || "advertiser") as "advertiser" | "owner";

  const tonscanUrl = (address: string) => {
    const base = tonNetwork === "mainnet"
      ? "https://tonscan.org/address/"
      : "https://testnet.tonscan.org/address/";
    return base + address;
  };

  const load = useCallback(async () => {
    try {
      const data = await getDeal(Number(id), role);
      setDeal(data);
      // Initialize brief edit fields
      setEditBrief(data.brief || "");
      setEditPublishFrom(data.publish_from ? data.publish_from.slice(0, 16) : "");
      setEditPublishTo(data.publish_to ? data.publish_to.slice(0, 16) : "");
      setOwnerWallet(data.owner_wallet_address || "");
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [id, role]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    getPlatformConfig().then(cfg => {
      if (cfg.ton_network) setTonNetwork(cfg.ton_network);
    }).catch(() => {});
  }, []);

  const handleAction = async (action: string) => {
    if (DESTRUCTIVE_ACTIONS.has(action)) {
      if (!window.confirm(t("deal_action_confirm"))) return;
    }
    setActionLoading(action);
    setActionError(null);
    try {
      await transitionDeal(Number(id), action, role);
      await load();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : t("error"));
    }
    setActionLoading(null);
  };

  const stopVerifyPolling = useCallback(() => {
    if (verifyTimerRef.current) {
      clearTimeout(verifyTimerRef.current);
      verifyTimerRef.current = null;
    }
  }, []);

  // Cleanup polling on unmount
  useEffect(() => stopVerifyPolling, [stopVerifyPolling]);

  const pollDepositVerification = useCallback(async (attemptsLeft: number) => {
    if (attemptsLeft <= 0) {
      setDepositVerifying(false);
      await load();
      return;
    }
    try {
      const escrowResult = await confirmDeposit(Number(id));
      if (escrowResult.on_chain_state === "funded") {
        setDepositVerifying(false);
        await load();
        return;
      }
    } catch { /* ignore */ }
    verifyTimerRef.current = setTimeout(() => pollDepositVerification(attemptsLeft - 1), 5000);
  }, [id, load]);

  const handleSendDeposit = async () => {
    if (!deal?.escrow || !connected) return;
    const escrow = deal.escrow;
    const targetAddress = escrow.contract_address || "";
    if (!targetAddress || targetAddress.startsWith("pending-")) {
      alert("Escrow contract not yet deployed");
      return;
    }
    try {
      await sendDeposit(targetAddress, escrow.amount, escrow.state_init_boc || undefined);
      // Transaction sent — start polling for on-chain verification
      setDepositVerifying(true);
      pollDepositVerification(12); // poll up to 12 times (~60s)
    } catch { /* user rejected or wallet error */ }
  };

  const handleSaveBrief = async () => {
    setBriefSaving(true);
    try {
      await updateDealBrief(Number(id), {
        brief: editBrief || undefined,
        publish_from: editPublishFrom || undefined,
        publish_to: editPublishTo || undefined,
      });
      await load();
    } catch { /* ignore */ }
    setBriefSaving(false);
  };

  const handleSaveOwnerWallet = async () => {
    if (!ownerWallet.trim()) return;
    setOwnerWalletSaving(true);
    try {
      await updateDealWallet(Number(id), ownerWallet.trim());
      await load();
    } catch { /* ignore */ }
    setOwnerWalletSaving(false);
  };

  const handleConfirmProfileWallet = async () => {
    setOwnerWalletSaving(true);
    try {
      await confirmDealWallet(Number(id));
      await load();
    } catch { /* ignore */ }
    setOwnerWalletSaving(false);
  };

  const handleAmendment = async (action: "accept" | "reject") => {
    if (!deal?.pending_amendment) return;
    setActionLoading(action === "accept" ? "accept_amend" : "reject_amend");
    try {
      await resolveAmendment(Number(id), deal.pending_amendment.id, action);
      await load();
    } catch { /* ignore */ }
    setActionLoading(null);
  };

  const handleSubmitCreative = async () => {
    if (!creativeText.trim()) return;
    setCreativeSaving(true);
    try {
      await submitCreative(Number(id), { text: creativeText });
      setCreativeText("");
      await load();
    } catch { /* ignore */ }
    setCreativeSaving(false);
  };

  const handleApproveCreative = async () => {
    setActionLoading("approve_creative");
    try {
      await approveCreative(Number(id));
      await load();
    } catch { /* ignore */ }
    setActionLoading(null);
  };

  const handleRequestChanges = async () => {
    if (!feedbackText.trim()) return;
    setFeedbackSaving(true);
    try {
      await requestCreativeChanges(Number(id), feedbackText);
      setFeedbackText("");
      await load();
    } catch { /* ignore */ }
    setFeedbackSaving(false);
  };

  const handleSchedulePost = async () => {
    if (!scheduleDate) return;
    const dateStr = scheduleTime
      ? `${scheduleDate}T${scheduleTime}:00`
      : `${scheduleDate}T12:00:00`;
    if (new Date(dateStr).getTime() <= Date.now()) {
      alert(t("schedule_past_error"));
      return;
    }
    setScheduleSaving(true);
    try {
      await schedulePost(Number(id), dateStr);
      setScheduleDate("");
      setScheduleTime("");
      await load();
    } catch { /* ignore */ }
    setScheduleSaving(false);
  };

  const handleCheckRetention = async () => {
    setRetentionChecking(true);
    setRetentionMessage(null);
    try {
      const result = await checkRetention(Number(id), role);
      if (result.ok && !result.finalized) {
        setRetentionMessage({ text: t("posting_check_ok"), color: "#34C759" });
      } else if (result.ok && result.finalized) {
        setRetentionMessage({ text: t("posting_check_ok_elapsed"), color: "#34C759" });
        await load();
      } else {
        // Violation detected — refund initiated in background
        const reason = result.error || t("posting_not_retained");
        setRetentionMessage({
          text: t("posting_violation_refund", { reason }),
          color: "#FF9500",
        });
        await load();
      }
    } catch (err) {
      // 409 means the deal already transitioned (check completed by another process)
      if (err instanceof ApiError && err.status === 409) {
        await load();
      } else {
        setRetentionMessage({ text: t("error"), color: "#FF3B30" });
      }
    }
    setRetentionChecking(false);
  };

  if (loading) {
    return <SkeletonDetail />;
  }

  if (!deal) {
    return <ErrorMessage message={t("error")} onRetry={load} />;
  }

  const statusColor = STATUS_COLORS[deal.status] || theme.textSecondary;
  const listing = deal.listing;
  const channel = listing?.channel;
  const isAdvertiser = user?.id === deal.advertiser_id;
  const isOwner = user?.id === deal.owner_id || (!isAdvertiser && deal.available_actions.length > 0);
  const isOwnerSide = !isAdvertiser;
  const isDraft = deal.status === "DRAFT";
  const escrow = deal.escrow;
  const showEscrowCard = escrow || deal.status === "OWNER_ACCEPTED" || deal.status === "AWAITING_ESCROW_PAYMENT" || deal.status === "ESCROW_FUNDED";
  const currentCreative = deal.current_creative;
  const creativeHistory = deal.creative_history || [];
  const posting = deal.posting;

  // Creative-related statuses
  const showCreativeCard = [
    "CREATIVE_PENDING_OWNER", "CREATIVE_SUBMITTED", "CREATIVE_CHANGES_REQUESTED",
    "CREATIVE_APPROVED", "SCHEDULED", "POSTED", "RETENTION_CHECK", "RELEASED",
  ].includes(deal.status);

  // Schedule-related statuses
  const showScheduleCard = ["CREATIVE_APPROVED", "SCHEDULED", "POSTED", "RETENTION_CHECK", "RELEASED"].includes(deal.status);

  // Posting info card
  const showPostingCard = posting && ["POSTED", "RETENTION_CHECK", "RELEASED", "REFUNDED"].includes(deal.status);

  // Actions handled by dedicated UI (filter out from generic buttons)
  const DEDICATED_ACTIONS = new Set(["submit_creative", "approve_creative", "request_changes", "schedule"]);
  const genericActions = deal.available_actions.filter(a => !DEDICATED_ACTIONS.has(a));

  return (
    <div style={{ paddingTop: 8, paddingBottom: 16 }}>

      {/* Deal header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: theme.text, margin: 0 }}>
          {t("deal_detail_title")} #{deal.id}
        </h2>
        <span style={{
          fontSize: 13,
          fontWeight: 700,
          padding: "4px 12px",
          borderRadius: 8,
          backgroundColor: statusColor + "22",
          color: statusColor,
        }}>
          {deal.status}
        </span>
      </div>

      {/* Listing & channel info */}
      {listing && channel && (
        <div
          onClick={() => {
            if (isOwnerSide) {
              navigate(`/channels/${channel.id}`);
            } else {
              navigate(`/channel-view/${channel.id}`, { state: { channel } });
            }
          }}
          style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: 16, marginBottom: 16, cursor: "pointer" }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
            <span style={{ fontWeight: 700, fontSize: 16, color: theme.text, flex: 1 }}>{channel.title}</span>
            {channel.username && <span style={{ color: theme.textSecondary, fontSize: 13 }}>@{channel.username}</span>}
            <span style={{ fontSize: 16, color: theme.textSecondary, marginLeft: 4 }}>{"\u203A"}</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <div>
              <span style={{ fontSize: 11, color: theme.textSecondary }}>{t("channel_subscribers")}</span>
              <p style={{ fontWeight: 600, fontSize: 14, color: theme.text, margin: "2px 0 0" }}>{channel.subscribers.toLocaleString()}</p>
            </div>
            <div>
              <span style={{ fontSize: 11, color: theme.textSecondary }}>{t("channel_avg_views")}</span>
              <p style={{ fontWeight: 600, fontSize: 14, color: theme.text, margin: "2px 0 0" }}>{channel.avg_views.toLocaleString()}</p>
            </div>
          </div>
          {listing.title && (
            <div style={{ marginTop: 10, paddingTop: 10, borderTop: `1px solid ${theme.border}` }}>
              <span style={{ fontSize: 11, color: theme.textSecondary }}>{t("listing_title")}</span>
              <p style={{ fontWeight: 600, fontSize: 14, color: theme.text, margin: "2px 0 0" }}>{listing.title}</p>
            </div>
          )}
        </div>
      )}

      {/* Deal details */}
      <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: "6px 16px", marginBottom: 16 }}>
        <InfoRow label={t("listing_price")} value={`${Number(deal.price).toFixed(2)} ${deal.currency}`} accent />
        <InfoRow label={t("deal_status")} value={deal.status} />
        <InfoRow label={t("deal_role")} value={isAdvertiser ? t("role_advertiser") : t("role_owner")} />
        <InfoRow label={t("deal_created")} value={new Date(deal.created_at).toLocaleDateString()} />
        {/* Brief fields (read-only when not DRAFT) */}
        {!isDraft && deal.brief && (
          <InfoRow label={t("deal_brief")} value={deal.brief.length > 60 ? deal.brief.slice(0, 60) + "..." : deal.brief} />
        )}
        {!isDraft && deal.publish_from && (
          <InfoRow label={t("campaign_publish_from")} value={new Date(deal.publish_from).toLocaleString()} />
        )}
        {!isDraft && deal.publish_to && (
          <InfoRow label={t("campaign_publish_to")} value={new Date(deal.publish_to).toLocaleString()} />
        )}
      </div>

      {/* Editable brief fields (DRAFT + advertiser only) */}
      {isDraft && isAdvertiser && (
        <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: 16, marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: theme.text, margin: "0 0 12px" }}>{t("deal_brief_section")}</h3>
          <div style={{ marginBottom: 10 }}>
            <label style={{ fontSize: 12, color: theme.textSecondary, display: "block", marginBottom: 4 }}>{t("deal_brief")} *</label>
            <textarea
              value={editBrief}
              onChange={e => setEditBrief(e.target.value)}
              rows={3}
              style={{
                width: "100%", padding: 10, borderRadius: 8, border: `1px solid ${theme.border}`,
                backgroundColor: theme.bg, color: theme.text, fontSize: 14, resize: "vertical",
                boxSizing: "border-box",
              }}
            />
          </div>
          <div style={{ marginBottom: 10 }}>
            <label style={{ fontSize: 12, color: theme.textSecondary, display: "block", marginBottom: 4 }}>{t("campaign_publish_from")}</label>
            {(() => {
              const splitDT = (v: string) => {
                if (!v) return { date: "", time: "" };
                const [d, t] = v.split("T");
                return { date: d ?? "", time: t?.slice(0, 5) ?? "" };
              };
              const { date, time } = splitDT(editPublishFrom);
              const inputSt: React.CSSProperties = {
                padding: 10, borderRadius: 8, border: `1px solid ${theme.border}`,
                backgroundColor: theme.bg, color: theme.text, fontSize: 14, boxSizing: "border-box",
              };
              return (
                <div style={{ display: "flex", gap: 8 }}>
                  <input type="date" value={date} onChange={e => {
                    const d = e.target.value;
                    setEditPublishFrom(d ? `${d}T${time || "00:00"}` : "");
                  }} style={{ ...inputSt, flex: 1, minWidth: 0 }} />
                  <input type="time" value={time} onChange={e => {
                    setEditPublishFrom(date ? `${date}T${e.target.value || "00:00"}` : "");
                  }} style={{ ...inputSt, width: 110 }} />
                </div>
              );
            })()}
          </div>
          <div style={{ marginBottom: 10 }}>
            <label style={{ fontSize: 12, color: theme.textSecondary, display: "block", marginBottom: 4 }}>{t("campaign_publish_to")}</label>
            {(() => {
              const splitDT = (v: string) => {
                if (!v) return { date: "", time: "" };
                const [d, t] = v.split("T");
                return { date: d ?? "", time: t?.slice(0, 5) ?? "" };
              };
              const { date, time } = splitDT(editPublishTo);
              const inputSt: React.CSSProperties = {
                padding: 10, borderRadius: 8, border: `1px solid ${theme.border}`,
                backgroundColor: theme.bg, color: theme.text, fontSize: 14, boxSizing: "border-box",
              };
              return (
                <div style={{ display: "flex", gap: 8 }}>
                  <input type="date" value={date} onChange={e => {
                    const d = e.target.value;
                    setEditPublishTo(d ? `${d}T${time || "00:00"}` : "");
                  }} style={{ ...inputSt, flex: 1, minWidth: 0 }} />
                  <input type="time" value={time} onChange={e => {
                    setEditPublishTo(date ? `${date}T${e.target.value || "00:00"}` : "");
                  }} style={{ ...inputSt, width: 110 }} />
                </div>
              );
            })()}
          </div>
          <button
            onClick={handleSaveBrief}
            disabled={briefSaving}
            style={{
              width: "100%", padding: "10px 16px", borderRadius: 10, border: "none",
              backgroundColor: theme.accent, color: "#fff", fontWeight: 600, fontSize: 14,
              cursor: briefSaving ? "wait" : "pointer", opacity: briefSaving ? 0.6 : 1,
            }}
          >
            {briefSaving ? "..." : t("deal_brief_save")}
          </button>
        </div>
      )}

      {/* Pending amendment card (advertiser only) */}
      {deal.pending_amendment && isAdvertiser && (
        <div style={{ backgroundColor: "#FF950022", borderRadius: 14, padding: 16, marginBottom: 16, border: "1px solid #FF9500" }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: "#FF9500", margin: "0 0 8px" }}>{t("deal_amendment_title")}</h3>
          {deal.pending_amendment.proposed_price != null && (
            <p style={{ fontSize: 13, color: theme.text, margin: "4px 0" }}>
              {t("deal_amendment_price")}: {Number(deal.pending_amendment.proposed_price).toFixed(2)} {deal.currency}
            </p>
          )}
          {deal.pending_amendment.proposed_publish_date && (
            <p style={{ fontSize: 13, color: theme.text, margin: "4px 0" }}>
              {t("deal_amendment_publish_date")}: {new Date(deal.pending_amendment.proposed_publish_date).toLocaleDateString()}
            </p>
          )}
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <button
              onClick={() => handleAmendment("accept")}
              disabled={actionLoading !== null}
              style={{
                flex: 1, padding: "8px 16px", borderRadius: 10, border: "none",
                backgroundColor: "#34C75922", color: "#34C759", fontWeight: 600, fontSize: 14,
                cursor: actionLoading ? "wait" : "pointer",
              }}
            >
              {actionLoading === "accept_amend" ? "..." : t("deal_amendment_accept")}
            </button>
            <button
              onClick={() => handleAmendment("reject")}
              disabled={actionLoading !== null}
              style={{
                flex: 1, padding: "8px 16px", borderRadius: 10, border: "none",
                backgroundColor: "#FF3B3022", color: "#FF3B30", fontWeight: 600, fontSize: 14,
                cursor: actionLoading ? "wait" : "pointer",
              }}
            >
              {actionLoading === "reject_amend" ? "..." : t("deal_amendment_reject")}
            </button>
          </div>
        </div>
      )}

      {/* Pending amendment card (owner — read-only) */}
      {deal.pending_amendment && !isAdvertiser && (
        <div style={{ backgroundColor: "#FF950022", borderRadius: 14, padding: 16, marginBottom: 16, border: "1px solid #FF9500" }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: "#FF9500", margin: "0 0 8px" }}>{t("deal_amendment_pending")}</h3>
          {deal.pending_amendment.proposed_price != null && (
            <p style={{ fontSize: 13, color: theme.text, margin: "4px 0" }}>
              {t("deal_amendment_price")}: {Number(deal.pending_amendment.proposed_price).toFixed(2)} {deal.currency}
            </p>
          )}
          {deal.pending_amendment.proposed_publish_date && (
            <p style={{ fontSize: 13, color: theme.text, margin: "4px 0" }}>
              {t("deal_amendment_publish_date")}: {new Date(deal.pending_amendment.proposed_publish_date).toLocaleDateString()}
            </p>
          )}
        </div>
      )}

      {/* Escrow card */}
      {showEscrowCard && (
        <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: 16, marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: theme.text, margin: "0 0 12px" }}>{t("escrow_title")}</h3>

          {/* Wallet status */}
          {isAdvertiser && !connected && (
            <div style={{ marginBottom: 12 }}>
              <p style={{ fontSize: 13, color: theme.textSecondary, margin: "0 0 8px" }}>{t("escrow_no_wallet")}</p>
              <button
                onClick={() => navigate("/profile")}
                style={{
                  padding: "8px 16px", borderRadius: 10, border: "none",
                  backgroundColor: theme.accent, color: "#fff", fontWeight: 600, fontSize: 14,
                  cursor: "pointer",
                }}
              >
                {t("profile_wallet_connect")}
              </button>
            </div>
          )}
          {isAdvertiser && connected && walletAddress && (
            <div style={{ marginBottom: 12 }}>
              <InfoRow label={t("escrow_wallet_connected")} value={walletAddress.slice(0, 8) + "\u2026" + walletAddress.slice(-4)} accent />
            </div>
          )}

          {/* Escrow info when it exists */}
          {escrow && (
            <div>
              <InfoRow
                label={t("escrow_state")}
                value={t(`escrow_state_${escrow.on_chain_state}`)}
              />
              <InfoRow label={t("escrow_amount")} value={`${Number(escrow.amount).toFixed(2)} TON`} accent />
              {escrow.fee_percent > 0 && (
                <InfoRow
                  label={t("escrow_fee")}
                  value={t("escrow_fee_value", {
                    percent: escrow.fee_percent,
                    amount: ((escrow.amount * escrow.fee_percent) / 100).toFixed(2),
                  })}
                />
              )}
              {escrow.contract_address && !escrow.contract_address.startsWith("pending-") && (
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0", borderBottom: `1px solid ${theme.border}` }}>
                  <span style={{ fontSize: 14, color: theme.textSecondary }}>{t("escrow_address")}</span>
                  <a
                    href={tonscanUrl(escrow.contract_address)}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ fontSize: 14, fontWeight: 600, color: theme.accent, textDecoration: "none" }}
                  >
                    {escrow.contract_address.slice(0, 8) + "\u2026" + escrow.contract_address.slice(-4)} ↗
                  </a>
                </div>
              )}
              {isOwner && escrow.owner_address && (
                <InfoRow label={t("escrow_owner_payout")} value={escrow.owner_address.slice(0, 8) + "\u2026" + escrow.owner_address.slice(-4)} />
              )}
              {escrow.funded_at && (
                <InfoRow label={t("escrow_funded_at")} value={new Date(escrow.funded_at).toLocaleString()} />
              )}
              {escrow.released_at && (
                <InfoRow label={t("escrow_released_at")} value={new Date(escrow.released_at).toLocaleString()} />
              )}
              {escrow.refunded_at && (
                <InfoRow label={t("escrow_refunded_at")} value={new Date(escrow.refunded_at).toLocaleString()} />
              )}

              {/* State-specific indicators */}
              {escrow.on_chain_state !== "init" && (
                <div style={{ marginTop: 8, padding: "6px 12px", borderRadius: 8, backgroundColor: (ESCROW_STATE_COLORS[escrow.on_chain_state] || theme.accent) + "22" }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: ESCROW_STATE_COLORS[escrow.on_chain_state] || theme.accent }}>
                    {t(`escrow_state_${escrow.on_chain_state}`)}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Waiting for wallets indicator (AWAITING_ESCROW_PAYMENT + no escrow yet) */}
          {deal.status === "AWAITING_ESCROW_PAYMENT" && !escrow && (
            <div style={{
              marginTop: 12, padding: 16, borderRadius: 10,
              backgroundColor: "#FF950018", textAlign: "center",
            }}>
              <p style={{ fontSize: 14, fontWeight: 600, color: "#FF9500", margin: "0 0 4px" }}>
                {t("escrow_waiting_wallets")}
              </p>
              <p style={{ fontSize: 12, color: theme.textSecondary, margin: 0 }}>
                {t("escrow_waiting_wallets_hint")}
              </p>
            </div>
          )}

          {/* Owner per-deal wallet — no permission message for team members without can_payout */}
          {isOwnerSide && !deal.can_manage_wallet && !escrow && !["RELEASED", "REFUNDED", "CANCELLED", "EXPIRED"].includes(deal.status) && !deal.owner_wallet_confirmed && (
            <div style={{ marginTop: 12, padding: 12, borderRadius: 10, backgroundColor: "#FF950018" }}>
              <p style={{ fontSize: 13, color: "#FF9500", margin: 0, lineHeight: 1.4 }}>
                {t("deal_wallet_no_permission")}
              </p>
            </div>
          )}

          {/* Owner per-deal wallet — editable only before escrow is created */}
          {deal.can_manage_wallet && !escrow && !["RELEASED", "REFUNDED", "CANCELLED", "EXPIRED"].includes(deal.status) && (
            <div style={{ marginTop: 12 }}>
              <label style={{ fontSize: 12, color: theme.textSecondary, display: "block", marginBottom: 4 }}>
                {t("deal_owner_wallet")}
              </label>
              <p style={{ fontSize: 11, color: theme.textSecondary, margin: "0 0 6px" }}>
                {deal.owner_wallet_confirmed
                  ? t("deal_owner_wallet_confirmed_hint")
                  : t("deal_owner_wallet_confirm_required")}
              </p>

              {/* No wallet at all — prompt to connect */}
              {!user?.wallet_address && !deal.owner_wallet_address && (
                <div style={{ marginBottom: 8 }}>
                  <p style={{ fontSize: 13, color: "#FF9500", margin: "0 0 8px" }}>
                    {t("deal_owner_wallet_no_wallet")}
                  </p>
                  <button
                    onClick={() => navigate("/profile")}
                    style={{
                      width: "100%", padding: "8px 16px", borderRadius: 10, border: "none",
                      backgroundColor: theme.accent, color: "#fff", fontWeight: 600, fontSize: 14,
                      cursor: "pointer",
                    }}
                  >
                    {t("profile_wallet_connect")}
                  </button>
                </div>
              )}

              {/* Wallet input + action buttons */}
              {(user?.wallet_address || deal.owner_wallet_address) && (
                <>
                  <input
                    type="text"
                    value={ownerWallet}
                    onChange={e => setOwnerWallet(e.target.value)}
                    placeholder={user?.wallet_address ? `${user.wallet_address.slice(0, 8)}\u2026${user.wallet_address.slice(-4)}` : "EQ..."}
                    style={{
                      width: "100%", padding: 10, borderRadius: 8, border: `1px solid ${theme.border}`,
                      backgroundColor: theme.bg, color: theme.text, fontSize: 14,
                      boxSizing: "border-box", marginBottom: 8,
                    }}
                  />
                  <div style={{ display: "flex", gap: 8 }}>
                    <button
                      onClick={handleSaveOwnerWallet}
                      disabled={ownerWalletSaving || !ownerWallet.trim()}
                      style={{
                        flex: 1, padding: "10px 16px", borderRadius: 10, border: "none",
                        backgroundColor: theme.accent, color: "#fff", fontWeight: 600, fontSize: 14,
                        cursor: ownerWalletSaving ? "wait" : "pointer",
                        opacity: ownerWalletSaving || !ownerWallet.trim() ? 0.6 : 1,
                      }}
                    >
                      {ownerWalletSaving ? "..." : t("deal_owner_wallet_save")}
                    </button>
                    {user?.wallet_address && !deal.owner_wallet_confirmed && (
                      <button
                        onClick={handleConfirmProfileWallet}
                        disabled={ownerWalletSaving}
                        style={{
                          flex: 1, padding: "10px 16px", borderRadius: 10, border: "none",
                          backgroundColor: "#34C75922", color: "#34C759", fontWeight: 600, fontSize: 14,
                          cursor: ownerWalletSaving ? "wait" : "pointer",
                          opacity: ownerWalletSaving ? 0.6 : 1,
                        }}
                      >
                        {t("deal_owner_wallet_confirm")}
                      </button>
                    )}
                  </div>
                </>
              )}

              {/* Wallet confirmed badge */}
              {deal.owner_wallet_confirmed && (
                <div style={{ marginTop: 8, padding: "6px 12px", borderRadius: 8, backgroundColor: "#34C75922" }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "#34C759" }}>
                    {t("deal_owner_wallet_confirmed_badge")}
                  </span>
                </div>
              )}
            </div>
          )}
          {/* Send Deposit button (AWAITING_ESCROW_PAYMENT + advertiser + escrow exists + wallet connected) */}
          {isAdvertiser && deal.status === "AWAITING_ESCROW_PAYMENT" && escrow && escrow.on_chain_state === "init" && connected && !depositVerifying && (
            <div style={{ marginTop: 12 }}>
              <p style={{ fontSize: 12, color: theme.textSecondary, margin: "0 0 8px" }}>
                {t("escrow_deposit_hint", { amount: Number(escrow.amount).toFixed(2) })}
              </p>
              <button
                onClick={handleSendDeposit}
                disabled={sending}
                style={{
                  width: "100%", padding: "10px 16px", borderRadius: 10, border: "none",
                  backgroundColor: "#007AFF", color: "#fff", fontWeight: 600, fontSize: 14,
                  cursor: sending ? "wait" : "pointer", opacity: sending ? 0.6 : 1,
                }}
              >
                {sending ? t("escrow_sending") : t("escrow_send_deposit")}
              </button>
            </div>
          )}

          {/* Verification indicator (shown after deposit sent) */}
          {depositVerifying && (
            <div style={{
              marginTop: 12, padding: 16, borderRadius: 10,
              backgroundColor: "#007AFF18", textAlign: "center",
            }}>
              <div style={{
                width: 24, height: 24, margin: "0 auto 10px",
                border: "3px solid #007AFF33", borderTopColor: "#007AFF",
                borderRadius: "50%",
                animation: "spin 1s linear infinite",
              }} />
              <p style={{ fontSize: 14, fontWeight: 600, color: "#007AFF", margin: "0 0 4px" }}>
                {t("escrow_verifying")}
              </p>
              <p style={{ fontSize: 12, color: theme.textSecondary, margin: 0 }}>
                {t("escrow_verifying_hint")}
              </p>
              <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
            </div>
          )}
        </div>
      )}

      {/* Creative Card */}
      {showCreativeCard && (
        <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: 16, marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: theme.text, margin: "0 0 12px" }}>{t("creative_title")}</h3>

          {/* Current creative preview */}
          {currentCreative && (
            <div style={{ marginBottom: 12, padding: 12, borderRadius: 8, backgroundColor: theme.bg, border: `1px solid ${theme.border}` }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <span style={{ fontSize: 12, color: theme.textSecondary }}>{t("creative_version")} {currentCreative.version}</span>
                <span style={{
                  fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 6,
                  backgroundColor: currentCreative.status === "approved" ? "#34C75922" : currentCreative.status === "changes_requested" ? "#FF3B3022" : "#007AFF22",
                  color: currentCreative.status === "approved" ? "#34C759" : currentCreative.status === "changes_requested" ? "#FF3B30" : "#007AFF",
                }}>
                  {t(`creative_status_${currentCreative.status}`)}
                </span>
              </div>
              <p style={{ fontSize: 14, color: theme.text, margin: "4px 0", whiteSpace: "pre-wrap", lineHeight: 1.4 }}>
                {currentCreative.text.length > 300 ? currentCreative.text.slice(0, 300) + "..." : currentCreative.text}
              </p>
              {currentCreative.media_items && currentCreative.media_items.length > 0 && (
                <p style={{ fontSize: 12, color: theme.textSecondary, margin: "4px 0 0" }}>
                  {t("creative_media_attached")}: {currentCreative.media_items.length} {currentCreative.media_items.length === 1 ? currentCreative.media_items[0].type : "files"}
                </p>
              )}
              {currentCreative.feedback && (
                <div style={{ marginTop: 8, padding: 8, borderRadius: 6, backgroundColor: "#FF3B3010", border: "1px solid #FF3B3033" }}>
                  <span style={{ fontSize: 11, color: "#FF3B30", fontWeight: 600 }}>{t("creative_feedback")}:</span>
                  <p style={{ fontSize: 13, color: theme.text, margin: "4px 0 0" }}>{currentCreative.feedback}</p>
                </div>
              )}
            </div>
          )}

          {/* Advertiser: waiting hint when no creative yet */}
          {isAdvertiser && deal.status === "CREATIVE_PENDING_OWNER" && !currentCreative && (
            <p style={{ fontSize: 13, color: theme.textSecondary, margin: "0 0 8px", lineHeight: 1.4 }}>
              {t("creative_waiting_owner")}
            </p>
          )}

          {/* Owner: submit creative form */}
          {isOwner && (deal.status === "CREATIVE_PENDING_OWNER" || deal.status === "CREATIVE_CHANGES_REQUESTED") && (
            <div style={{ marginTop: 8 }}>
              <textarea
                value={creativeText}
                onChange={e => setCreativeText(e.target.value)}
                placeholder={t("creative_placeholder")}
                rows={4}
                style={{
                  width: "100%", padding: 10, borderRadius: 8, border: `1px solid ${theme.border}`,
                  backgroundColor: theme.bg, color: theme.text, fontSize: 14, resize: "vertical",
                  boxSizing: "border-box", marginBottom: 8,
                }}
              />
              <p style={{ fontSize: 12, color: theme.textSecondary, margin: "0 0 8px" }}>
                {t("creative_media_hint")}
              </p>
              <button
                onClick={handleSubmitCreative}
                disabled={creativeSaving || !creativeText.trim()}
                style={{
                  width: "100%", padding: "10px 16px", borderRadius: 10, border: "none",
                  backgroundColor: "#007AFF", color: "#fff", fontWeight: 600, fontSize: 14,
                  cursor: creativeSaving ? "wait" : "pointer", opacity: creativeSaving || !creativeText.trim() ? 0.6 : 1,
                }}
              >
                {creativeSaving ? "..." : t("creative_submit")}
              </button>
            </div>
          )}

          {/* Advertiser: approve / request changes */}
          {isAdvertiser && deal.status === "CREATIVE_SUBMITTED" && currentCreative && (
            <div style={{ marginTop: 8 }}>
              <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                <button
                  onClick={handleApproveCreative}
                  disabled={actionLoading !== null}
                  style={{
                    flex: 1, padding: "10px 16px", borderRadius: 10, border: "none",
                    backgroundColor: "#34C75922", color: "#34C759", fontWeight: 600, fontSize: 14,
                    cursor: actionLoading ? "wait" : "pointer",
                  }}
                >
                  {actionLoading === "approve_creative" ? "..." : t("creative_approve")}
                </button>
              </div>
              <textarea
                value={feedbackText}
                onChange={e => setFeedbackText(e.target.value)}
                placeholder={t("creative_feedback_placeholder")}
                rows={2}
                style={{
                  width: "100%", padding: 10, borderRadius: 8, border: `1px solid ${theme.border}`,
                  backgroundColor: theme.bg, color: theme.text, fontSize: 14, resize: "vertical",
                  boxSizing: "border-box", marginBottom: 8,
                }}
              />
              <button
                onClick={handleRequestChanges}
                disabled={feedbackSaving || !feedbackText.trim()}
                style={{
                  width: "100%", padding: "10px 16px", borderRadius: 10, border: "none",
                  backgroundColor: "#FF950022", color: "#FF9500", fontWeight: 600, fontSize: 14,
                  cursor: feedbackSaving ? "wait" : "pointer", opacity: feedbackSaving || !feedbackText.trim() ? 0.6 : 1,
                }}
              >
                {feedbackSaving ? "..." : t("creative_request_changes")}
              </button>
            </div>
          )}

          {/* Creative history */}
          {creativeHistory.length > 1 && (
            <details style={{ marginTop: 12 }}>
              <summary style={{ fontSize: 12, color: theme.textSecondary, cursor: "pointer" }}>
                {t("creative_history")} ({creativeHistory.length})
              </summary>
              {creativeHistory.filter(c => !c.is_current).map(c => (
                <div key={c.id} style={{ marginTop: 8, padding: 8, borderRadius: 6, backgroundColor: theme.bg, border: `1px solid ${theme.border}` }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ fontSize: 11, color: theme.textSecondary }}>v{c.version}</span>
                    <span style={{ fontSize: 11, color: theme.textSecondary }}>{c.status}</span>
                  </div>
                  <p style={{ fontSize: 13, color: theme.text, margin: "4px 0 0" }}>
                    {c.text.length > 100 ? c.text.slice(0, 100) + "..." : c.text}
                  </p>
                </div>
              ))}
            </details>
          )}
        </div>
      )}

      {/* Schedule Card */}
      {showScheduleCard && (
        <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: 16, marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: theme.text, margin: "0 0 12px" }}>{t("schedule_title")}</h3>

          {posting?.scheduled_at && (
            <InfoRow
              label={t("schedule_scheduled_at")}
              value={new Date(posting.scheduled_at).toLocaleString(undefined, { timeZone: user?.timezone || undefined })}
            />
          )}

          {/* Advertiser: waiting hint when no schedule yet */}
          {isAdvertiser && deal.status === "CREATIVE_APPROVED" && !posting?.scheduled_at && (
            <p style={{ fontSize: 13, color: theme.textSecondary, margin: "0 0 8px", lineHeight: 1.4 }}>
              {t("schedule_waiting_owner")}
            </p>
          )}

          {/* Owner: schedule form (CREATIVE_APPROVED only) */}
          {isOwner && deal.status === "CREATIVE_APPROVED" && !posting && (
            <div style={{ marginTop: 8 }}>
              <p style={{ fontSize: 12, color: theme.textSecondary, margin: "0 0 8px" }}>
                {t("profile_timezone")}: {user?.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone}
              </p>
              <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                <input
                  type="date"
                  value={scheduleDate}
                  min={new Date().toISOString().slice(0, 10)}
                  onChange={e => setScheduleDate(e.target.value)}
                  style={{
                    flex: 1, padding: 10, borderRadius: 8, border: `1px solid ${theme.border}`,
                    backgroundColor: theme.bg, color: theme.text, fontSize: 14, boxSizing: "border-box",
                  }}
                />
                <input
                  type="time"
                  value={scheduleTime}
                  onChange={e => setScheduleTime(e.target.value)}
                  style={{
                    width: 120, padding: 10, borderRadius: 8, border: `1px solid ${theme.border}`,
                    backgroundColor: theme.bg, color: theme.text, fontSize: 14, boxSizing: "border-box",
                  }}
                />
              </div>
              <button
                onClick={handleSchedulePost}
                disabled={scheduleSaving || !scheduleDate}
                style={{
                  width: "100%", padding: "10px 16px", borderRadius: 10, border: "none",
                  backgroundColor: "#5856D6", color: "#fff", fontWeight: 600, fontSize: 14,
                  cursor: scheduleSaving ? "wait" : "pointer", opacity: scheduleSaving || !scheduleDate ? 0.6 : 1,
                }}
              >
                {scheduleSaving ? "..." : t("schedule_post")}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Posting Card */}
      {showPostingCard && posting && (
        <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: 16, marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: theme.text, margin: "0 0 12px" }}>{t("posting_title")}</h3>
          {posting.posted_at && (
            <InfoRow label={t("posting_posted_at")} value={new Date(posting.posted_at).toLocaleString(undefined, { timeZone: user?.timezone || undefined })} />
          )}
          <InfoRow label={t("posting_retention_hours")} value={`${posting.retention_hours}h`} />
          {posting.verified_at && (
            <InfoRow label={t("posting_verified_at")} value={new Date(posting.verified_at).toLocaleString(undefined, { timeZone: user?.timezone || undefined })} />
          )}
          {posting.retained !== null && posting.retained !== undefined && (
            <div style={{
              marginTop: 8, padding: "6px 12px", borderRadius: 8,
              backgroundColor: posting.retained ? "#34C75922" : "#FF3B3022",
            }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: posting.retained ? "#34C759" : "#FF3B30" }}>
                {posting.retained ? t("posting_retained") : t("posting_not_retained")}
              </span>
            </div>
          )}
          {posting.verification_error && (
            <p style={{ fontSize: 12, color: "#FF3B30", margin: "8px 0 0" }}>{posting.verification_error}</p>
          )}
          {deal.status === "RETENTION_CHECK" && !posting.verified_at && posting.posted_at && (
            <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{
                padding: 12, borderRadius: 8,
                backgroundColor: "#FF950018", textAlign: "center",
              }}>
                <p style={{ fontSize: 13, fontWeight: 600, color: "#FF9500", margin: 0 }}>
                  {t("posting_retention_in_progress")}
                </p>
              </div>
              <button
                onClick={handleCheckRetention}
                disabled={retentionChecking}
                style={{
                  width: "100%", padding: "10px 16px", borderRadius: 10, border: "none",
                  backgroundColor: "#007AFF22", color: "#007AFF", fontWeight: 600, fontSize: 14,
                  cursor: retentionChecking ? "wait" : "pointer", opacity: retentionChecking ? 0.6 : 1,
                }}
              >
                {retentionChecking ? "..." : t("posting_check_now")}
              </button>
              {retentionMessage && (
                <p style={{ fontSize: 13, fontWeight: 600, color: retentionMessage.color, textAlign: "center", margin: 0 }}>
                  {retentionMessage.text}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Status explanation */}
      <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: 16, marginBottom: 16 }}>
        <span style={{ fontSize: 12, color: theme.textSecondary }}>{t("deal_status_hint")}</span>
        <p style={{ color: theme.text, fontSize: 14, margin: "6px 0 0", lineHeight: 1.4 }}>
          {t(`deal_status_${deal.status.toLowerCase()}`)}
        </p>
      </div>

      {/* Action buttons */}
      {genericActions.length > 0 && (
        <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: 16, marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: theme.text, margin: "0 0 12px" }}>{t("deal_actions_title")}</h3>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {genericActions.map(action => (
              <button
                key={action}
                onClick={() => handleAction(action)}
                disabled={actionLoading !== null || escrowCreating}
                style={{
                  padding: "8px 16px",
                  borderRadius: 10,
                  border: "none",
                  backgroundColor: (ACTION_COLORS[action] || theme.accent) + "22",
                  color: ACTION_COLORS[action] || theme.accent,
                  fontWeight: 600,
                  fontSize: 14,
                  cursor: actionLoading ? "wait" : "pointer",
                  opacity: actionLoading === action || (action === "request_escrow" && escrowCreating) ? 0.6 : 1,
                }}
              >
                {action === "request_escrow" && escrowCreating
                  ? t("escrow_creating")
                  : actionLoading === action
                    ? "..."
                    : t(`deal_action_${action}`)}
              </button>
            ))}
          </div>
          {actionError && (
            <p style={{ color: "#FF3B30", fontSize: 13, marginTop: 8, marginBottom: 0 }}>{actionError}</p>
          )}
        </div>
      )}

      {/* Bot messaging hint */}
      <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: 16 }}>
        <p style={{ color: theme.textSecondary, fontSize: 13, margin: 0, lineHeight: 1.4 }}>
          {t("deal_bot_messaging_hint")}
        </p>
      </div>
    </div>
  );
}

export default DealDetail;
