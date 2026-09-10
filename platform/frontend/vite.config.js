import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Hasil build ditaruh di platform/frontend-dist supaya FastAPI bisa
// menyajikannya langsung tanpa server tambahan.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Selama `npm run dev`, panggilan API diteruskan ke backend FastAPI.
      "/api": {
        target: "http://127.0.0.1:8080",
        // target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "../frontend-dist",
    emptyOutDir: true,
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        // Vite 8 memakai rolldown, yang hanya menerima bentuk fungsi.
        // Pustaka besar dipisah supaya perubahan kode aplikasi tidak
        // membatalkan cache vendor di peramban.
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("recharts") || id.includes("d3-")) return "charts";
          if (id.includes("antd") || id.includes("@ant-design")) return "antd";
          if (id.includes("react-router") || id.includes("/react-dom/") || id.includes("/react/")) {
            return "vendor";
          }
          return undefined;
        },
      },
    },
  },
});
