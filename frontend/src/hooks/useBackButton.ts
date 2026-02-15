import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

type NavigateTarget = string | number;

interface TelegramWebApp {
  BackButton?: {
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
  };
  close?: () => void;
}

function getTelegramWebApp(): TelegramWebApp | undefined {
  return (window as unknown as { Telegram?: { WebApp?: TelegramWebApp } })
    .Telegram?.WebApp;
}

/**
 * Show the Telegram Mini App native BackButton in the header.
 * If there is no history to go back to (e.g. deep-linked page),
 * the button closes the Mini App window instead.
 * Falls back to a no-op outside Telegram (the button simply won't appear).
 */
export function useBackButton(to: NavigateTarget) {
  const navigate = useNavigate();

  useEffect(() => {
    const webApp = getTelegramWebApp();
    const backButton = webApp?.BackButton;
    if (!backButton) return;

    const handler = () => {
      const canGoBack =
        typeof to === "number" && to < 0 &&
        (window.history.state?.idx ?? 0) > 0;

      if (typeof to === "number") {
        if (canGoBack) {
          navigate(to);
        } else {
          webApp?.close?.();
        }
      } else {
        navigate(to);
      }
    };

    backButton.show();
    backButton.onClick(handler);

    return () => {
      backButton.offClick(handler);
      backButton.hide();
    };
  }, [navigate, to]);
}
