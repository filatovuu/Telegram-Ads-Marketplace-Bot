import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useTheme } from "@/context/ThemeContext";
import { useBackButton } from "@/hooks/useBackButton";
import { getCampaign, createCampaign, updateCampaign, deleteCampaign } from "@/api/campaigns";

function CampaignForm() {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  useBackButton(-1);
  const isEdit = Boolean(id);

  const [title, setTitle] = useState("");
  const [brief, setBrief] = useState("");
  const [category, setCategory] = useState("");
  const [targetLanguage, setTargetLanguage] = useState("");
  const [budgetMin, setBudgetMin] = useState("");
  const [budgetMax, setBudgetMax] = useState("");
  const [publishFrom, setPublishFrom] = useState("");
  const [publishTo, setPublishTo] = useState("");
  const [links, setLinks] = useState("");
  const [restrictions, setRestrictions] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!isEdit) return;
    try {
      const c = await getCampaign(Number(id));
      setTitle(c.title);
      setBrief(c.brief || "");
      setCategory(c.category || "");
      setTargetLanguage(c.target_language || "");
      setBudgetMin(Number(c.budget_min).toFixed(2));
      const maxVal = Number(c.budget_max);
      if (maxVal >= 999999999) {
        setBudgetMax("");
      } else {
        setBudgetMax(maxVal.toFixed(2));
      }
      setPublishFrom(c.publish_from ? c.publish_from.slice(0, 16) : "");
      setPublishTo(c.publish_to ? c.publish_to.slice(0, 16) : "");
      setLinks(c.links || "");
      setRestrictions(c.restrictions || "");
      setIsActive(c.is_active);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [id, isEdit]);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    if (!title.trim() || !brief.trim()) return;
    const parsedMin = budgetMin ? parseFloat(budgetMin) : 0.5;
    const parsedMax = budgetMax ? parseFloat(budgetMax) : 999999999;
    if (parsedMin < 0.5) {
      setError(t("listing_min_price_error", { min: "0.5" }));
      return;
    }
    if (parsedMax < parsedMin) {
      setError(t("campaign_budget_max_error"));
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const data = {
        title: title.trim(),
        brief: brief.trim() || undefined,
        category: category.trim() || undefined,
        target_language: targetLanguage || undefined,
        budget_min: parsedMin,
        budget_max: parsedMax,
        publish_from: publishFrom || undefined,
        publish_to: publishTo || undefined,
        links: links.trim() || undefined,
        restrictions: restrictions.trim() || undefined,
      };
      if (isEdit) {
        await updateCampaign(Number(id), { ...data, is_active: isActive });
      } else {
        await createCampaign(data);
      }
      navigate("/campaigns");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error"));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!isEdit) return;
    try {
      await deleteCampaign(Number(id));
      navigate("/campaigns");
    } catch {
      /* ignore */
    }
  };

  if (loading) {
    return <p style={{ textAlign: "center", paddingTop: 40, color: theme.textSecondary }}>{t("loading")}</p>;
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

  const splitDateTime = (value: string) => {
    // value: "2026-02-12T10:59"
    if (!value) return { date: "", time: "" };
  
    const [date, time] = value.split("T");
    return {
      date: date ?? "",
      time: time?.slice(0, 5) ?? "", // HH:mm
    };
  };
  
  const mergeDateTime = (date: string, time: string) => {
    if (!date) return "";
    if (!time) return `${date}T00:00`;
    return `${date}T${time}`;
  };

  return (
    <div style={{ paddingTop: 8, paddingBottom: 16 }}>

      <h2 style={{ fontSize: 20, fontWeight: 700, color: theme.text, marginBottom: 20 }}>
        {isEdit ? t("campaign_edit_title") : t("campaign_new_title")}
      </h2>

      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {/* Title */}
        <div>
          <label style={{ fontSize: 13, color: theme.textSecondary, display: "block", marginBottom: 6 }}>
            {t("campaign_title")} *
          </label>
          <input value={title} onChange={(e) => setTitle(e.target.value)} style={inputStyle} />
        </div>

        {/* Brief */}
        <div>
          <label style={{ fontSize: 13, color: theme.textSecondary, display: "block", marginBottom: 6 }}>
            {t("campaign_brief")} *
          </label>
          <textarea
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            rows={3}
            style={{ ...inputStyle, resize: "vertical" }}
          />
        </div>

        {/* Category + Language */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <div>
            <label style={{ fontSize: 13, color: theme.textSecondary, display: "block", marginBottom: 6 }}>
              {t("campaign_category")}
            </label>
            <select value={category} onChange={(e) => setCategory(e.target.value)} style={{ ...inputStyle, appearance: "auto" }}>
              <option value="">{t("filter_any")}</option>
              <option value="crypto">Crypto</option>
              <option value="finance">Finance</option>
              <option value="tech">Tech</option>
              <option value="lifestyle">Lifestyle</option>
              <option value="news">News</option>
              <option value="education">Education</option>
              <option value="entertainment">Entertainment</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div>
            <label style={{ fontSize: 13, color: theme.textSecondary, display: "block", marginBottom: 6 }}>
              {t("filter_language")}
            </label>
            <select value={targetLanguage} onChange={(e) => setTargetLanguage(e.target.value)} style={{ ...inputStyle, appearance: "auto" }}>
              <option value="">{t("filter_any")}</option>
              <option value="en">English</option>
              <option value="ru">Russian</option>
            </select>
          </div>
        </div>

        {/* Budget range */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <div>
            <label style={{ fontSize: 13, color: theme.textSecondary, display: "block", marginBottom: 6 }}>
              {t("campaign_budget_min")}
            </label>
            <input
              type="text"
              inputMode="decimal"
              placeholder={t("filter_any")}
              value={budgetMin}
              onChange={(e) => setBudgetMin(e.target.value.replace(",", "."))}
              style={inputStyle}
            />
          </div>
          <div>
            <label style={{ fontSize: 13, color: theme.textSecondary, display: "block", marginBottom: 6 }}>
              {t("campaign_budget_max")}
            </label>
            <input
              type="text"
              inputMode="decimal"
              placeholder={t("filter_any")}
              value={budgetMax}
              onChange={(e) => setBudgetMax(e.target.value.replace(",", "."))}
              style={inputStyle}
            />
          </div>
        </div>

        {/* Publish window */}
        <div style={{ minWidth: 0 }}>
          <label style={{ fontSize: 13, color: theme.textSecondary, display: "block", marginBottom: 6 }}>
            {t("campaign_publish_from")}
          </label>

          {(() => {
            const { date, time } = splitDateTime(publishFrom);

            return (
              <div style={{ display: "flex", gap: 10 }}>
                <input
                  type="date"
                  value={date}
                  onChange={(e) => setPublishFrom(mergeDateTime(e.target.value, time))}
                  style={{ ...inputStyle, flex: 1, minWidth: 0 }}
                />

                <input
                  type="time"
                  value={time}
                  onChange={(e) => setPublishFrom(mergeDateTime(date, e.target.value))}
                  style={{ ...inputStyle, width: 110 }}
                />
              </div>
            );
          })()}
        </div>

        <div style={{ minWidth: 0 }}>
          <label style={{ fontSize: 13, color: theme.textSecondary, display: "block", marginBottom: 6 }}>
            {t("campaign_publish_to")}
          </label>

          {(() => {
            const { date, time } = splitDateTime(publishTo);

            return (
              <div style={{ display: "flex", gap: 10 }}>
                <input
                  type="date"
                  value={date}
                  onChange={(e) => setPublishTo(mergeDateTime(e.target.value, time))}
                  style={{ ...inputStyle, flex: 1, minWidth: 0 }}
                />

                <input
                  type="time"
                  value={time}
                  onChange={(e) => setPublishTo(mergeDateTime(date, e.target.value))}
                  style={{ ...inputStyle, width: 110 }}
                />
              </div>
            );
          })()}
        </div>

        {/* Links */}
        <div>
          <label style={{ fontSize: 13, color: theme.textSecondary, display: "block", marginBottom: 6 }}>
            {t("campaign_links")}
          </label>
          <textarea
            value={links}
            onChange={(e) => setLinks(e.target.value)}
            rows={1}
            placeholder="https://..."
            style={{ ...inputStyle, resize: "vertical" }}
          />
        </div>

        {/* Restrictions */}
        <div>
          <label style={{ fontSize: 13, color: theme.textSecondary, display: "block", marginBottom: 6 }}>
            {t("campaign_restrictions")}
          </label>
          <textarea
            value={restrictions}
            onChange={(e) => setRestrictions(e.target.value)}
            rows={2}
            style={{ ...inputStyle, resize: "vertical" }}
          />
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
          disabled={saving || !title.trim() || !brief.trim()}
          style={{
            width: "100%",
            padding: "14px",
            fontSize: 16,
            fontWeight: 600,
            borderRadius: 12,
            border: "none",
            backgroundColor: theme.accent,
            color: "#fff",
            cursor: saving || !title.trim() || !brief.trim() ? "default" : "pointer",
            opacity: saving || !title.trim() || !brief.trim() ? 0.5 : 1,
          }}
        >
          {saving ? t("loading") : isEdit ? t("campaign_save") : t("campaign_create")}
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
            {t("campaign_delete")}
          </button>
        )}
      </div>
    </div>
  );
}

export default CampaignForm;
