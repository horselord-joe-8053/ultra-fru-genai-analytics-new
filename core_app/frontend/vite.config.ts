import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

// API port for proxy: VITE_API_PORT if set (per dev-server instance), else 5001.
// VITE_* vars are special: they are exposed to the browser (import.meta.env),
// so start_local.py is responsible for setting VITE_API_PORT before "npm run dev".
const apiPort = process.env.VITE_API_PORT || "5001";
const apiTarget = `http://localhost:${apiPort}`;

export default defineConfig({
  plugins: [react()],
  define: {
    // No build-time version constants needed; UI uses backend /version as single source of truth.
  },
  server: {
    port: 5173,
    proxy: {
      "/query": { target: apiTarget, changeOrigin: true },
      "/query/stream": { target: apiTarget, changeOrigin: true },
      "/analytics": { target: apiTarget, changeOrigin: true },
      "/rawdata": { target: apiTarget, changeOrigin: true },
      "/rawdata/*": { target: apiTarget, changeOrigin: true },
      "/health": { target: apiTarget, changeOrigin: true },
      "/version": { target: apiTarget, changeOrigin: true },
    },
  },
});
