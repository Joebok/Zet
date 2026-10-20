import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { execFileSync } from "node:child_process";

const ROOT = path.resolve(import.meta.dirname, "..");
const OUTPUT_ROOT = path.resolve(process.env.ZET_UI_OUTPUT || path.join(ROOT, "test-results", "ui", new Date().toISOString().replace(/[:.]/g, "-")));
const BASE_URL = process.env.ZET_DASHBOARD_URL;
const REVISION = execFileSync("git", ["rev-parse", "HEAD"], { cwd: ROOT, encoding: "utf8" }).trim();
const DIRTY = Boolean(execFileSync("git", ["status", "--porcelain"], { cwd: ROOT, encoding: "utf8" }).trim());
if (!BASE_URL) throw new Error("Set ZET_DASHBOARD_URL to the isolated fixture dashboard URL before capturing.");
const PAGES = (process.env.ZET_UI_PAGES || "onboarding,local-body-reference,local-head-image,local-character-assembly,local-costume-dressing,minor-characters,identity-keys,turnarounds,costumes,phase-comparison,auxiliary-resources,image-generation,narrative,scene-candidates,zine,universes,universe-create,universe-settings,template-editor,ai-controls,local-batch-status,local-image-config,pipeline-inspection,pipeline-controls,help").split(",");
const VIEWPORTS = [
  { folder: "Desktop", width: 1920, height: 911 },
  { folder: "IpadMini", width: 1133, height: 610 },
  { folder: "IpadShort", width: 1133, height: 560 },
  { folder: "Ipad", width: 1024, height: 640 },
  { folder: "Phone", width: 390, height: 844 },
];

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
  const results = [];
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
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
  for (const viewport of VIEWPORTS) {
    pages = await captureViewport(browser, viewport);
  }
  console.log(`Captured ${pages.length} pages at ${VIEWPORTS.length} viewport sizes in ${OUTPUT_ROOT}.`);
} finally {
  await browser.close();
}
