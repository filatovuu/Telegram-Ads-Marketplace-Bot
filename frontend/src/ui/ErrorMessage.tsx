import { useTranslation } from "react-i18next";
import { useTheme } from "@/context/ThemeContext";

interface ErrorMessageProps {
  message?: string;
  onRetry?: () => void;
}

function ErrorMessage({ message, onRetry }: ErrorMessageProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <div
      style={{
        margin: "40px 16px",
        padding: "16px",
        borderRadius: 12,
        backgroundColor: theme.danger + "12",
        border: `1px solid ${theme.danger}40`,
        textAlign: "center",
      }}
    >
      <p style={{ color: theme.danger, fontSize: 14, fontWeight: 600, margin: "0 0 4px" }}>
        {message || t("error")}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            marginTop: 10,
            padding: "8px 20px",
            borderRadius: 8,
            border: "none",
            backgroundColor: theme.danger,
            color: "#fff",
            fontWeight: 600,
            fontSize: 13,
            cursor: "pointer",
          }}
        >
          {t("retry")}
        </button>
      )}
    </div>
  );
}

export default ErrorMessage;
