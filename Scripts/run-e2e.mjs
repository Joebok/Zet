import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { rmSync } from "node:fs";
import path from "node:path";
import { resultsRoot } from "../tests/e2e/results-path.mjs";

const config = process.argv[2] === "live" ? "playwright.live.config.mjs" : "playwright.config.mjs";
const runRoot = path.join(resultsRoot, `run-${process.pid}-${Date.now()}`);
const require = createRequire(import.meta.url);
const cli = path.join(path.dirname(require.resolve("playwright")), "cli.js");
const result = spawnSync(process.execPath, [cli, "test", "--config", config], {
  stdio: "inherit",
  env: { ...process.env, ZET_TEST_RESULTS_ROOT: runRoot },
});
if (result.error) throw result.error;
if (result.status === 0) {
  rmSync(runRoot, { recursive: true, force: true });
}
process.exit(result.status ?? 1);
