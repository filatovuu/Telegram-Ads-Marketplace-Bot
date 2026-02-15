import { useTranslation } from "react-i18next";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { useBackButton } from "@/hooks/useBackButton";
import { useTonEscrow } from "@/hooks/useTonEscrow";

const LOCALES = [
  { code: "en" as const, label: "English" },
  { code: "ru" as const, label: "Русский" },
];

function getInitials(firstName?: string, lastName?: string, username?: string): string {
  if (firstName && lastName) return (firstName[0] + lastName[0]).toUpperCase();
  if (firstName) return firstName.slice(0, 2).toUpperCase();
  if (username) return username.slice(0, 2).toUpperCase();
  return "U";
}

function Profile() {
  const { t, i18n } = useTranslation();
  const { user, setLocale } = useAuth();
  const theme = useTheme();
  const { walletAddress, connected, connect, disconnect } = useTonEscrow();
  useBackButton(-1);

  if (!user) return null;

  const initials = getInitials(user.first_name ?? undefined, user.last_name ?? undefined, user.username ?? undefined);
  const fullName = [user.first_name, user.last_name].filter(Boolean).join(" ") || "User";

  const rows = [
    { label: t("profile_username"), value: user.username ? `@${user.username}` : "\u2014" },
    { label: "Telegram ID", value: String(user.telegram_id) },
  ];

  const handleLocaleChange = async (code: "en" | "ru") => {
    if (code === user.locale) return;
    await setLocale(code);
    i18n.changeLanguage(code);
  };

  const shortAddress = walletAddress
    ? walletAddress.slice(0, 6) + "\u2026" + walletAddress.slice(-4)
    : null;

  return (
    <div style={{ paddingTop: 8, paddingBottom: 24 }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", marginBottom: 28 }}>
        <div
          style={{
            width: 72,
            height: 72,
            borderRadius: "50%",
            background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            marginBottom: 12,
          }}
        >
          <span style={{ color: "#fff", fontSize: 24, fontWeight: 700 }}>{initials}</span>
        </div>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: theme.text }}>{fullName}</h2>
        {user.username && (
          <p style={{ color: theme.textSecondary, fontSize: 15, marginTop: 2 }}>
            @{user.username}
          </p>
        )}
      </div>

      <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 16, overflow: "hidden", marginBottom: 16 }}>
        {rows.map((row, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "14px 16px",
              borderBottom: i < rows.length - 1 ? `0.5px solid ${theme.border}` : "none",
            }}
          >
            <span style={{ color: theme.textSecondary, fontSize: 15 }}>{row.label}</span>
            <span style={{ fontSize: 15, fontWeight: 500, color: theme.text }}>{row.value}</span>
          </div>
        ))}
      </div>

      {/* Language section */}
      <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 16, overflow: "hidden", marginBottom: 16 }}>
        <div style={{ padding: "14px 16px", borderBottom: `0.5px solid ${theme.border}` }}>
          <span style={{ color: theme.textSecondary, fontSize: 13, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
            {t("profile_locale")}
          </span>
        </div>
        <div style={{ display: "flex", gap: 8, padding: "12px 16px" }}>
          {LOCALES.map((loc) => (
            <button
              key={loc.code}
              onClick={() => handleLocaleChange(loc.code)}
              style={{
                flex: 1,
                padding: "10px 16px",
                borderRadius: 10,
                border: user.locale === loc.code ? `2px solid ${theme.accent}` : `1px solid ${theme.border}`,
                backgroundColor: user.locale === loc.code ? `${theme.accent}18` : "transparent",
                color: user.locale === loc.code ? theme.accent : theme.text,
                fontWeight: 600,
                fontSize: 14,
                cursor: "pointer",
              }}
            >
              {loc.label}
            </button>
          ))}
        </div>
      </div>

      {/* TON Wallet section */}
      <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 16, overflow: "hidden" }}>
        <div style={{ padding: "14px 16px", borderBottom: `0.5px solid ${theme.border}` }}>
          <span style={{ color: theme.textSecondary, fontSize: 13, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
            {t("profile_wallet_section")}
          </span>
        </div>

        {connected && shortAddress ? (
          <>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "14px 16px",
                borderBottom: `0.5px solid ${theme.border}`,
              }}
            >
              <span style={{ color: theme.textSecondary, fontSize: 15 }}>{t("wallet_address")}</span>
              <span style={{ fontSize: 15, fontWeight: 500, color: theme.accent }}>{shortAddress}</span>
            </div>
            <div style={{ padding: "12px 16px" }}>
              <button
                onClick={disconnect}
                style={{
                  width: "100%",
                  padding: "10px 16px",
                  borderRadius: 10,
                  border: "none",
                  backgroundColor: "#FF3B3018",
                  color: "#FF3B30",
                  fontWeight: 600,
                  fontSize: 14,
                  cursor: "pointer",
                }}
              >
                {t("profile_wallet_disconnect")}
              </button>
            </div>
          </>
        ) : (
          <div style={{ padding: "12px 16px" }}>
            <p style={{ color: theme.textSecondary, fontSize: 13, margin: "0 0 10px" }}>
              {t("profile_wallet_hint")}
            </p>
            <button
              onClick={connect}
              style={{
                width: "100%",
                padding: "10px 16px",
                borderRadius: 10,
                border: "none",
                backgroundColor: theme.accent,
                color: "#fff",
                fontWeight: 600,
                fontSize: 14,
                cursor: "pointer",
              }}
            >
              {t("profile_wallet_connect")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default Profile;
