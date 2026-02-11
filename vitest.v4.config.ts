import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/unit/**/*.test.ts", "tests/integration/**/*.test.ts"],
    exclude: ["node_modules", "dist"],
    testTimeout: 10_000,
    globals: true,
  },
});
