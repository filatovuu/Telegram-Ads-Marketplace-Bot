import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import fs from "fs";

function writeManifestIfChanged(dir: string, filename: string, content: string) {
  fs.mkdirSync(dir, { recursive: true });
  const filePath = path.join(dir, filename);
  const existing = fs.existsSync(filePath) ? fs.readFileSync(filePath, "utf-8") : "";
  if (existing !== content) {
    fs.writeFileSync(filePath, content);
  }
}

function tonConnectManifestPlugin(appUrl: string) {
  const manifest =
    JSON.stringify(
      {
        url: appUrl,
        name: "Ads Marketplace",
        iconUrl: `${appUrl}/tc/icon.png`,
      },
      null,
      2,
    ) + "\n";
  // Serve at /tc/manifest.json — unique path to bypass wallet-side caching
  const dir = path.resolve(__dirname, "public", "tc");
  return {
    name: "tonconnect-manifest",
    buildStart() {
      // Only write if content actually changed — prevents watch loop in dev mode
      // (Vite watches public/ and would trigger endless rebuilds otherwise)
      writeManifestIfChanged(dir, "manifest.json", manifest);
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  const domain = env.DOMAIN || process.env.DOMAIN || "localhost";
  const protocol = domain === "localhost" || domain === "127.0.0.1" ? "http" : "https";
  const appUrl = `${protocol}://${domain}`;

  // VITE_BOT_USERNAME may come from: .env file (loadEnv), or Docker env (process.env)
  const botUsername =
    env.VITE_BOT_USERNAME || process.env.VITE_BOT_USERNAME || process.env.BOT_USERNAME || "";

  return {
    plugins: [react(), tonConnectManifestPlugin(appUrl)],
    define: {
      "import.meta.env.VITE_BOT_USERNAME": JSON.stringify(botUsername),
    },
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      host: "0.0.0.0",
      port: 3000,

      allowedHosts: [domain, "localhost", "127.0.0.1"].filter(Boolean),

      hmr: {
        // Use the public domain so HMR WebSocket works through nginx/Cloudflare
        clientPort: protocol === "https" ? 443 : 80,
      },

      proxy: {
        "/api": {
          target: "http://backend:8000",
          changeOrigin: true,
        },
      },
    },
  };
});
