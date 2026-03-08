import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

// API port for proxy: LOCAL_API_PORT or VITE_API_PORT (when 5001 is in use)
const apiPort = process.env.LOCAL_API_PORT || process.env.VITE_API_PORT || "5001";
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
