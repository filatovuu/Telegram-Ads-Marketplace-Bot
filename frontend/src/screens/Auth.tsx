import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";

function Auth() {
  const { t } = useTranslation();
  const { login, authenticated, loading, error } = useAuth();
  const theme = useTheme();
  const navigate = useNavigate();

  useEffect(() => {
    if (authenticated) {
      navigate("/home", { replace: true });
      return;
    }

    const tg = (window as unknown as Record<string, unknown>).Telegram as
      | { WebApp?: { initData?: string } }
      | undefined;

    const initData = tg?.WebApp?.initData;
    if (initData) {
      login(initData);
    }
  }, [authenticated, login, navigate]);

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "60vh" }}>
        <div style={{ textAlign: "center" }}>
          <div
            style={{
              width: 40,
              height: 40,
              border: `3px solid ${theme.bgSecondary}`,
              borderTopColor: theme.accent,
              borderRadius: "50%",
              animation: "spin 0.8s linear infinite",
              margin: "0 auto 16px",
            }}
          />
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          <p style={{ color: theme.textSecondary, fontSize: 15 }}>{t("loading")}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "60vh" }}>
        <div style={{ textAlign: "center", padding: "0 24px" }}>
          <p style={{ color: theme.danger, fontSize: 16, fontWeight: 600, marginBottom: 8 }}>
            {error}
          </p>
          <p style={{ color: theme.textSecondary, fontSize: 14 }}>
            {t("auth_open_in_telegram")}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "60vh" }}>
      <div style={{ textAlign: "center", padding: "0 24px" }}>
        <p style={{ fontSize: 48, marginBottom: 16 }}>{"\u{1F4AC}"}</p>
        <p style={{ color: theme.textSecondary, fontSize: 15, lineHeight: 1.5 }}>
          {t("auth_open_in_telegram")}
        </p>
      </div>
    </div>
  );
}

export default Auth;
