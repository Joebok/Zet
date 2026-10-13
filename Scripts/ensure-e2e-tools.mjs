import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

function canResolve(packageName) {
  try {
    require.resolve(packageName);
    return true;
  } catch {
    return false;
  }
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { stdio: "inherit", ...options });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}

if (!canResolve("playwright") || !canResolve("@playwright/test")) {
  console.log("Installing npm dependencies pinned in package-lock.json...");
  // npm lifecycle scripts export .npmrc settings as environment overrides. npm 11
  // rejects allow-scripts overrides for project installs; let ci read policy from
  // package.json/.npmrc itself. Preserve all other settings, including userconfig.
  const installEnv = Object.fromEntries(Object.entries(process.env).filter(
    ([key]) => !/^npm_config_allow[-_]scripts$/i.test(key),
  ));
  run(process.platform === "win32" ? "npm.cmd" : "npm", ["ci"], {
    shell: process.platform === "win32",
    env: installEnv,
  });
}

const { chromium } = require("playwright");
if (!existsSync(chromium.executablePath())) {
  console.log("Installing the Chromium browser required by the E2E suite...");
  const playwrightCli = join(dirname(require.resolve("playwright")), "cli.js");
  run(process.execPath, [playwrightCli, "install", "chromium"]);
}
