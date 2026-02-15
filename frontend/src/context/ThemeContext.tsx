import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

type Mode = "dark" | "light";

export interface ThemeColors {
  mode: Mode;
  bg: string;
  bgSecondary: string;
  bgTertiary: string;
  text: string;
  textSecondary: string;
  accent: string;
  danger: string;
  border: string;
  segmentBg: string;
  segmentActive: string;
  navActiveBg: string;
}

const dark: ThemeColors = {
  mode: "dark",
  bg: "#1C1C1E",
  bgSecondary: "#2C2C2E",
  bgTertiary: "#3A3A3C",
  text: "#FFFFFF",
  textSecondary: "#8E8E93",
  accent: "#007AFF",
  danger: "#FF453A",
  border: "rgba(255,255,255,0.08)",
  segmentBg: "#2C2C2E",
  segmentActive: "#3A3A3C",
  navActiveBg: "#2C2C2E",
};

const light: ThemeColors = {
  mode: "light",
  bg: "#F2F2F7",
  bgSecondary: "#FFFFFF",
  bgTertiary: "#E5E5EA",
  text: "#000000",
  textSecondary: "#8E8E93",
  accent: "#007AFF",
  danger: "#FF3B30",
  border: "rgba(0,0,0,0.08)",
  segmentBg: "#E5E5EA",
  segmentActive: "#FFFFFF",
  navActiveBg: "#E5E5EA",
};

const ThemeContext = createContext<ThemeColors>(dark);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>(() => {
    // Check Telegram WebApp theme first
    const tg = (window as unknown as Record<string, unknown>).Telegram as
      | { WebApp?: { colorScheme?: string } }
      | undefined;
    if (tg?.WebApp?.colorScheme) {
      return tg.WebApp.colorScheme === "light" ? "light" : "dark";
    }
    // Fallback to system preference
    if (window.matchMedia?.("(prefers-color-scheme: light)").matches) {
      return "light";
    }
    return "dark";
  });

  useEffect(() => {
    const mql = window.matchMedia("(prefers-color-scheme: light)");
    const handler = (e: MediaQueryListEvent) => {
      setMode(e.matches ? "light" : "dark");
    };
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);

  // Also listen for Telegram theme changes
  useEffect(() => {
    const tg = (window as unknown as Record<string, unknown>).Telegram as
      | { WebApp?: { onEvent?: (event: string, cb: () => void) => void; colorScheme?: string } }
      | undefined;
    if (tg?.WebApp?.onEvent) {
      const cb = () => {
        setMode(tg.WebApp?.colorScheme === "light" ? "light" : "dark");
      };
      tg.WebApp.onEvent("themeChanged", cb);
    }
  }, []);

  // Set CSS variables on document
  useEffect(() => {
    const colors = mode === "dark" ? dark : light;
    const root = document.documentElement;
    root.style.setProperty("--bg", colors.bg);
    root.style.setProperty("--text", colors.text);
    document.body.style.backgroundColor = colors.bg;
    document.body.style.color = colors.text;
  }, [mode]);

  const value = useMemo(() => (mode === "dark" ? dark : light), [mode]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeColors {
  return useContext(ThemeContext);
}
