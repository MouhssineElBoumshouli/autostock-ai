import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In Docker, the server runs in the "api" container. Requests to /api are forwarded there.
const apiTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { "/api": apiTarget },
    // Docker Desktop on Windows does not always pass file-change events into containers,
    // so we check for changes regularly instead. This keeps auto-reload working.
    watch: { usePolling: true, interval: 300 },
  },
});
