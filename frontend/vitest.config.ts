import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  define: { __APP_VERSION__: JSON.stringify("0.5.0") },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    // Playwright specs live in e2e/ and must not be collected by Vitest.
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["src/utils/**/*.{ts,tsx}", "src/api/**/*.{ts,tsx}", "src/components/**/*.{ts,tsx}"],
      exclude: ["src/**/__tests__/**"],
      thresholds: {
        lines: 40,
        functions: 40,
        statements: 40,
        branches: 30,
        "src/utils/**/*.{ts,tsx}": {
          lines: 90,
          functions: 90,
          statements: 90,
        },
      },
    },
  },
});
