import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import pkg from "./package.json";

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  server: {
    port: 5173,
    host: "127.0.0.1",
  },
  build: {
    // 产物直接进 Python 包目录：wheel 与 sdist 都会自动带上，无需额外打包规则。
    outDir: "../vulnclaw/web/dist",
    emptyOutDir: true,
  },
});
