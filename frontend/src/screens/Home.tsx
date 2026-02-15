import { useTranslation } from "react-i18next";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";

function Home() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const theme = useTheme();

  if (!user) return null;

  const isOwner = user.active_role === "owner";

  const actions = isOwner
    ? [
        { icon: "\u{1F4E2}", label: t("action_add_channel") },
        { icon: "\u{1F4CB}", label: t("action_create_listing") },
        { icon: "\u{1F4CA}", label: t("action_view_stats") },
        { icon: "\u{1F91D}", label: t("action_my_deals") },
      ]
    : [
        { icon: "\u{1F50D}", label: t("action_find_channels") },
        { icon: "\u{1F4CB}", label: t("action_new_campaign") },
        { icon: "\u{1F91D}", label: t("action_my_deals") },
        { icon: "\u{1F4B0}", label: t("action_escrow") },
      ];

  return (
    <div style={{ paddingTop: 8, paddingBottom: 16 }}>
      <div style={{ textAlign: "center", marginBottom: 24 }}>
        <p style={{ color: theme.textSecondary, fontSize: 14, marginBottom: 4 }}>
          {t("welcome_back")}
        </p>
        <h1 style={{ fontSize: 28, fontWeight: 700, letterSpacing: "-0.5px", color: theme.text }}>
          {user.first_name || user.username || "User"}
        </h1>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10, marginBottom: 20 }}>
        {actions.map((action, i) => (
          <button
            key={i}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              padding: "18px 12px",
              backgroundColor: theme.bgSecondary,
              borderRadius: 16,
              border: "none",
              cursor: "pointer",
              color: theme.text,
              WebkitTapHighlightColor: "transparent",
            }}
          >
            <span style={{ fontSize: 28 }}>{action.icon}</span>
            <span style={{ fontSize: 13, fontWeight: 500, color: theme.textSecondary }}>
              {action.label}
            </span>
          </button>
        ))}
      </div>

      <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 16, padding: "16px 20px" }}>
        <p style={{ color: theme.textSecondary, fontSize: 14, lineHeight: 1.5 }}>
          {isOwner ? t("home_owner_hint") : t("home_advertiser_hint")}
        </p>
      </div>
    </div>
  );
}

export default Home;
