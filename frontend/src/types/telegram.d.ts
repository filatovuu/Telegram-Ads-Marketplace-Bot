interface TelegramWebApp {
  initData: string;
  colorScheme: "light" | "dark";
  openTelegramLink(url: string): void;
  openLink(url: string): void;
  close(): void;
  expand(): void;
  ready(): void;
  onEvent(event: string, callback: () => void): void;
  offEvent(event: string, callback: () => void): void;
  BackButton: {
    show(): void;
    hide(): void;
    onClick(callback: () => void): void;
    offClick(callback: () => void): void;
  };
}

declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp;
    };
  }
}

export {};
