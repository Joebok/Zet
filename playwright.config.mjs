import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "fast.spec.mjs",
  workers: 1,
  outputDir: "./test-results/playwright",
  timeout: 90_000,
  expect: {
    timeout: 8_000,
  },
  use: {
    baseURL: "http://127.0.0.1:8765",
    browserName: "chromium",
    reducedMotion: "reduce",
    trace: "retain-on-failure",
  },
  webServer: {
    command: `"${process.env.ZET_TEST_PYTHON || "python3"}" -B tests/e2e/server.py --mode fast`,
    url: "http://127.0.0.1:8765/api/context",
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
