import { useTranslation } from "react-i18next";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";

interface Tab {
  label: string;
  path: string;
  icon: string;
}

const ADVERTISER_TABS: Tab[] = [
  { label: "nav_campaigns", path: "/campaigns", icon: "campaigns" },
  { label: "nav_deals", path: "/deals", icon: "deals" },
  { label: "nav_search", path: "/search", icon: "search" },
];

const OWNER_TABS: Tab[] = [
  { label: "nav_channels", path: "/channels", icon: "channels" },
  { label: "nav_deals", path: "/deals", icon: "deals" },
  { label: "nav_listings", path: "/listings", icon: "listings" },
  { label: "nav_search", path: "/campaign-search", icon: "search" },
];

function TabIcon({ name, color }: { name: string; color: string }) {
  const size = 24;
  const props = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: color, strokeWidth: "1.8", strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

  switch (name) {
    case "campaigns":
      return (
        <svg {...props}>
          <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2" />
          <rect x="9" y="3" width="6" height="4" rx="1" />
          <path d="M9 14l2 2 4-4" />
        </svg>
      );
    case "deals":
      return (
        <svg {...props}>
          <path d="M20.5 11H3.5" /><path d="M3.5 11l4-4" />
          <path d="M20.5 13l-4 4" /><path d="M3.5 13h17" />
        </svg>
      );
    case "search":
      return (
        <svg {...props}>
          <circle cx="11" cy="11" r="7" /><path d="M21 21l-4.35-4.35" />
        </svg>
      );
    case "channels":
      return (
        <svg {...props}>
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
      );
    case "listings":
      return (
        <svg {...props}>
          <path d="M12 2L2 7l10 5 10-5-10-5z" />
          <path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
        </svg>
      );
    default:
      return null;
  }
}

function NavBar() {
  const { t } = useTranslation();
  const { user, authenticated } = useAuth();
  const theme = useTheme();
  const navigate = useNavigate();
  const location = useLocation();

  if (!authenticated) return null;

  const tabs = user?.active_role === "owner" ? OWNER_TABS : ADVERTISER_TABS;

  return (
    <nav
      style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        gap: 4,
        padding: "8px 16px",
        paddingBottom: "calc(env(safe-area-inset-bottom, 8px) + 8px)",
        backgroundColor: theme.bg,
        borderTop: `0.5px solid ${theme.border}`,
      }}
    >
      {tabs.map((tab) => {
        const active = location.pathname === tab.path;
        return (
          <button
            key={tab.path}
            onClick={() => navigate(tab.path)}
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 4,
              padding: "8px 0",
              minHeight: 52,
              border: "none",
              borderRadius: 16,
              cursor: "pointer",
              WebkitTapHighlightColor: "transparent",
              transition: "all 0.2s ease",
              backgroundColor: active ? theme.navActiveBg : "transparent",
              color: active ? theme.text : theme.textSecondary,
            }}
          >
            <TabIcon
              name={tab.icon}
              color={active ? theme.accent : theme.textSecondary}
            />
            <span
              style={{
                fontSize: 10,
                fontWeight: active ? 600 : 500,
                color: active ? theme.accent : theme.textSecondary,
              }}
            >
              {t(tab.label)}
            </span>
          </button>
        );
      })}
    </nav>
  );
}

export default NavBar;
