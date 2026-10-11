import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "live.spec.mjs",
  workers: 1,
  outputDir: "./test-results/playwright-live",
  timeout: Number(process.env.ZET_LIVE_TEST_TIMEOUT_MS || 20 * 60 * 1000),
  expect: { timeout: 30_000 },
  use: {
    baseURL: "http://127.0.0.1:8766",
    browserName: "chromium",
    reducedMotion: "reduce",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "python3 -B tests/e2e/server.py --mode live",
    url: "http://127.0.0.1:8766/api/context",
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
