import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Forward /api/* to the FastAPI backend, so the browser sees one origin
    // and no CORS setup is needed
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
