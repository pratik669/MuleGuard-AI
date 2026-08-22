import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:4000" } },
  build: {
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks: {
          reactflow: ["reactflow"],
          recharts: ["recharts"],
          vendor: ["react", "react-dom", "react-router-dom"],
        }
      }
    }
  }
});
