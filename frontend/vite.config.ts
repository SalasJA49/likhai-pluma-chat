import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // proxied on the dev server → same origin to the browser
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
