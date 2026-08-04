import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/browser",
  workers: 1,
  outputDir: "./test-results/playwright",
  snapshotDir: "./tests/browser/snapshots",
  timeout: 30_000,
  expect: {
    timeout: 8_000,
    toHaveScreenshot: { animations: "disabled", maxDiffPixelRatio: 0.01 },
  },
  use: {
    baseURL: "http://127.0.0.1:8765",
    browserName: "chromium",
    reducedMotion: "reduce",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "python3 -B tests/browser/run_test_server.py",
    url: "http://127.0.0.1:8765/api/context",
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
