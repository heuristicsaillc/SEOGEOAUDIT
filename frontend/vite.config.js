// Vite configuration for the React frontend.
import { defineConfig } from "vite"; // Vite config helper
import react from "@vitejs/plugin-react"; // React fast-refresh + JSX support

// During development the API runs on :8000; we proxy /api to it so the
// frontend can use same-origin relative URLs in both dev and production.
export default defineConfig({
  plugins: [react()], // Enable React support
  server: {
    port: 5173, // Vite dev server port
    proxy: {
      // Forward any /api request to the FastAPI backend during development
      "/api": {
        target: "http://127.0.0.1:8000", // Backend address
        changeOrigin: true, // Rewrite the Host header to the target
      },
    },
  },
  build: {
    outDir: "dist", // FastAPI serves this directory in production
  },
});
