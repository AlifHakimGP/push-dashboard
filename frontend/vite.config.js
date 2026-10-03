import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The proxy below is ONLY used when running `npm run dev` (the Vite dev
// server on :5173). It's what lets you write fetch("/api/pushes") in the
// React code and have it "just work" in both places: in dev, Vite
// forwards it to the FastAPI backend on :8000; in production, there's no
// Vite server at all — FastAPI itself serves the built files AND the API
// from the same origin, so no proxy is needed or used there.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/webhook": "http://localhost:8000",
    },
  },
});
