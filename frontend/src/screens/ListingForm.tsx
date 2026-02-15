import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useTheme } from "@/context/ThemeContext";
import { useBackButton } from "@/hooks/useBackButton";
import { getMyChannels } from "@/api/channels";
import { createListing, updateListing, deleteListing, getMyListings, getPlatformConfig } from "@/api/listings";
import type { Channel, Listing } from "@/api/types";

function ListingForm() {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  useBackButton(-1);
  const isEdit = Boolean(id);
  const preselectedChannel = searchParams.get("channel");

  const [channels, setChannels] = useState<Channel[]>([]);
  const [channelId, setChannelId] = useState<number>(0);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [payout, setPayout] = useState("");
  const [editingField, setEditingField] = useState<"price" | "payout">("price");
  const [format, setFormat] = useState("post");

  // Fee config from backend
  const [feePct, setFeePct] = useState(10);
  const [gasTon, setGasTon] = useState(0.1);
  const [minPrice, setMinPrice] = useState(0.5);

  const calcPayout = (p: number) => Math.max(0, p * (1 - feePct / 100) - gasTon);
  const calcPrice = (pay: number) => (pay + gasTon) / (1 - feePct / 100);
  const [isActive, setIsActive] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [chs, cfg] = await Promise.all([getMyChannels(), getPlatformConfig()]);
      setFeePct(cfg.platform_fee_percent);
      setGasTon(cfg.escrow_gas_ton);
      setMinPrice(cfg.min_price_ton);
      setChannels(chs);
      if (!isEdit && chs.length > 0) {
        const pre = preselectedChannel ? Number(preselectedChannel) : 0;
        const match = pre && chs.find((ch) => ch.id === pre);
        setChannelId(match ? match.id : chs[0].id);
      }

      if (isEdit) {
        const listings = await getMyListings();
        const existing = listings.find((l: Listing) => l.id === Number(id));
        if (existing) {
          setChannelId(existing.channel_id);
          setTitle(existing.title);
          setDescription(existing.description || "");
          setPrice(Number(existing.price).toFixed(2));
          setPayout(calcPayout(existing.price).toFixed(2));
          setFormat(existing.format);
          setIsActive(existing.is_active);
        }
      }
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [id, isEdit, preselectedChannel]);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    if (!title.trim() || !price.trim() || !channelId) return;
    setSaving(true);
    setError(null);
    try {
      if (isEdit) {
        await updateListing(Number(id), {
          title: title.trim(),
          description: description.trim() || undefined,
          price: parseFloat(price),
          format,
          is_active: isActive,
        });
      } else {
        await createListing({
          channel_id: channelId,
          title: title.trim(),
          description: description.trim() || undefined,
          price: parseFloat(price),
          format,
        });
      }
      navigate("/listings");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error"));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!isEdit) return;
    try {
      await deleteListing(Number(id));
      navigate("/listings");
    } catch {
      /* ignore */
    }
  };

  if (loading) {
    return <p style={{ textAlign: "center", paddingTop: 40, color: theme.textSecondary }}>{t("loading")}</p>;
  }

  if (!isEdit && channels.length === 0) {
    return (
      <div style={{ paddingTop: 8, paddingBottom: 16 }}>
        <div style={{
          backgroundColor: theme.bgSecondary,
          borderRadius: 14,
          padding: 24,
          textAlign: "center",
        }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: theme.text, marginBottom: 8 }}>
            {t("listing_no_channels_title")}
          </h2>
          <p style={{ color: theme.textSecondary, fontSize: 14, lineHeight: 1.5, marginBottom: 20 }}>
            {t("listing_no_channels_hint")}
          </p>
          <button
            onClick={() => navigate("/channels/add")}
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
            }}
          >
            {t("action_add_channel")}
          </button>
        </div>
      </div>
    );
  }

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "12px 14px",
    fontSize: 15,
    borderRadius: 10,
    border: `1px solid ${theme.border}`,
    backgroundColor: theme.bgSecondary,
    color: theme.text,
    outline: "none",
    boxSizing: "border-box",
  };

  return (
    <div style={{ paddingTop: 8, paddingBottom: 16 }}>

      <h2 style={{ fontSize: 20, fontWeight: 700, color: theme.text, marginBottom: 20 }}>
        {isEdit ? t("listing_edit_title") : t("listing_new_title")}
      </h2>

      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {/* Channel selector */}
        {!isEdit && (
          <div>
            <label style={{ fontSize: 13, color: theme.textSecondary, display: "block", marginBottom: 6 }}>
              {t("listing_channel")}
            </label>
            <select
              value={channelId}
              onChange={(e) => setChannelId(Number(e.target.value))}
              style={{ ...inputStyle, appearance: "auto" }}
            >
              {channels.map((ch) => (
                <option key={ch.id} value={ch.id}>{ch.title}</option>
              ))}
            </select>
          </div>
        )}

        {/* Title */}
        <div>
          <label style={{ fontSize: 13, color: theme.textSecondary, display: "block", marginBottom: 6 }}>
            {t("listing_title")}
          </label>
          <input value={title} onChange={(e) => setTitle(e.target.value)} style={inputStyle} />
        </div>

        {/* Description */}
        <div>
          <label style={{ fontSize: 13, color: theme.textSecondary, display: "block", marginBottom: 6 }}>
            {t("listing_description")}
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            style={{ ...inputStyle, resize: "vertical" }}
          />
        </div>

        {/* Price */}
        <div>
          <label style={{ fontSize: 13, color: theme.textSecondary, display: "block", marginBottom: 6 }}>
            {t("listing_price")}
          </label>
          <input
            type="text"
            inputMode="decimal"
            value={price}
            onChange={(e) => {
              const v = e.target.value.replace(",", ".");
              setPrice(v);
              setEditingField("price");
              const n = parseFloat(v);
              setPayout(n > 0 ? calcPayout(n).toFixed(2) : "");
            }}
            style={{
              ...inputStyle,
              borderColor: editingField === "price" && price ? theme.accent : theme.border,
            }}
          />
        </div>

        {/* Payout */}
        <div>
          <label style={{ fontSize: 13, color: theme.textSecondary, display: "block", marginBottom: 6 }}>
            {t("listing_payout")}
          </label>
          <input
            type="text"
            inputMode="decimal"
            value={payout}
            onChange={(e) => {
              const v = e.target.value.replace(",", ".");
              setPayout(v);
              setEditingField("payout");
              const n = parseFloat(v);
              setPrice(n > 0 ? calcPrice(n).toFixed(2) : "");
            }}
            style={{
              ...inputStyle,
              borderColor: editingField === "payout" && payout ? theme.accent : theme.border,
            }}
          />
        </div>

        {/* Min price warning */}
        {price && parseFloat(price) > 0 && parseFloat(price) < minPrice && (
          <p style={{ color: "#FF3B30", fontSize: 13, fontWeight: 600, margin: 0 }}>
            {t("listing_min_price_error", { min: minPrice })}
          </p>
        )}

        {/* Fee breakdown */}
        {price && parseFloat(price) >= minPrice && (
          <div style={{
            backgroundColor: theme.bgSecondary,
            borderRadius: 10,
            padding: "12px 14px",
          }}>
            <p style={{ fontSize: 12, color: theme.textSecondary, margin: "0 0 8px" }}>
              {t("listing_price_hint")}
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                <span style={{ color: theme.textSecondary }}>{t("listing_advertiser_pays")}</span>
                <span style={{ color: theme.text, fontWeight: 600 }}>{parseFloat(price).toFixed(2)} TON</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                <span style={{ color: theme.textSecondary }}>{t("listing_platform_fee", { percent: feePct })}</span>
                <span style={{ color: "#FF3B30" }}>-{(parseFloat(price) * feePct / 100).toFixed(2)} TON</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                <span style={{ color: theme.textSecondary }}>{t("listing_gas")}</span>
                <span style={{ color: "#FF3B30" }}>~{gasTon} TON</span>
              </div>
              <div style={{ borderTop: `1px solid ${theme.border}`, paddingTop: 6, display: "flex", justifyContent: "space-between", fontSize: 14 }}>
                <span style={{ color: theme.text, fontWeight: 600 }}>{t("listing_you_receive")}</span>
                <span style={{ color: "#34C759", fontWeight: 700 }}>~{calcPayout(parseFloat(price)).toFixed(2)} TON</span>
              </div>
            </div>
          </div>
        )}

        {/* Format */}
        <div>
          <label style={{ fontSize: 13, color: theme.textSecondary, display: "block", marginBottom: 6 }}>
            {t("listing_format")}
          </label>
          <select value={format} onChange={(e) => setFormat(e.target.value)} style={{ ...inputStyle, appearance: "auto" }}>
            <option value="post">{t("format_post")}</option>
            <option value="repost">{t("format_repost")}</option>
            <option value="story">{t("format_story")}</option>
          </select>
        </div>

        {/* Active toggle (edit only) */}
        {isEdit && (
          <label style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 14, color: theme.text }}>
            <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
            {t("listing_is_active")}
          </label>
        )}

        {error && <p style={{ color: theme.danger, fontSize: 13 }}>{error}</p>}

        <button
          onClick={handleSave}
          disabled={saving || !title.trim() || !price.trim() || parseFloat(price) < minPrice}
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
            opacity: saving ? 0.5 : 1,
          }}
        >
          {saving ? t("loading") : isEdit ? t("listing_save") : t("listing_create")}
        </button>

        {isEdit && (
          <button
            onClick={handleDelete}
            style={{
              width: "100%",
              padding: "14px",
              fontSize: 16,
              fontWeight: 600,
              borderRadius: 12,
              border: "none",
              backgroundColor: theme.danger,
              color: "#fff",
              cursor: "pointer",
            }}
          >
            {t("listing_delete")}
          </button>
        )}
      </div>
    </div>
  );
}

export default ListingForm;
