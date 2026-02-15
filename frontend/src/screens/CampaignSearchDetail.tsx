import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useTheme } from "@/context/ThemeContext";
import { useBackButton } from "@/hooks/useBackButton";
import { getMarketCampaign } from "@/api/campaigns";
import { getMyListings } from "@/api/listings";
import { createOwnerDeal } from "@/api/deals";
import type { CampaignPublic, Listing } from "@/api/types";

function CampaignSearchDetail() {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  useBackButton(-1);
  const [campaign, setCampaign] = useState<CampaignPublic | null>(null);
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [selectedListingId, setSelectedListingId] = useState<number | null>(null);
  const [price, setPrice] = useState("");
  const [brief, setBrief] = useState("");

  const load = useCallback(async () => {
    try {
      const [c, myListings] = await Promise.all([
        getMarketCampaign(Number(id)),
        getMyListings(),
      ]);
      setCampaign(c);
      const active = myListings.filter((l) => l.is_active);
      setListings(active);
      if (active.length > 0) setSelectedListingId(active[0].id);
      setPrice(Number(c.budget_min).toFixed(2));
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const handlePropose = async () => {
    if (!campaign || !selectedListingId) return;
    setCreating(true);
    setError(null);
    try {
      const deal = await createOwnerDeal({
        campaign_id: campaign.id,
        listing_id: selectedListingId,
        price: Math.round(Number(price) * 100) / 100,
        brief: brief || undefined,
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

  if (!campaign) {
    return <p style={{ textAlign: "center", paddingTop: 40, color: theme.textSecondary }}>{t("campaign_not_found")}</p>;
  }

  const priceNum = Number(price);
  const priceValid = !isNaN(priceNum) && priceNum >= Number(campaign.budget_min) && priceNum <= Number(campaign.budget_max);

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "10px 12px",
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
      <h2 style={{ fontSize: 20, fontWeight: 700, color: theme.text, marginBottom: 4 }}>
        {campaign.title}
      </h2>

      {/* Badges */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 16 }}>
        {campaign.category && (
          <span style={{
            fontSize: 12,
            fontWeight: 600,
            color: theme.accent,
            backgroundColor: `${theme.accent}15`,
            borderRadius: 6,
            padding: "3px 10px",
          }}>
            {campaign.category}
          </span>
        )}
        {campaign.target_language && (
          <span style={{
            fontSize: 12,
            fontWeight: 600,
            color: theme.textSecondary,
            backgroundColor: theme.bgTertiary,
            borderRadius: 6,
            padding: "3px 10px",
          }}>
            {campaign.target_language.toUpperCase()}
          </span>
        )}
      </div>

      {/* Campaign details */}
      <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: "14px 16px", marginBottom: 16 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <div>
            <span style={{ fontSize: 12, color: theme.textSecondary }}>{t("campaign_budget_min")}</span>
            <p style={{ fontWeight: 600, fontSize: 15, color: theme.text, margin: "4px 0 0" }}>{Number(campaign.budget_min).toFixed(2)} TON</p>
          </div>
          <div>
            <span style={{ fontSize: 12, color: theme.textSecondary }}>{t("campaign_budget_max")}</span>
            <p style={{ fontWeight: 600, fontSize: 15, color: theme.text, margin: "4px 0 0" }}>{Number(campaign.budget_max).toFixed(2)} TON</p>
          </div>
          {campaign.publish_from && (
            <div>
              <span style={{ fontSize: 12, color: theme.textSecondary }}>{t("campaign_publish_from")}</span>
              <p style={{ fontWeight: 600, fontSize: 14, color: theme.text, margin: "4px 0 0" }}>{new Date(campaign.publish_from).toLocaleDateString()}</p>
            </div>
          )}
          {campaign.publish_to && (
            <div>
              <span style={{ fontSize: 12, color: theme.textSecondary }}>{t("campaign_publish_to")}</span>
              <p style={{ fontWeight: 600, fontSize: 14, color: theme.text, margin: "4px 0 0" }}>{new Date(campaign.publish_to).toLocaleDateString()}</p>
            </div>
          )}
        </div>
      </div>

      {/* Brief */}
      {campaign.brief && (
        <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: "14px 16px", marginBottom: 16 }}>
          <span style={{ fontSize: 12, color: theme.textSecondary }}>{t("campaign_brief")}</span>
          <p style={{ color: theme.text, fontSize: 14, margin: "6px 0 0", lineHeight: 1.4 }}>{campaign.brief}</p>
        </div>
      )}

      {/* Restrictions */}
      {campaign.restrictions && (
        <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: "14px 16px", marginBottom: 16 }}>
          <span style={{ fontSize: 12, color: theme.textSecondary }}>{t("campaign_restrictions")}</span>
          <p style={{ color: theme.text, fontSize: 14, margin: "6px 0 0", lineHeight: 1.4 }}>{campaign.restrictions}</p>
        </div>
      )}

      {/* Proposal form */}
      <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: "14px 16px", marginBottom: 16 }}>
        <h3 style={{ fontSize: 16, fontWeight: 700, color: theme.text, margin: "0 0 14px" }}>{t("campaign_proposal_title")}</h3>

        {listings.length === 0 ? (
          <p style={{ color: theme.textSecondary, fontSize: 13 }}>{t("campaign_no_listings")}</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label style={{ fontSize: 12, color: theme.textSecondary, display: "block", marginBottom: 4 }}>{t("campaign_select_listing")}</label>
              <select
                value={selectedListingId ?? ""}
                onChange={(e) => setSelectedListingId(Number(e.target.value))}
                style={{ ...inputStyle, appearance: "auto" }}
              >
                {listings.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.title} ({l.channel.title})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ fontSize: 12, color: theme.textSecondary, display: "block", marginBottom: 4 }}>
                {t("campaign_proposal_price")} ({Number(campaign.budget_min).toFixed(2)} &ndash; {Number(campaign.budget_max).toFixed(2)} TON)
              </label>
              <input
                type="text"
                inputMode="decimal"
                value={price}
                onChange={(e) => setPrice(e.target.value.replace(",", "."))}
                onBlur={() => { const n = parseFloat(price); if (!isNaN(n)) setPrice(n.toFixed(2)); }}
                style={{
                  ...inputStyle,
                  borderColor: price && !priceValid ? theme.danger : theme.border,
                }}
              />
              {price && !priceValid && (
                <p style={{ color: theme.danger, fontSize: 12, marginTop: 4 }}>{t("campaign_price_range_error")}</p>
              )}
            </div>

            <div>
              <label style={{ fontSize: 12, color: theme.textSecondary, display: "block", marginBottom: 4 }}>{t("campaign_proposal_note")}</label>
              <textarea
                value={brief}
                onChange={(e) => setBrief(e.target.value)}
                placeholder={t("campaign_proposal_note_placeholder")}
                rows={3}
                style={{ ...inputStyle, resize: "vertical" }}
              />
            </div>
          </div>
        )}
      </div>

      {error && <p style={{ color: theme.danger, fontSize: 13, marginBottom: 12 }}>{error}</p>}

      {listings.length > 0 && (
        <button
          onClick={handlePropose}
          disabled={creating || !priceValid || !selectedListingId}
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
            opacity: creating || !priceValid || !selectedListingId ? 0.5 : 1,
          }}
        >
          {creating ? t("loading") : t("campaign_propose_deal")}
        </button>
      )}
    </div>
  );
}

export default CampaignSearchDetail;
