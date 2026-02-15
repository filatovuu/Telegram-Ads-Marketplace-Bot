import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { I18nextProvider } from "react-i18next";
import { TonConnectUIProvider } from "@tonconnect/ui-react";
import i18n from "@/i18n";
import { ThemeProvider } from "@/context/ThemeContext";
import { AuthProvider } from "@/context/AuthContext";
import App from "@/App";

// Manifest path uses /tc/ prefix to avoid wallet-side caching of old
// /tonconnect-manifest.json responses (wallets cache by URL path and
// ignore query-string cache-busters).
const manifestUrl = `${window.location.origin}/tc/manifest.json`;

const tg = window.Telegram?.WebApp;
tg?.ready();
tg?.expand();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <TonConnectUIProvider manifestUrl={manifestUrl}>
      <I18nextProvider i18n={i18n}>
        <BrowserRouter>
          <ThemeProvider>
            <AuthProvider>
              <App />
            </AuthProvider>
          </ThemeProvider>
        </BrowserRouter>
      </I18nextProvider>
    </TonConnectUIProvider>
  </React.StrictMode>
);
