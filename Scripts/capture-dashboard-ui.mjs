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

async function captureViewport(browser, viewport, expectedPages) {
  const outputFolder = path.join(OUTPUT_ROOT, viewport.folder);
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

  const expectedFiles = pages.map(
    (pageName, index) => `${String(index + 1).padStart(2, "0")}-${pageName}.png`,
  );
  const capturedFiles = (await readdir(outputFolder))
    .filter((name) => name.endsWith(".png"))
    .sort();
  if (capturedFiles.join("\n") !== expectedFiles.sort().join("\n")) {
    throw new Error(`Missing dashboard captures in ${outputFolder}.`);
  }

  await context.close();
  return pages;
}

await Promise.all(
  VIEWPORTS.map((viewport) => prepareOutputFolder(path.join(OUTPUT_ROOT, viewport.folder))),
);

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
