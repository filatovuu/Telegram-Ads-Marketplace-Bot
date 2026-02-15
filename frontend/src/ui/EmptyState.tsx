import { useTheme } from "@/context/ThemeContext";

interface EmptyStateProps {
  icon: string;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  const theme = useTheme();
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", paddingTop: 80 }}>
      <span style={{ fontSize: 48, marginBottom: 16 }}>{icon}</span>
      <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 6, color: theme.text }}>{title}</h2>
      {description && (
        <p style={{ color: theme.textSecondary, fontSize: 14, marginBottom: action ? 20 : 0, textAlign: "center", maxWidth: 260 }}>{description}</p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          style={{
            backgroundColor: theme.accent,
            color: "#fff",
            border: "none",
            borderRadius: 12,
            padding: "12px 24px",
            fontSize: 15,
            fontWeight: 600,
            cursor: "pointer",
            WebkitTapHighlightColor: "transparent",
          }}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}

export default EmptyState;
