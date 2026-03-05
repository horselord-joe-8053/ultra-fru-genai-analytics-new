import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

export default defineConfig({
  plugins: [react()],
  define: {
    // No build-time version constants needed; UI uses backend /version as single source of truth.
  },
  server: {
    port: 5173,
    proxy: {
      "/query": {
        target: "http://localhost:5001",
        changeOrigin: true,
      },
      "/analytics": {
        target: "http://localhost:5001",
        changeOrigin: true,
      },
      "/query/stream": {
        target: "http://localhost:5001",
        changeOrigin: true,
      },
    },
  },
});
