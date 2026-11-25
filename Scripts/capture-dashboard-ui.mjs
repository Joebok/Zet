import { chromium } from "playwright";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { execFileSync } from "node:child_process";
import { pathToFileURL } from "node:url";

const ROOT = path.resolve(import.meta.dirname, "..");
const OUTPUT_ROOT = path.resolve(process.env.ZET_UI_OUTPUT || path.join(ROOT, "test-results", "ui", new Date().toISOString().replace(/[:.]/g, "-")));
const BASE_URL = process.env.ZET_DASHBOARD_URL;
const REVISION = execFileSync("git", ["rev-parse", "HEAD"], { cwd: ROOT, encoding: "utf8" }).trim();
const DIRTY = Boolean(execFileSync("git", ["status", "--porcelain"], { cwd: ROOT, encoding: "utf8" }).trim());
if (!BASE_URL) throw new Error("Set ZET_DASHBOARD_URL to the isolated fixture dashboard URL before capturing.");
const PAGES = (process.env.ZET_UI_PAGES || "onboarding,character-asset-container,minor-characters,identity-keys,turnarounds,costumes,phase-comparison,auxiliary-resources,image-generation,narrative,scene-candidates,zine,universes,universe-create,universe-settings,template-editor,ai-controls,local-image-config,pipeline-inspection,pipeline-controls,help,recent-renders").split(",");
const VIEWPORTS = [
  { folder: "Desktop", width: 1920, height: 911, touch: false },
  { folder: "TabletLandscape", width: 1133, height: 610, touch: true },
  { folder: "TabletPortrait", width: 810, height: 1080, touch: true },
];
const collectorPath = process.env.ZET_EVIDENCE_COLLECTOR;
if (!collectorPath) throw new Error("Set ZET_EVIDENCE_COLLECTOR to the Zet_Tester evidence.mjs path.");
const { observeBrowser, startEvidenceRun } = await import(pathToFileURL(path.resolve(collectorPath)).href);
const release = { revision: process.env.ZET_TEST_RELEASE_REVISION || "unknown", boot_id: process.env.ZET_TEST_BOOT_ID || "unknown" };
if (release.revision === "unknown" || release.boot_id === "unknown") throw new Error("Set the verified Zet Test release revision and boot ID before capturing review evidence.");
const healthResponse = await fetch(new URL('/api/health', BASE_URL));
if (!healthResponse.ok) throw new Error(`Could not verify the dashboard release at ${BASE_URL}.`);
const health = await healthResponse.json();
if (!health.ready || health.revision !== release.revision || health.boot_id !== release.boot_id) throw new Error("The dashboard health does not match the pinned Test release and boot ID.");

async function openDashboard(page) {
  try {
    await page.goto(BASE_URL, { waitUntil: "networkidle" });
  } catch (error) {
    throw new Error(
      `Could not open ${BASE_URL}. Start the isolated fixture dashboard first.\n${error.message}`,
    );
  }
  await page.waitForFunction(() => typeof window.activatePage === "function");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
}

async function activateDashboardPage(page, pageName) {
  await page.evaluate(async (name) => {
    await window.activatePage(name, { skipAutosave: true });
  }, pageName);
  const activePage = page.locator(`main > section.page.active`);
  try {
    await activePage.waitFor({ state: "visible", timeout: 10_000 });
  } catch {
    throw new Error(
      `The dashboard redirected away from "${pageName}". Complete the selected character phase before capturing.`,
    );
  }
  await page.waitForLoadState("networkidle");
  await page.waitForFunction(() => !document.querySelector('[aria-busy="true"]'));
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all(
      Array.from(document.images, (image) => {
        if (image.hidden || image.complete) return undefined;
        return new Promise((resolve) => {
          image.addEventListener("load", resolve, { once: true });
          image.addEventListener("error", resolve, { once: true });
        });
      }),
    );
  });
}

async function captureViewport(browser, viewport) {
  const outputFolder = path.join(OUTPUT_ROOT, viewport.folder);
  await mkdir(outputFolder, { recursive: true });
  const { evidenceDir } = await startEvidenceRun(outputFolder, { origin: "zet-page-sweep", zet_revision: REVISION, dirty: DIRTY, release_revision: release.revision, boot_id: release.boot_id, viewport_profile: viewport.folder });
  const results = [];
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    deviceScaleFactor: 1,
    isMobile: false,
    hasTouch: viewport.touch,
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const captureEvidence = observeBrowser(page, evidenceDir, { origin: "zet-page-sweep", zet_revision: REVISION, release_revision: release.revision, boot_id: release.boot_id, viewport_profile: viewport.folder });
  await openDashboard(page);
  const pages = PAGES;

  for (const [index, pageName] of pages.entries()) {
    let error = null;
    try { await activateDashboardPage(page, pageName); } catch (failure) { error = failure.message; }
    const overflow = await page.evaluate(() => {
      const activePage = document.querySelector("main > .page.active");
      return {
        document: document.documentElement.scrollWidth > document.documentElement.clientWidth,
        page: Boolean(activePage && activePage.scrollWidth > activePage.clientWidth),
      };
    });
    results.push({ route: pageName, viewport, revision: REVISION, dirty: DIRTY, capturedAt: new Date().toISOString(), error, overflow, actual: await page.evaluate(() => ({page: document.querySelector("main > .page.active")?.id, width: innerWidth, height: innerHeight, scale: visualViewport?.scale, browser: navigator.userAgent})) });
    if (!error) await captureEvidence(`page-${pageName}`, { state_key: pageName, requested_page: pageName, actual_page: await page.evaluate(() => new URLSearchParams(location.search).get("page") || "onboarding") });
    const filename = `${String(index + 1).padStart(2, "0")}-${pageName}.png`;
    await page.screenshot({
      path: path.join(outputFolder, filename),
      fullPage: false,
      animations: "disabled",
    });
    console.log(`${viewport.folder}: ${filename}`);
  }

  await writeFile(path.join(outputFolder, "inspection.json"), JSON.stringify(results, null, 2));
  const overflows = results.filter(row => row.overflow.document || row.overflow.page).length;
  console.log(`${viewport.folder}: ${overflows} pages with overflow, ${results.filter(row => row.error).length} activation errors; see inspection.json`);
  if (overflows) process.exitCode = 1;

  await context.close();
  return pages;
}

const browser = await chromium.launch();
try {
  let pages;
  const runManifests = [];
  const coverage = [];
  for (const viewport of VIEWPORTS) {
    pages = await captureViewport(browser, viewport);
    const outputFolder = path.join(OUTPUT_ROOT, viewport.folder);
    const manifest = JSON.parse(await readFile(path.join(outputFolder, "evidence", "manifest.json"), "utf8"));
    runManifests.push({profile: viewport.folder, path: `${viewport.folder}/evidence/manifest.json`, captures: manifest.captures});
    const inspections = JSON.parse(await readFile(path.join(outputFolder, "inspection.json"), "utf8"));
    coverage.push(...inspections.map(item => ({page: item.route, profile: viewport.folder, status: item.error ? "blocked" : "structure-captured", workflow_output_freshness: "not-established", interaction_coverage: "not-captured", error: item.error, capture_id: manifest.captures.find(capture => capture.state_key === item.route)?.capture_id})));
  }
  const campaignDir = path.join(OUTPUT_ROOT, "evidence");
  await mkdir(campaignDir, {recursive: true});
  await writeFile(path.join(campaignDir, "manifest.json"), JSON.stringify({schema_version: 1, collector: "zet-tester/evidence-v1", origin: "zet-page-sweep", campaign_id: path.basename(OUTPUT_ROOT), zet_revision: REVISION, dirty: DIRTY, release_revision: release.revision, boot_id: release.boot_id, profiles: runManifests.map(({profile, path}) => ({profile, manifest: path})), capture_count: runManifests.reduce((sum, item) => sum + item.captures.length, 0)}, null, 2));
  await writeFile(path.join(campaignDir, "coverage.json"), JSON.stringify(coverage, null, 2));
  console.log(`Captured ${pages.length} pages at ${VIEWPORTS.length} viewport sizes in ${OUTPUT_ROOT}.`);
} finally {
  await browser.close();
}
