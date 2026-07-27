import { chromium } from "playwright";
import { mkdir, readdir, rm } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const ROOT = path.resolve(import.meta.dirname, "..");
const OUTPUT_ROOT = path.join(ROOT, "Docs", "UI");
const BASE_URL = process.env.ZET_DASHBOARD_URL || "http://127.0.0.1:8080/";
const VIEWPORTS = [
  { folder: "Desktop", width: 1920, height: 911 },
  { folder: "Ipad", width: 1024, height: 768 },
  { folder: "Phone", width: 390, height: 844 },
];

async function prepareOutputFolder(folder) {
  await mkdir(folder, { recursive: true });
  const entries = await readdir(folder, { withFileTypes: true });
  await Promise.all(
    entries
      .filter((entry) => entry.isFile() && entry.name.endsWith(".png"))
      .map((entry) => rm(path.join(folder, entry.name))),
  );
}

async function openDashboard(page) {
  try {
    await page.goto(BASE_URL, { waitUntil: "networkidle" });
  } catch (error) {
    throw new Error(
      `Could not open ${BASE_URL}. Start the dashboard first with run_zet_web.bat.\n${error.message}`,
    );
  }
  await page.waitForFunction(() => typeof window.activatePage === "function");
}

async function discoverPages(page) {
  return page.locator("main > section.page[id$='-page']:not(#placeholder-page)").evaluateAll(
    (sections) => sections.map((section) => section.id.replace(/-page$/, "")),
  );
}

async function activateDashboardPage(page, pageName) {
  await page.evaluate(async (name) => {
    await window.activatePage(name, { skipAutosave: true });
  }, pageName);
  const activePage = page.locator(`#${pageName}-page.active`);
  try {
    await activePage.waitFor({ state: "visible", timeout: 10_000 });
  } catch {
    throw new Error(
      `The dashboard redirected away from "${pageName}". Complete the selected character phase before capturing.`,
    );
  }
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
}

async function captureViewport(browser, viewport, expectedPages) {
  const outputFolder = path.join(OUTPUT_ROOT, viewport.folder);
  await prepareOutputFolder(outputFolder);
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  await openDashboard(page);
  const pages = await discoverPages(page);
  if (expectedPages && pages.join("\n") !== expectedPages.join("\n")) {
    throw new Error("Dashboard page discovery changed between viewport captures.");
  }

  for (const [index, pageName] of pages.entries()) {
    await activateDashboardPage(page, pageName);
    const filename = `${String(index + 1).padStart(2, "0")}-${pageName}.png`;
    await page.screenshot({
      path: path.join(outputFolder, filename),
      fullPage: false,
      animations: "disabled",
    });
    console.log(`${viewport.folder}: ${filename}`);
  }

  await context.close();
  return pages;
}

const browser = await chromium.launch();
try {
  let pages;
  for (const viewport of VIEWPORTS) {
    pages = await captureViewport(browser, viewport, pages);
  }
  console.log(`Captured ${pages.length} pages at ${VIEWPORTS.length} viewport sizes in ${OUTPUT_ROOT}.`);
} finally {
  await browser.close();
}
