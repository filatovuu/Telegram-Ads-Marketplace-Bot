import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useTheme } from "@/context/ThemeContext";
import { useBackButton } from "@/hooks/useBackButton";
import { useAuth } from "@/context/AuthContext";
import { useTonEscrow } from "@/hooks/useTonEscrow";
import { addChannel, getMyChannels } from "@/api/channels";
import type { Channel } from "@/api/types";

type Step = "intro" | "waiting" | "success" | "timeout" | "manual";

const webApp = window.Telegram?.WebApp;

const BOT_USERNAME = import.meta.env.VITE_BOT_USERNAME || "";
const ADMIN_RIGHTS = "post_messages+edit_messages+delete_messages+change_info+manage_chat";
const DEEP_LINK = `https://t.me/${BOT_USERNAME}?startchannel=&admin=${ADMIN_RIGHTS}`;
const POLL_INTERVAL = 1500;
const POLL_TIMEOUT = 120_000;
const STORAGE_KEY = "add_channel_pending";

interface PendingState {
  knownIds: number[];
  startedAt: number;
}

function savePending(knownIds: number[]) {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ knownIds, startedAt: Date.now() } satisfies PendingState),
  );
}

function loadPending(): PendingState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as PendingState;
    if (Date.now() - data.startedAt > POLL_TIMEOUT) {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return data;
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

function clearPending() {
  localStorage.removeItem(STORAGE_KEY);
}

function AddChannel() {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { connected, connect } = useTonEscrow();
  const hasWallet = !!user?.wallet_address || connected;
  useBackButton(-1);

  const pending = loadPending();
  const [step, setStep] = useState<Step>(pending ? "waiting" : "intro");
  const [newChannel, setNewChannel] = useState<Channel | null>(null);
  const [username, setUsername] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const knownIdsRef = useRef<Set<number>>(new Set(pending?.knownIds ?? []));
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  const checkForNewChannel = useCallback(async () => {
    try {
      const channels = await getMyChannels();
      const added = channels.find(
        (ch) => !knownIdsRef.current.has(ch.id),
      );
      if (added) {
        stopPolling();
        clearPending();
        setNewChannel(added);
        setStep("success");
      }
    } catch {}
  }, [stopPolling]);

  const startPolling = useCallback(
    (remainingMs: number) => {
      pollTimerRef.current = setInterval(checkForNewChannel, POLL_INTERVAL);

      timeoutRef.current = setTimeout(() => {
        stopPolling();
        clearPending();
        setStep("timeout");
      }, remainingMs);
    },
    [checkForNewChannel, stopPolling],
  );

  useEffect(() => {
    if (pending) {
      const elapsed = Date.now() - pending.startedAt;
      const remaining = Math.max(POLL_TIMEOUT - elapsed, 2000);
      startPolling(remaining);
    }
    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleConnect = async () => {
    let ids: number[] = [];
    try {
      const channels = await getMyChannels();
      ids = channels.map((ch) => ch.id);
    } catch {}
    knownIdsRef.current = new Set(ids);
    savePending(ids);
    setStep("waiting");
    startPolling(POLL_TIMEOUT);

    webApp?.openTelegramLink(DEEP_LINK);
  };

  const handleManualSubmit = async () => {
    if (!username.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const ch = await addChannel(username.trim());
      stopPolling();
      clearPending();
      setNewChannel(ch);
      setStep("success");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error"));
    } finally {
      setSubmitting(false);
    }
  };

  const handleRetry = () => {
    stopPolling();
    clearPending();
    setNewChannel(null);
    setError(null);
    setUsername("");
    setStep("intro");
  };

  const handleDone = () => {
    navigate("/channels");
  };

  const stepIndex = { intro: 0, waiting: 1, success: 2, timeout: 1, manual: 1 };

  const btnStyle = (active: boolean) => ({
    width: "100%",
    padding: "14px",
    fontSize: 16,
    fontWeight: 600 as const,
    borderRadius: 12,
    border: "none" as const,
    backgroundColor: active ? theme.accent : theme.bgTertiary,
    color: active ? "#fff" : theme.textSecondary,
    cursor: active ? "pointer" : ("default" as const),
  });

  return (
    <div style={{ paddingTop: 8, paddingBottom: 16 }}>
      <h2 style={{ fontSize: 20, fontWeight: 700, color: theme.text, marginBottom: 20 }}>
        {t("add_channel_title")}
      </h2>

      {/* Progress bar */}
      <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: 4,
              borderRadius: 2,
              backgroundColor: i <= stepIndex[step] ? theme.accent : theme.bgTertiary,
            }}
          />
        ))}
      </div>

      {/* === WALLET GATE === */}
      {!hasWallet && (step === "intro" || step === "manual") && (
        <div style={{
          backgroundColor: "#FF950015",
          borderRadius: 14,
          padding: 16,
          marginBottom: 16,
          border: "1px solid #FF950044",
        }}>
          <p style={{ fontSize: 14, color: theme.text, margin: "0 0 12px", lineHeight: 1.5 }}>
            {t("wallet_required_channel")}
          </p>
          <p style={{ fontSize: 13, color: theme.textSecondary, margin: "0 0 12px", lineHeight: 1.4 }}>
            {t("profile_wallet_hint")}
          </p>
          {!connected ? (
            <button
              onClick={connect}
              style={{
                width: "100%",
                padding: 14,
                fontSize: 16,
                fontWeight: 600,
                borderRadius: 12,
                border: "none",
                backgroundColor: theme.accent,
                color: "#fff",
                cursor: "pointer",
              }}
            >
              {t("profile_wallet_connect")}
            </button>
          ) : (
            <p style={{ fontSize: 13, color: "#34C759", fontWeight: 600, margin: 0 }}>
              {t("escrow_wallet_connected")}
            </p>
          )}
        </div>
      )}

      {/* === INTRO === */}
      {step === "intro" && (
        <div>
          <p style={{ fontSize: 15, color: theme.textSecondary, lineHeight: 1.5, marginBottom: 24 }}>
            {t("add_channel_deep_link_hint")}
          </p>
          <button onClick={handleConnect} disabled={!hasWallet} style={btnStyle(hasWallet)}>
            {t("add_channel_connect")}
          </button>

          {/* Manual fallback link */}
          <button
            onClick={() => setStep("manual")}
            style={{
              background: "none",
              border: "none",
              color: theme.accent,
              fontSize: 14,
              cursor: "pointer",
              marginTop: 16,
              padding: 0,
              width: "100%",
              textAlign: "center",
            }}
          >
            {t("add_channel_manual_link")}
          </button>
        </div>
      )}

      {/* === WAITING === */}
      {step === "waiting" && (
        <div style={{ textAlign: "center", paddingTop: 40 }}>
          <p style={{ color: theme.text, fontSize: 16, fontWeight: 600, marginBottom: 8 }}>
            {t("add_channel_waiting")}
          </p>
          <p style={{ color: theme.textSecondary, fontSize: 14 }}>
            {t("add_channel_waiting_hint")}
          </p>
        </div>
      )}

      {/* === SUCCESS === */}
      {step === "success" && newChannel && (
        <div>
          <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: 16, marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
              <div style={{
                width: 48,
                height: 48,
                borderRadius: "50%",
                backgroundColor: theme.accent,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}>
                <span style={{ color: "#fff", fontSize: 22, fontWeight: 700 }}>
                  {newChannel.title.charAt(0).toUpperCase()}
                </span>
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: 18, color: theme.text }}>
                  {newChannel.title}
                </div>
                {newChannel.username && (
                  <div style={{ color: theme.textSecondary, fontSize: 14 }}>
                    @{newChannel.username}
                  </div>
                )}
              </div>
            </div>
            {newChannel.description && (
              <p style={{
                color: theme.textSecondary,
                fontSize: 14,
                lineHeight: 1.4,
                margin: "0 0 12px",
                display: "-webkit-box",
                WebkitLineClamp: 3,
                WebkitBoxOrient: "vertical",
                overflow: "hidden",
              }}>
                {newChannel.description}
              </p>
            )}
            <div style={{ backgroundColor: theme.bgTertiary, borderRadius: 10, padding: "10px 12px" }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: theme.text }}>
                {newChannel.subscribers.toLocaleString()}
              </div>
              <div style={{ fontSize: 12, color: theme.textSecondary }}>
                {t("channel_subscribers")}
              </div>
            </div>
          </div>
          <button onClick={handleDone} style={btnStyle(true)}>
            {t("add_channel_done")}
          </button>
        </div>
      )}

      {/* === TIMEOUT / MANUAL === */}
      {(step === "timeout" || step === "manual") && (
        <div>
          <p style={{ color: theme.danger, fontSize: 15, marginBottom: 16, textAlign: "center" }}>
            {t("add_channel_timeout")}
          </p>

          <div style={{
            backgroundColor: "#FF950015",
            border: "1px solid #FF950044",
            borderRadius: 12,
            padding: "12px 14px",
            marginBottom: 16,
          }}>
            <p style={{ color: theme.text, fontSize: 13, lineHeight: 1.5, margin: 0 }}>
              {t("add_channel_manual_admin_warning")}
            </p>
          </div>

          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="@channel_name"
            style={{
              width: "100%",
              padding: "12px 14px",
              fontSize: 16,
              borderRadius: 12,
              border: `1px solid ${theme.border}`,
              backgroundColor: theme.bgSecondary,
              color: theme.text,
              outline: "none",
              boxSizing: "border-box",
            }}
          />
          {error && (
            <p style={{ color: theme.danger, fontSize: 13, marginTop: 8 }}>{error}</p>
          )}
          <button
            onClick={handleManualSubmit}
            disabled={!username.trim() || submitting || !hasWallet}
            style={{ ...btnStyle(!!username.trim() && !submitting && hasWallet), marginTop: 16 }}
          >
            {submitting ? t("loading") : t("add_channel_manual_connect")}
          </button>
          <button
            onClick={handleRetry}
            style={{
              background: "none",
              border: "none",
              color: theme.accent,
              fontSize: 14,
              cursor: "pointer",
              marginTop: 16,
              padding: 0,
              width: "100%",
              textAlign: "center",
            }}
          >
            {t("add_channel_retry")}
          </button>
        </div>
      )}
    </div>
  );
}

export default AddChannel;
