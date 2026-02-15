import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import type { Role } from "@/api/types";

function getInitials(firstName?: string, lastName?: string, username?: string): string {
  if (firstName && lastName) {
    return (firstName[0] + lastName[0]).toUpperCase();
  }
  if (firstName) return firstName.slice(0, 2).toUpperCase();
  if (username) return username.slice(0, 2).toUpperCase();
  return "U";
}

function TopBar() {
  const { t } = useTranslation();
  const { user, setRole, authenticated } = useAuth();
  const theme = useTheme();
  const navigate = useNavigate();

  if (!authenticated || !user) return null;

  const initials = getInitials(user.first_name ?? undefined, user.last_name ?? undefined, user.username ?? undefined);
  const activeRole = user.active_role;

  const handleRoleSwitch = async (role: Role) => {
    if (role !== activeRole) {
      await setRole(role);
      navigate("/deals", { replace: true });
    }
  };

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "10px 16px",
        paddingTop: "calc(env(safe-area-inset-top, 0px) + 10px)",
      }}
    >
      {/* Avatar */}
      <button
        onClick={() => navigate("/profile")}
        style={{
          width: 36,
          height: 36,
          borderRadius: "50%",
          background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
          border: "none",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          flexShrink: 0,
          WebkitTapHighlightColor: "transparent",
        }}
      >
        <span style={{ color: "#fff", fontSize: 13, fontWeight: 700, letterSpacing: "0.5px" }}>
          {initials}
        </span>
      </button>

      {/* Segmented Control */}
      <div
        style={{
          display: "flex",
          backgroundColor: theme.segmentBg,
          borderRadius: 20,
          padding: 3,
          gap: 2,
        }}
      >
        {(["owner", "advertiser"] as Role[]).map((role) => (
          <button
            key={role}
            onClick={() => handleRoleSwitch(role)}
            style={{
              padding: "7px 16px",
              borderRadius: 18,
              border: "none",
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
              transition: "all 0.2s ease",
              backgroundColor: activeRole === role ? theme.segmentActive : "transparent",
              color: activeRole === role ? theme.text : theme.textSecondary,
              WebkitTapHighlightColor: "transparent",
            }}
          >
            {role === "owner" ? t("role_owner_short") : t("role_advertiser_short")}
          </button>
        ))}
      </div>

      <div style={{ width: 36, flexShrink: 0 }} />
    </div>
  );
}

export default TopBar;
