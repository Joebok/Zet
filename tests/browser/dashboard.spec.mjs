import { expect, test } from "@playwright/test";
import { restorePristineProjectState, restorePristineScene } from "./scene-fixtures.mjs";

test.beforeEach(async ({ page }) => {
  await restorePristineProjectState();
  await restorePristineScene(page, "Alpha-Story", "Opening-Scene");
  await restorePristineScene(page, "Alpha-Story", "Closing-Scene");
});

const DESKTOP_VIEWPORTS = [
  [1600, 900],
];

async function openPage(page, pageName) {
  await page.goto("/");
  await page.waitForFunction(() => typeof window.activatePage === "function");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await expect(page.locator("#character-select option")).not.toHaveCount(0);
  await page.evaluate(async (name) => window.activatePage(name, { skipAutosave: true }), pageName);
  await expect(page.locator(`#${pageName}-page`)).toHaveClass(/active/);
}

function delayedGate(delayMs = 120_000) {
  let release;
  const promise = new Promise((resolve) => {
    const timer = setTimeout(resolve, delayMs);
    release = () => {
      clearTimeout(timer);
      resolve();
    };
  });
  return { promise, release };
}

test("universe pages create and save canonical art style", async ({ page }) => {
  await openPage(page, "universes");
  await expect(page.locator("#universe-list")).toContainText("Moonsea");
  await page.getByRole("button", { name: "New Universe" }).click();
  await expect(page.locator("#universe-create-page")).toHaveClass(/active/);
  await page.locator("#universe-create-name").fill("Test Realm");
  await page.locator("#universe-create-art-style").fill("Painterly fantasy");
  await page.getByRole("button", { name: "Create Universe" }).click();
  await expect(page.locator("#universe-settings-title")).toHaveText("Test Realm Settings");
  await expect(page.locator("#universe-settings-art-style")).toHaveValue("Painterly fantasy");
  await page.locator("#universe-settings-art-style").fill("Updated painterly fantasy");
  await page.getByRole("button", { name: "Save Settings" }).click();
  await expect(page.locator("#universe-settings-message")).toHaveText("Settings saved.");
  await page.getByRole("button", { name: "Back to Universes" }).click();
  await expect(page.locator("#universe-list")).toContainText("Updated painterly fantasy");
});

test("image generation fills eight slots and imports the selected image's prompt", async ({ page }) => {
  const submitted = [];
  const jobs = new Map();
  let imported;
  await page.route("**/api/image-generation/options", (route) => route.fulfill({
    json: {
      model: "Qwen Image 2.1", checkpoint: "qwen.safetensors", default_count: 4,
      default_width: 1024, default_height: 1024,
    },
  }));
  await page.route("**/api/image-generation/jobs", async (route) => {
    if (route.request().method() === "POST") {
      const request = route.request().postDataJSON();
      submitted.push(request);
      const request_id = `browser-image-job-${submitted.length}`;
      const job = {
        request_id, mode: request.mode, status: "COMPLETE", requested: request.count,
        completed: request.count, failed: 0, error: "", prompt: request.prompt,
        negative_prompt: request.negative_prompt, source_asset_id: "",
        images: Array.from({ length: request.count }, (_, index) => ({
          index, url: `/api/image-generation/jobs/${request_id}/images/${index}`,
        })),
      };
      jobs.set(request_id, job);
      await route.fulfill({ json: job });
      return;
    }
    await route.fulfill({ status: 405 });
  });
  await page.route(/\/api\/image-generation\/jobs\/browser-image-job-\d+$/, (route) => {
    const id = route.request().url().split("/").at(-1);
    if (route.request().method() === "DELETE") {
      jobs.delete(id);
      return route.fulfill({ json: { message: "Image generation results cleared." } });
    }
    return route.fulfill({ json: jobs.get(id) });
  });
  await page.route(/\/api\/image-generation\/jobs\/browser-image-job-\d+\/images\/\d+$/, (route) => {
    const parts = new URL(route.request().url()).pathname.split("/");
    const id = parts.at(-3);
    const index = Number(parts.at(-1));
    if (route.request().method() === "DELETE") {
      const job = jobs.get(id);
      job.images = job.images.filter((image) => image.index !== index);
      job.completed = job.images.length;
      return route.fulfill({ json: job });
    }
    return route.fulfill({
      status: 200, contentType: "image/png",
      body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC0lEQVR42mP8/x8AAwMCAO+/QioAAAAASUVORK5CYII=", "base64"),
    });
  });

  await openPage(page, "image-generation");
  await expect(page.locator("#image-generation-results-grid figure")).toHaveCount(8);
  await expect(page.locator("#image-generation-width")).toHaveValue("1024");
  await expect(page.locator("#image-generation-height")).toHaveValue("1024");
  await page.locator("#image-generation-img2img").click();
  await expect(page.locator("#image-generation-reference-field")).toBeVisible();
  await page.locator("#image-generation-reference").setInputFiles({
    name: "reference.png",
    mimeType: "image/png",
    buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/QioAAAAASUVORK5CYII=", "base64"),
  });
  await page.locator("#image-generation-prompt").fill("Make the object carved from jade");
  await page.locator("#image-generation-negative").fill("plastic");
  await page.locator("#image-generation-width").fill("1280");
  await page.locator("#image-generation-height").fill("768");
  await page.getByRole("button", { name: "Render First 4" }).click();
  await expect(page.locator("#image-generation-results-grid img")).toHaveCount(4);
  expect(submitted[0]).toMatchObject({
    mode: "img2img", width: 1280, height: 768, count: 4,
    prompt: "Make the object carved from jade",
  });
  expect(submitted[0].reference_image).toMatch(/^data:image\/png;base64,/);
  await page.locator("#image-generation-prompt").fill("Make the object from bronze");
  await page.locator("#image-generation-negative").fill("plastic, scratches");
  await page.getByRole("button", { name: "Fill Slots" }).click();
  await expect(page.locator("#image-generation-results-grid img")).toHaveCount(8);
  expect(submitted[1]).toMatchObject({ count: 4, prompt: "Make the object from bronze" });
  await page.getByRole("button", { name: "Review slot 5" }).click();
  await expect(page.locator("#image-generation-review-prompt")).toHaveText("Make the object from bronze");
  await page.locator("#image-generation-review-previous").click();
  await expect(page.locator("#image-generation-review-prompt")).toHaveText("Make the object carved from jade");
  await page.locator("#image-generation-review-next").click();
  await page.locator("#image-generation-review-select").click();
  await page.locator("#image-generation-review-close").click();
  await expect(page.locator("#image-generation-review-import")).toBeEnabled();
  await page.reload();
  await expect(page.locator("#image-generation-prompt")).toHaveValue("Make the object from bronze");
  await expect(page.locator("#image-generation-width")).toHaveValue("1280");
  await expect(page.locator("#image-generation-results-grid img")).toHaveCount(8);
  await expect(page.locator("#image-generation-review-import")).toBeEnabled();
  const libraryImport = await page.request.post("/api/entity-library/assets?label=Generated+Import+Fixture", {
    data: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/QioAAAAASUVORK5CYII=", "base64"),
    headers: { "content-type": "image/png" },
  });
  expect(libraryImport.ok()).toBeTruthy();
  const libraryAsset = (await libraryImport.json()).asset;
  await page.route("**/api/image-generation/jobs/browser-image-job-2/images/0/import", async (route) => {
    imported = route.request().postDataJSON();
    await route.fulfill({ json: { asset: libraryAsset, duplicate: false } });
  });
  await page.locator("#image-generation-review-import").click();
  await expect(page.locator("#auxiliary-resources-page")).toHaveClass(/active/);
  await expect(page.locator("#entity-library-import-dialog")).toBeVisible();
  await expect(page.locator("#entity-library-import-preview")).toBeVisible();
  await expect(page.locator("#entity-library-import-prompt")).toHaveText("Make the object from bronze");
  await expect(page.locator("#entity-library-import-negative-prompt")).toHaveText("plastic, scratches");
  const importResponse = page.waitForResponse((response) => response.url().includes("/api/image-generation/jobs/browser-image-job-2/images/0/import") && response.ok());
  await page.locator("#entity-library-import").click();
  await importResponse;
  expect(imported).toMatchObject({ label: "Make the object from bronze", provenance: "Image Generation job browser-image-job-2, result 1" });
  await expect(page.locator("#entity-library-import-dialog")).toBeHidden();
  await expect(page.locator("#entity-library-save")).toBeEnabled();
  await page.evaluate(() => window.activatePage("image-generation", { skipAutosave: true }));
  await page.getByRole("button", { name: "Review slot 5" }).click();
  await page.locator("#image-generation-review-clear").click();
  await expect(page.locator("#image-generation-results-grid img")).toHaveCount(7);
  await page.locator("#image-generation-review-close").click();
  await page.locator("#image-generation-prompt").fill("Make the object from ruby");
  await page.getByRole("button", { name: "Fill Slots" }).click();
  await expect(page.locator("#image-generation-results-grid img")).toHaveCount(8);
  expect(submitted[2]).toMatchObject({ count: 1, prompt: "Make the object from ruby" });
  await page.locator("#image-generation-clear").click();
  await expect(page.locator("#image-generation-results-grid img")).toHaveCount(0);
  await expect(page.locator("#image-generation-prompt")).toHaveValue("");
});

test("inventory img2img replaces saved and previously chosen references", async ({ page }) => {
  const sourceBytes = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/QioAAAAASUVORK5CYII=", "base64");
  await openPage(page, "auxiliary-resources");
  const response = await page.request.post("/api/entity-library/assets?label=Inventory+Reference+Fixture", {
    data: sourceBytes, headers: { "content-type": "image/png" },
  });
  expect(response.ok()).toBeTruthy();
  const asset = (await response.json()).asset;
  await page.route(`**/api/entity-library/assets/${asset.asset_id}`, async (route) => {
    const result = await route.fetch();
    const payload = await result.json();
    payload.asset.width = 1280;
    payload.asset.height = 768;
    await route.fulfill({ response: result, json: payload });
  });
  await page.evaluate(async () => {
    const database = await new Promise((resolve, reject) => {
      const request = indexedDB.open("zet-image-generation", 1);
      request.onupgradeneeded = () => request.result.createObjectStore("state");
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    await new Promise((resolve, reject) => {
      const transaction = database.transaction("state", "readwrite");
      transaction.objectStore("state").put("data:image/png;base64,YmFk", "reference");
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error);
    });
    database.close();
  });
  await page.reload();
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.evaluate(async (assetId) => {
    await window.activatePage("auxiliary-resources", { skipAutosave: true });
    await selectEntityLibraryAsset(assetId);
  }, asset.asset_id);
  const submitted = [];
  await page.route("**/api/image-generation/jobs", (route) => {
    const payload = route.request().postDataJSON();
    submitted.push(payload);
    return route.fulfill({ json: {
      request_id: `inventory-reference-job-${submitted.length}`, mode: "img2img", status: "COMPLETE",
      requested: 4, completed: 0, failed: 0, error: "", images: [],
      prompt: payload.prompt, negative_prompt: payload.negative_prompt,
      source_asset_id: payload.source_asset_id, source_checksum: payload.source_checksum,
    } });
  });
  await page.locator("#entity-library-modify-generated").click();
  await expect(page.locator("#image-generation-page")).toHaveClass(/active/);
  await expect(page.locator("#image-generation-width")).toHaveValue("1280");
  await expect(page.locator("#image-generation-height")).toHaveValue("768");
  await page.locator("#image-generation-prompt").fill("Edit the inventory image");
  await page.getByRole("button", { name: "Render First 4" }).click();
  await expect.poll(() => submitted.length).toBe(1);
  expect(submitted[0].source_asset_id).toBe(asset.asset_id);
  expect(Buffer.from(submitted[0].reference_image.split(",")[1], "base64")).toEqual(sourceBytes);

  await page.locator("#image-generation-reference").setInputFiles({
    name: "old-reference.png", mimeType: "image/png", buffer: Buffer.concat([sourceBytes, Buffer.from("old")]),
  });
  await page.locator("#image-generation-width").fill("1024");
  await page.locator("#image-generation-height").fill("1024");
  await page.evaluate(async (assetId) => {
    await window.activatePage("auxiliary-resources", { skipAutosave: true });
    await selectEntityLibraryAsset(assetId);
  }, asset.asset_id);
  await page.locator("#entity-library-modify-generated").click();
  await expect(page.locator("#image-generation-reference")).toHaveValue("");
  await expect(page.locator("#image-generation-width")).toHaveValue("1280");
  await expect(page.locator("#image-generation-height")).toHaveValue("768");
  await page.locator("#image-generation-prompt").fill("Edit the inventory image again");
  await page.getByRole("button", { name: "Render First 4" }).click();
  await expect.poll(() => submitted.length).toBe(2);
  expect(Buffer.from(submitted[1].reference_image.split(",")[1], "base64")).toEqual(sourceBytes);
});

test("navigation cancels an active candidate load and ignores its late response", async ({ page }) => {
  await openPage(page, "stories");
  await page.route("**/api/scene-candidate-sources", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ sources: [{ key: "active-fixture", label: "Active fixture", path: "fixture", default_story_slug: "Alpha-Story" }] }),
  }));
  let markStarted;
  const requestStarted = new Promise((resolve) => { markStarted = resolve; });
  const delayedResponse = delayedGate();
  await page.route(/\/api\/scene-candidates\?source_key=/, async (route) => {
    markStarted();
    await delayedResponse.promise;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ items: [{ candidate_id: "late-candidate", label: "Late candidate" }], total: 1, next_cursor: null, generation: 1, freshness: {} }),
    }).catch(() => {});
  });

  await page.evaluate(() => { window.wp02DelayedPage = window.activatePage("scene-candidates", { skipAutosave: true }); });
  await requestStarted;
  const elapsed = await page.evaluate(async () => {
    const started = performance.now();
    await window.activatePage("stories", { skipAutosave: true });
    return performance.now() - started;
  });
  expect(elapsed).toBeLessThan(250);
  await expect(page.locator("#stories-page")).toHaveClass(/active/);

  delayedResponse.release();
  await page.waitForTimeout(100);
  await expect(page.locator("#stories-page")).toHaveClass(/active/);
  await expect(page.locator("#scene-candidate-list")).not.toContainText("Late candidate");
});

test("a late active-candidate error cannot replace the newly active page", async ({ page }) => {
  await openPage(page, "stories");
  await page.route("**/api/scene-candidate-sources", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ sources: [{ key: "active-fixture", label: "Active fixture", path: "fixture", default_story_slug: "Alpha-Story" }] }),
  }));
  let markStarted;
  const requestStarted = new Promise((resolve) => { markStarted = resolve; });
  const delayedResponse = delayedGate();
  await page.route(/\/api\/scene-candidates\?source_key=/, async (route) => {
    markStarted();
    await delayedResponse.promise;
    await route.fulfill({ status: 503, body: "late failure" }).catch(() => {});
  });

  await page.evaluate(() => { window.wp02DelayedError = window.activatePage("scene-candidates", { skipAutosave: true }); });
  await requestStarted;
  await page.evaluate(() => window.activatePage("stories", { skipAutosave: true }));
  delayedResponse.release();
  await page.waitForTimeout(100);
  await expect(page.locator("#stories-page")).toHaveClass(/active/);
  await expect(page.locator("#story-status")).not.toContainText(/failed/i);
});

test("candidate loading, empty, and failed states stay distinct", async ({ page }) => {
  await openPage(page, "stories");
  await page.route("**/api/scene-candidate-sources", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ sources: [{ key: "wp02", label: "WP02", path: "fixture", default_story_slug: "Alpha-Story" }] }),
  }));
  const candidatesResponse = delayedGate();
  await page.route(/\/api\/scene-candidates\?source_key=/, async (route) => {
    await candidatesResponse.promise;
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ items: [], total: 0, next_cursor: null, generation: 1, freshness: {} }) });
  });

  await page.evaluate(() => { window.wp02CandidateLoad = window.activatePage("scene-candidates", { skipAutosave: true }); });
  await expect(page.locator("#scene-candidate-status")).toHaveText("Loading candidates...");
  const elapsed = await page.evaluate(async () => {
    const started = performance.now();
    await window.activatePage("stories", { skipAutosave: true });
    return performance.now() - started;
  });
  expect(elapsed).toBeLessThan(250);
  candidatesResponse.release();
  await expect(page.locator("#stories-page")).toHaveClass(/active/);

  await page.unroute(/\/api\/scene-candidates\?source_key=/);
  await page.route(/\/api\/scene-candidates\?source_key=/, (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ items: [], total: 0, next_cursor: null, generation: 1, freshness: {} }),
  }));
  await page.evaluate(() => window.activatePage("scene-candidates", { skipAutosave: true }));
  await expect(page.locator("#scene-candidate-status")).toHaveText("0 candidates");
  await expect(page.locator("#scene-candidate-list")).toContainText("No candidates match this filter.");

  await page.unroute(/\/api\/scene-candidates\?source_key=/);
  await page.route(/\/api\/scene-candidates\?source_key=/, (route) => route.fulfill({ status: 503, body: "unavailable" }));
  await page.evaluate(() => window.activatePage("stories", { skipAutosave: true }));
  await page.evaluate(() => window.activatePage("scene-candidates", { skipAutosave: true }));
  await expect(page.locator("#scene-candidate-status")).toHaveText("Load failed.");
  await expect(page.locator("#scene-candidate-message")).toContainText("503");
});

test("summary refreshes never overlap and pause while hidden", async ({ page }) => {
  await openPage(page, "stories");
  await expect.poll(() => page.evaluate(() => eval("Boolean(state.productionWorkPromise)"))).toBe(false);
  await page.evaluate(() => eval("state.productionWorkTimer && window.clearTimeout(state.productionWorkTimer); state.productionWorkTimer = null"));
  let active = 0;
  let maximumActive = 0;
  let requestCount = 0;
  let releaseSummary;
  const summaryResponse = new Promise((resolve) => { releaseSummary = resolve; });
  await page.route(/\/api\/production-work-summary\?/, async (route) => {
    requestCount += 1;
    active += 1;
    maximumActive = Math.max(maximumActive, active);
    if (requestCount === 1) await summaryResponse;
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ current: {}, project: {} }) });
    active -= 1;
  });

  await page.evaluate(() => {
    window.wp02SummaryPromise = window.refreshProductionWorkSummary();
    void window.refreshProductionWorkSummary();
    void window.refreshProductionWorkSummary();
  });
  await expect.poll(() => page.evaluate(() => eval("state.productionWorkRefreshPending"))).toBe(true);
  await expect.poll(() => requestCount).toBe(1);
  releaseSummary();
  await page.evaluate(() => window.wp02SummaryPromise);
  await expect.poll(() => requestCount).toBe(2);
  expect(maximumActive).toBe(1);

  await page.evaluate(() => {
    window.wp02Hidden = true;
    Object.defineProperty(document, "hidden", { configurable: true, get: () => window.wp02Hidden });
    document.dispatchEvent(new Event("visibilitychange"));
    window.scheduleProductionWorkSummary(0);
  });
  await page.waitForTimeout(100);
  expect(requestCount).toBe(2);
  await page.evaluate(() => {
    window.wp02Hidden = false;
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect.poll(() => requestCount).toBe(3);
  expect(maximumActive).toBe(1);
});

test("WP03 direct scene entry uses ordered selection and browser history", async ({ page }) => {
  const scenes = (await (await page.request.get("/api/stories/Alpha-Story/scenes")).json()).scenes;
  expect(scenes).toHaveLength(8);
  const firstScene = scenes[0].slug;
  const lastScene = scenes.at(-1).slug;
  await page.goto(`/?page=scene-builder&story_slug=Alpha-Story&scene_slug=${firstScene}`);
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await expect(page.locator("#scene-builder-page")).toHaveClass(/active/);
  await expect(page.locator("#scene-builder-status")).toHaveText(`Alpha Story / ${scenes[0].title}`);
  await expect(page.locator("#scene-builder-previous")).toBeDisabled();
  await expect(page.locator("#scene-builder-next")).toBeEnabled();

  for (let index = 1; index < scenes.length; index += 1) {
    await page.locator("#scene-builder-next").click();
    await expect(page.locator("#scene-builder-status")).toHaveText(`Alpha Story / ${scenes[index].title}`);
    await expect.poll(() => page.evaluate(() => state.loadedBuilderContext.sceneSlug)).toBe(scenes[index].slug);
  }
  await expect(page.locator("#scene-builder-status")).toHaveText(`Alpha Story / ${scenes.at(-1).title}`);
  await expect(page.locator("#scene-builder-next")).toBeDisabled();
  await expect(page.locator("#scene-builder-previous")).toBeEnabled();

  expect(page.url()).toContain(`scene_slug=${encodeURIComponent(lastScene)}`);
  for (let index = scenes.length - 2; index >= 0; index -= 1) {
    await page.evaluate(() => window.history.back());
    await expect(page.locator("#scene-builder-page")).toHaveClass(/active/);
    await expect(page.locator("#scene-builder-status")).toHaveText(`Alpha Story / ${scenes[index].title}`);
    await expect.poll(() => page.evaluate(() => state.loadedBuilderContext.sceneSlug)).toBe(scenes[index].slug);
  }
  for (let index = 1; index < scenes.length; index += 1) {
    await page.evaluate(() => window.history.forward());
    await expect(page.locator("#scene-builder-status")).toHaveText(`Alpha Story / ${scenes[index].title}`);
    await expect.poll(() => page.evaluate(() => state.loadedBuilderContext.sceneSlug)).toBe(scenes[index].slug);
  }
});

test("WP03 rapid scene selection cannot stage a late previous document", async ({ page }) => {
  await openPage(page, "scenes");
  const delayed = delayedGate();
  let openingStarted;
  const openingRequest = new Promise((resolve) => { openingStarted = resolve; });
  await page.route(/\/api\/stories\/Alpha-Story\/scenes\/(Opening-Scene|Closing-Scene)$/, async (route) => {
    const scene = route.request().url().split("/").pop();
    if (scene === "Opening-Scene") {
      openingStarted();
      const response = await route.fetch();
      await delayed.promise;
      await route.fulfill({ response }).catch(() => {});
      return;
    }
    await route.continue();
  });

  const first = page.evaluate(() => selectStoryScene("Alpha-Story", "Opening-Scene", { skipGuard: true }));
  await openingRequest;
  await page.evaluate(() => selectStoryScene("Alpha-Story", "Closing-Scene", { skipGuard: true }));
  await expect(page.locator("#scene-editor-title")).toHaveText("Closing Scene");
  delayed.release();
  await first;
  await expect(page.locator("#scene-editor-title")).toHaveText("Closing Scene");
  await expect(page.locator("#scene-save")).toBeEnabled();
  await expect(page.locator("#scene-stage-render")).toBeEnabled();
});

test("WP03 scene mutations stay disabled until the requested document loads", async ({ page }) => {
  await openPage(page, "scenes");
  const currentScene = await page.locator("#header-scene-select").inputValue();
  const targetScene = await page.locator("#header-scene-select option").evaluateAll(
    (options, current) => options.find((item) => item.value && item.value !== current)?.value,
    currentScene,
  );
  const delayed = delayedGate();
  let requestStarted;
  const sceneRequest = new Promise((resolve) => { requestStarted = resolve; });
  await page.route(`**/api/stories/Alpha-Story/scenes/${targetScene}`, async (route) => {
    requestStarted();
    const response = await route.fetch();
    await delayed.promise;
    await route.fulfill({ response });
  });

  const selection = page.evaluate((sceneSlug) => selectStoryScene("Alpha-Story", sceneSlug, { skipGuard: true }), targetScene);
  await sceneRequest;
  for (const selector of ["#scene-save", "#scene-stage-render", "#scene-builder-open", "#scene-delete", "#scene-rename", "#scene-move"]) {
    await expect(page.locator(selector)).toBeDisabled();
  }
  delayed.release();
  await selection;
  await expect(page.locator("#scene-save")).toBeEnabled();
  await expect(page.locator("#scene-stage-render")).toBeEnabled();
});

test("WP03 a late Scene Builder response cannot replace the requested builder", async ({ page }) => {
  await openPage(page, "scenes");
  const delayed = delayedGate();
  let builderRequestStarted;
  const builderRequest = new Promise((resolve) => { builderRequestStarted = resolve; });
  await page.route((url) => new URL(url).pathname === "/api/stories/Alpha-Story/scenes/Opening-Scene/builder", async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    builderRequestStarted();
    const response = await route.fetch();
    await delayed.promise;
    await route.fulfill({ response }).catch(() => {});
  });

  const first = page.evaluate(() => selectStoryScene("Alpha-Story", "Opening-Scene", {
    skipGuard: true,
    destination: "scene-builder",
  }));
  await builderRequest;
  await page.evaluate(() => selectStoryScene("Alpha-Story", "Closing-Scene", {
    skipGuard: true,
    destination: "scene-builder",
  }));
  await expect(page.locator("#scene-builder-status")).toHaveText("Alpha Story / Closing Scene");
  expect(await page.evaluate(() => state.loadedBuilderContext)).toEqual({
    storySlug: "Alpha-Story",
    sceneSlug: "Closing-Scene",
  });
  delayed.release();
  await first;
  await expect(page.locator("#scene-builder-status")).toHaveText("Alpha Story / Closing Scene");
  await expect(page.locator("[data-builder-action='render']").first()).toBeEnabled();
});

test("WP03 rapid story selection cannot restore stale workspace context", async ({ page }) => {
  await openPage(page, "scenes");
  const delayed = delayedGate();
  let betaSummaryStarted;
  const summaryRequest = new Promise((resolve) => { betaSummaryStarted = resolve; });
  await page.route(/\/api\/workspace-summary\?.*story_slug=Beta-Story/, async (route) => {
    betaSummaryStarted();
    const response = await route.fetch();
    await delayed.promise;
    await route.fulfill({ response }).catch(() => {});
  });

  const first = page.evaluate(() => selectStoryScene("Beta-Story", "Opening-Scene", { skipGuard: true }));
  await summaryRequest;
  await page.evaluate(() => selectStoryScene("Gamma-Story", "Opening-Scene", { skipGuard: true }));
  await expect(page.locator("#header-story-select")).toHaveValue("Gamma-Story");
  await expect(page.locator("#scene-editor-title")).toHaveText("Opening Scene");
  delayed.release();
  await first;
  await expect(page.locator("#header-story-select")).toHaveValue("Gamma-Story");
  await expect(page.locator("#scene-save")).toBeEnabled();
});

test("WP03 invalid scene selections fall back to the canonical first scene", async ({ page }) => {
  await openPage(page, "scenes");
  const scenes = (await (await page.request.get("/api/stories/Alpha-Story/scenes")).json()).scenes;
  await page.evaluate(() => selectStoryScene("Alpha-Story", "Missing-Scene", { skipGuard: true }));
  await expect(page.locator("#header-scene-select")).toHaveValue(scenes[0].slug);
  await expect(page.locator("#scene-editor-title")).toHaveText(scenes[0].title);
});

test("WP03 To Do and Template Instruction Manuals open and report load failures", async ({ page }) => {
  await openPage(page, "local-batch-status");
  await page.locator("#toolbar-settings-button").click();
  await page.locator("#toolbar-todo-button").click();
  await expect(page.locator("#todo-dialog")).toBeVisible();
  await page.locator("#todo-dialog").evaluate((dialog) => dialog.close());

  await page.locator("#help-menu-button").click();
  await page.locator("#help-menu button[data-page='help']").click();
  await expect(page.locator("#help-page")).toHaveClass(/active/);
  await expect(page.locator("#help-status")).not.toHaveText("");

  await page.route("**/api/todo", (route) => route.fulfill({
    status: 500,
    contentType: "application/json",
    body: '{"detail":"Seeded To Do failure"}',
  }));
  await page.locator("#toolbar-settings-button").click();
  await page.locator("#toolbar-todo-button").click();
  await expect(page.locator("#action-message")).toContainText("Unable to open To Do: Seeded To Do failure");

  await page.evaluate(() => { state.templateManuals = []; });
  await page.route("**/api/help/template-manuals", (route) => route.fulfill({
    status: 500,
    contentType: "application/json",
    body: '{"detail":"Seeded manuals failure"}',
  }));
  await page.evaluate(() => activatePage("local-batch-status", { skipAutosave: true }));
  await page.locator("#help-menu-button").click();
  await page.locator("#help-menu button[data-page='help']").click();
  await expect(page.locator("#action-message")).toContainText(
    "Unable to open Template Instruction Manuals: Seeded manuals failure",
  );
});

test("Batches is persistent in the toolbar and links directly to the batch", async ({ page }) => {
  await page.route("**/api/local/batch-status", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      batch_count: 1,
      groups: [{ status: "AWAITING_FRONT_ANCHOR", label: "Awaiting FRONT anchor", batches: [{
        pipeline: "costume-dressing", pipeline_label: "Costume-Dressing", run_id: "batch-42",
        batch_name: "Winter coat", character: "Mira", phase: "Adult", costume: "Winter",
        status: "AWAITING_FRONT_ANCHOR", status_label: "Awaiting FRONT anchor", current_view: "",
      }] }],
    }),
  }));
  await openPage(page, "local-batch-status");

  await expect(page.locator('#local-assets-menu [data-page="local-batch-status"]')).toHaveCount(0);
  await expect(page.locator("#toolbar-batches")).toBeVisible();
  await expect(page.locator("#toolbar-batches")).toHaveText("Batches");
  expect(await page.locator("#toolbar-restart-zet").evaluate(node => node.nextElementSibling.id)).toBe("toolbar-batches");
  expect(await page.locator("#toolbar-batches").evaluate(node => node.nextElementSibling.querySelector("button").id)).toBe("toolbar-settings-button");
  await expect(page.locator("#local-assets-menu #local-run-all-remaining")).toHaveCount(0);
  await expect(page.locator("#local-batch-status-page #local-run-all-remaining")).toBeVisible();
  const link = page.locator("#local-batch-status-groups a");
  await expect(link).toHaveText("Mira/Adult/Winter coat");
  const href = new URL(await link.getAttribute("href"), page.url());
  expect(href.searchParams.get("page")).toBe("local-costume-dressing");
  expect(href.searchParams.get("character")).toBe("Mira");
  expect(href.searchParams.get("phase")).toBe("Adult");
  expect(href.searchParams.get("local_costume")).toBe("Winter");
  expect(href.searchParams.get("local_batch")).toBe("batch-42");
});

test("Batch Status refreshes while visible and reports empty and failed loads", async ({ page }) => {
  let requestCount = 0;
  await page.route("**/api/local/batch-status", (route) => {
    requestCount += 1;
    if (requestCount === 1) {
      return route.fulfill({ contentType: "application/json", body: '{"groups":[],"batch_count":0}' });
    }
    if (requestCount === 2) {
      return route.fulfill({ status: 503, contentType: "application/json", body: '{"detail":"Seeded batch status failure"}' });
    }
    return route.fulfill({ contentType: "application/json", body: '{"groups":[],"batch_count":0}' });
  });
  await openPage(page, "local-batch-status");
  await expect(page.locator("#local-batch-status-message")).toHaveText("No active or actionable batches.");
  await page.locator("#local-batch-status-refresh").click();
  await expect(page.locator("#local-batch-status-message")).toContainText("Seeded batch status failure");
  await expect.poll(() => requestCount, { timeout: 7000 }).toBeGreaterThan(2);
});

test("Run All Remaining starts from the top of Batch Status", async ({ page }) => {
  await page.route("**/api/local/batch-status", (route) => route.fulfill({
    contentType: "application/json", body: '{"groups":[],"batch_count":0}',
  }));
  await page.route("**/api/local/run-all-remaining", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ campaign_id: "campaign-1", status: "RUNNING", batches: [], batch_count: 0,
      progress: { RUNNING: 0 }, images_complete: 0, images_remaining: 0 }),
  }));
  await page.route("**/api/local/run-all-remaining/campaign-1", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ campaign_id: "campaign-1", status: "COMPLETE", batches: [], batch_count: 0,
      progress: { COMPLETE: 0 }, images_complete: 0, images_remaining: 0 }),
  }));
  await openPage(page, "local-batch-status");
  await page.locator("#local-run-all-remaining").click();
  await expect(page.locator("#local-run-all-status")).toContainText("Run all Remaining finished.");
  await expect(page.locator("#local-run-all-status")).toContainText("0/0 complete");
});

test("@desktop-smoke desktop layout does not overflow", async ({ page }) => {
  for (const [width, height] of DESKTOP_VIEWPORTS) {
    await page.setViewportSize({ width, height });
    await openPage(page, "local-batch-status");
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth))
      .toBe(true);
  }
});

test("retired Scene Appearances links resolve to local Assets", async ({ page }) => {
  await openPage(page, "local-batch-status");
  await page.evaluate(() => activatePage("scene-appearances", { skipAutosave: true }));
  await expect(page.locator("#local-batch-status-page")).toHaveClass(/active/);
  await expect(page.locator("#scene-appearances-page")).not.toHaveClass(/active/);
});

test("Image Inventory entity-library metadata and logical references use the supported editor", async ({ page }) => {
  await page.goto("/");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.locator("#workspace-character").click();
  await page.evaluate(() => window.activatePage("auxiliary-resources", { skipAutosave: true }));
  await expect(page.locator("#entity-library-search-view")).toBeVisible();
  const imported = await page.request.post("/api/entity-library/assets?label=Dashboard+Entity+Library+Fixture", {
    data: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/QioAAAAASUVORK5CYII=", "base64"),
    headers: { "content-type": "image/png" },
  });
  expect(imported.ok()).toBeTruthy();
  const asset = (await imported.json()).asset;
  await page.locator("#entity-library-search").fill("Dashboard Entity Library Fixture");
  await page.locator("#entity-library-refresh").click();
  const card = page.locator("#entity-library-results .image-catalog-card").filter({ hasText: "Dashboard Entity Library Fixture" });
  await expect(card).toBeVisible();
  const logical = await page.request.post("/api/entity-library/logical-references", {
    data: { reference_key: "dashboard.metadata.fixture", label: "Dashboard metadata fixture", asset_id: asset.asset_id },
  });
  expect(logical.ok()).toBeTruthy();
  await card.getByRole("button", { name: "Details" }).click();
  await expect(page.locator("#entity-library-detail-view")).toBeVisible();
  await expect(page.locator("#entity-library-logical-references")).toContainText("{{LIB:REF:dashboard.metadata.fixture}} · active");
});

test("Image Inventory preserves editable prompts in the entity-library detail", async ({ page }) => {
  await page.goto("/");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.locator("#workspace-character").click();
  await page.evaluate(() => window.activatePage("auxiliary-resources", { skipAutosave: true }));
  await expect(page.locator("#entity-library-search-view")).toBeVisible();
  const imported = await page.request.post("/api/entity-library/assets?label=Dashboard+Prompt+Fixture", {
    data: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aS8kAAAAASUVORK5CYII=", "base64"),
    headers: { "content-type": "image/png" },
  });
  expect(imported.ok()).toBeTruthy();
  const asset = (await imported.json()).asset;
  await page.locator("#entity-library-search").fill("Dashboard Prompt Fixture");
  await page.locator("#entity-library-refresh").click();
  const card = page.locator("#entity-library-results .image-catalog-card").filter({ hasText: "Dashboard Prompt Fixture" });
  await card.getByRole("button", { name: "Details" }).click();
  await page.locator("#entity-library-edit-prompt").fill("A bronze owl at dusk");
  await page.locator("#entity-library-edit-negative-prompt").fill("words, extra wings");
  await page.getByRole("button", { name: "Save image" }).click();
  await expect.poll(async () => (await (await page.request.get(`/api/entity-library/assets/${asset.asset_id}`)).json()).asset.prompt)
    .toBe("A bronze owl at dusk");
  const saved = (await (await page.request.get(`/api/entity-library/assets/${asset.asset_id}`)).json()).asset;
  expect(saved.negative_prompt).toBe("words, extra wings");
  await expect(page.locator("#entity-library-modify-generated")).toBeVisible();
});

test("@desktop-smoke workspace shell switches adaptive context and remembers the last page", async ({ page }) => {
  await page.goto("/");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.locator("#workspace-character").click();
  await expect(page.locator("#workspace-character")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#onboarding-page")).toHaveClass(/active/);
  await page.evaluate(() => window.activatePage("turnarounds", { skipAutosave: true }));
  await expect(page.locator("#turnarounds-page")).toHaveClass(/active/);
  await expect(page.locator("#workspace-character")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#character-context")).toBeVisible();
  await expect(page.locator("#story-context")).toBeHidden();

  await page.locator("#workspace-story").click();
  await expect(page.locator("#workspace-story")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#story-context")).toBeVisible();
  await expect(page.locator("#character-context")).toBeHidden();
  await page.locator("#story-navigation button[data-page='scenes']").click();
  await expect(page.locator("#scenes-page")).toHaveClass(/active/);

  await page.reload();
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await expect(page.locator("#workspace-story")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#scenes-page")).toHaveClass(/active/);

  await page.locator("#workspace-character").click();
  await expect(page.locator("#turnarounds-page")).toHaveClass(/active/);
});












test("@desktop-smoke story changes require explicit save and guard selection changes", async ({ page }) => {
  await openPage(page, "stories");
  const rows = page.locator("#story-table .row-selection-button");
  await expect(rows).toHaveCount(3);
  await rows.nth(0).click();
  const editor = page.locator("#story-text");
  await editor.fill("Title: `[Alpha Story]`\n\nUnsaved browser change.\n");
  await expect(page.locator("#story-save-state")).toContainText("Dirty");
  await rows.nth(1).click();
  const dialog = page.locator("#unsaved-changes-dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(page.locator("#story-table tr.selected")).toContainText("Alpha Story");
  await rows.nth(1).click();
  await dialog.getByRole("button", { name: "Discard" }).click();
  const saved = await page.request.get("/api/stories/Alpha-Story");
  expect((await saved.json()).document.text).not.toContain("Unsaved browser change.");
});



test("@desktop-smoke scene and Scene Builder changes require explicit save", async ({ page }) => {
  await openPage(page, "scenes");
  const rows = page.locator("#scene-table .row-selection-button");
  await expect(rows).toHaveCount(8);
  const initialSceneSlug = await page.locator("#scene-table tr.selected").getAttribute("data-scene-slug");
  const initialSceneText = await page.locator("#scene-text").inputValue();
  const initialSceneTitle = initialSceneText.split("\n", 1)[0];
  await page.locator("#scene-text").fill(`${initialSceneTitle}\n\nUnsaved scene change.\n`);
  await page.locator("#scene-table tr:not(.selected) .row-selection-button").first().click();
  const dialog = page.locator("#unsaved-changes-dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Discard" }).click();
  await expect
    .poll(() => page.locator("#scene-table tr.selected").getAttribute("data-scene-slug"))
    .not.toBe(initialSceneSlug);
  const saved = await page.request.get(`/api/stories/Alpha-Story/scenes/${initialSceneSlug}`);
  expect((await saved.json()).document.text).not.toContain("Unsaved scene change.");

  const selectedSceneSlug = await page.locator("#scene-table tr.selected").getAttribute("data-scene-slug");
  await page.route(`**/api/stories/Alpha-Story/scenes/${selectedSceneSlug}`, async (route) => {
    if (route.request().method() === "PUT") {
      await route.fulfill({ status: 500, contentType: "application/json", body: '{"detail":"Seeded scene save failure"}' });
    } else {
      await route.continue();
    }
  });
  await page.locator("#scene-text").fill("Scene save must fail.");
  await page.locator("#scene-save").click();
  await expect(page.locator("#scene-save-state")).toContainText("Error");
  await expect(page.locator("#scene-table tr.selected")).toHaveAttribute("data-scene-slug", selectedSceneSlug);
  await page.unroute(`**/api/stories/Alpha-Story/scenes/${selectedSceneSlug}`);
  const sceneSaved = page.waitForResponse((response) => response.url().endsWith(`/api/stories/Alpha-Story/scenes/${selectedSceneSlug}`) && response.request().method() === "PUT" && response.ok());
  await page.locator("#scene-save").click();
  await sceneSaved;

  await rows.nth(0).click();
  const referencesRefreshed = page.waitForResponse((response) => response.url().includes("/api/scene-image-picker"));
  await page.locator("#scene-builder-open").click();
  await referencesRefreshed;
  await expect(page.locator("#scene-builder-page")).toHaveClass(/active/);
  const storyBeat = page.locator('[data-builder-field="scene.story_beat"]');
  const originalStoryBeat = await storyBeat.inputValue();
  await storyBeat.fill("Unsaved builder beat.");
  await page.locator("button[data-page='stories']").click();
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(page.locator("#scene-builder-page")).toHaveClass(/active/);
  await page.locator("button[data-page='stories']").click();
  await dialog.getByRole("button", { name: "Discard" }).click();
  await expect(page.locator("#stories-page")).toHaveClass(/active/);
  await openPage(page, "scenes");
  await page.locator("#scene-builder-open").click();
  await expect(page.locator('[data-builder-field="scene.story_beat"]')).toHaveValue(originalStoryBeat);
  await page.route("**/api/stories/*/scenes/*/builder", async (route) => {
    if (route.request().method() === "PUT") {
      await route.fulfill({ status: 500, contentType: "application/json", body: '{"detail":"Seeded builder save failure"}' });
    } else {
      await route.continue();
    }
  });
  await page.locator('[data-builder-field="scene.story_beat"]').fill("Builder save must fail.");
  await page.locator("[data-builder-action='save']").first().click();
  await expect(page.locator("#scene-builder-page")).toHaveClass(/active/);
  await expect(page.locator("#scene-builder-message")).toContainText("Seeded builder save failure");
  await page.unroute("**/api/stories/*/scenes/*/builder");
});

test("@desktop-smoke Scene Builder adds, reorders, and removes multiple references", async ({ page }) => {
  await openPage(page, "scenes");
  await page.locator("#scene-builder-open").click();
  await expect(page.locator('[data-builder-field="scene.story_beat"]')).toBeVisible();
  await page.evaluate(() => {
    const element = {
      id: "reference-test", display_name: "Reference Test", resource_type: "Scene-Only",
      element_type: "Character", reference_images: [], fallback_visual_description: "Test subject",
    };
    state.sceneBuilder.scene_elements = [element];
    state.sceneBuilder.placements = [{ id: "reference-test-placement", scene_element_id: element.id, position_within_cell: "center", depth: "foreground", pose: {}, motion: { state: "stationary" } }];
    state.selectedBuilderElementId = element.id;
    renderSceneBuilder();
  });

  await page.getByRole("button", { name: "Add reference" }).click();
  await page.getByRole("button", { name: "Add reference" }).click();
  const tags = page.locator('[data-builder-reference-field="tag"]');
  await tags.nth(0).fill("{{ASSET:first}}");
  await tags.nth(1).fill("{{AUX:second}}");
  await page.locator('[data-builder-action="reference-down"][data-builder-reference-index="0"]').click();
  await expect(tags.nth(0)).toHaveValue("{{AUX:second}}");
  await expect(tags.nth(1)).toHaveValue("{{ASSET:first}}");
  await page.locator('[data-builder-action="reference-remove"][data-builder-reference-index="0"]').click();
  await expect(tags).toHaveCount(1);
  await expect(tags.nth(0)).toHaveValue("{{ASSET:first}}");
});

test("Scene Builder selects costume images through their current logical reference", async ({ page }) => {
  await openPage(page, "scenes");
  await page.locator("#scene-builder-open").click();
  await expect(page.locator('[data-builder-field="scene.story_beat"]')).toBeVisible();
  await page.evaluate(() => {
    state.characters = ["Tsaeytte"];
    state.phasesByCharacter = { Tsaeytte: ["Youth"] };
    const element = {
      id: "tsaeytte-test", display_name: "Tsaeytte", resource_type: "Character",
      character: "Tsaeytte", phase: "Youth", costume: "Woodland outfit", reference_images: [],
      fallback_visual_description: "Tsaeytte in a woodland outfit",
    };
    state.sceneBuilder.scene_elements = [element];
    state.sceneBuilder.placements = [{ id: "tsaeytte-test-placement", scene_element_id: element.id, position_within_cell: "center", depth: "foreground", pose: {}, motion: { state: "stationary" } }];
    state.selectedBuilderElementId = element.id;
    renderSceneBuilder();
  });
  await page.getByRole("button", { name: "Add reference" }).click();
  await page.route("**/api/entity-library/picker*", (route) => route.fulfill({ json: { assets: [{
    asset_id: "test-image", file_name: "generated.png", label: "Tsaeytte · Youth · Woodland outfit · Front",
    image_path: "/images/test.png", thumbnail_path: "/images/test.png", origin: "pipeline",
    logical_reference: { reference_key: "tsaeytte.youth.costume-dressing.woodland-outfit.front" },
    entities: [{ name: "Tsaeytte", variant_name: "Youth" }], width: 32, height: 32,
  }] } }));
  await page.locator('[data-builder-action="pick-image-tag"]').click();
  await expect(page.locator("#builder-image-picker-mode")).toHaveValue("logical");
  await expect(page.locator("#builder-image-picker-search")).toHaveValue("Tsaeytte Youth Woodland outfit");
  await page.locator("#builder-image-picker-table tbody tr").first().click();
  const selected = await page.evaluate(() => state.sceneBuilder.scene_elements[0].reference_images[0]);
  expect(selected.reference_key).toBe("tsaeytte.youth.costume-dressing.woodland-outfit.front");
  expect(selected.asset_id).toBeUndefined();
});

test("retired Render Console routes resolve to Scene Renders", async ({ page }) => {
  await page.goto("/?page=render-console");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await expect(page.locator("#scene-batches-page")).toHaveClass(/active/);
  await expect(page.locator("#scene-batches-page h1")).toHaveText("Scene Renders");
  await expect(page.locator("#render-console-page")).not.toHaveClass(/active/);
});

test("retired Render Console controls are absent from Scene Renders", async ({ page }) => {
  await openPage(page, "scene-batches");
  await expect(page.locator("#scene-batches-page")).toHaveClass(/active/);
  await expect(page.locator("#scene-batches-page #render-console-refinement-required, #scene-batches-page #render-console-reference-files")).toHaveCount(0);
});

test("@desktop-smoke Scene Builder interview applies locally without saving", async ({ page }) => {
  await openPage(page, "scenes");
  await page.locator("#scene-builder-open").click();
  await expect(page.locator('[data-builder-field="scene.story_beat"]')).toBeVisible();
  const draft = await page.evaluate(() => structuredClone(state.sceneBuilder));
  draft.scene.story_beat = "Interview draft beat";
  let builderPutCount = 0;
  page.on("request", (request) => {
    if (request.method() === "PUT" && request.url().endsWith("/builder")) builderPutCount += 1;
  });
  await page.route("**/builder/interview", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ session: "browser-test", complete: true, total_phases: 1, questions: [], draft }),
    });
  });

  await page.getByRole("button", { name: "Interview", exact: true }).click();
  await page.locator("#scene-builder-interview-narrative").fill("A concise scene description.");
  await page.locator("#scene-builder-interview-next").click();
  await expect(page.locator("#scene-builder-interview-apply")).toBeVisible();
  // A completed interview survives both reopening and a full page reload.
  await page.evaluate(() => document.querySelector("#scene-builder-interview-modal").close());
  await page.getByRole("button", { name: "Interview", exact: true }).click();
  await expect(page.locator("#scene-builder-interview-narrative")).toHaveValue("A concise scene description.");
  await expect(page.locator("#scene-builder-interview-apply")).toBeVisible();
  await page.reload();
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.evaluate(() => window.activatePage("scenes", { skipAutosave: true }));
  await page.locator("#scene-builder-open").click();
  await page.getByRole("button", { name: "Interview", exact: true }).click();
  await expect(page.locator("#scene-builder-interview-apply")).toBeVisible();
  await page.locator("#scene-builder-interview-apply").click();

  await expect(page.locator('[data-builder-field="scene.story_beat"]')).toHaveValue("Interview draft beat");
  await expect(page.locator("#scene-builder-save-state")).toHaveText("Dirty");
  expect(builderPutCount).toBe(0);
  await page.locator("button[data-page='stories']").click();
  await expect(page.locator("#unsaved-changes-dialog")).toBeVisible();
});







test("traditional asset routes resolve into the consolidated Assets workflow", async ({ page }) => {
  await openPage(page, "local-batch-status");
  await page.evaluate(() => activatePage("assets", { skipAutosave: true }));
  await expect(page.locator("#local-batch-status-page")).toHaveClass(/active/);
  await expect(page.locator("#assets-page")).not.toHaveClass(/active/);
});

test("@desktop-smoke selection, zine ordering, live status, and image dialogs are accessible", async ({ page }) => {
  await openPage(page, "zine");
  const selection = page.locator("#zine-table .row-selection-button").first();
  await selection.focus();
  await page.keyboard.press("Enter");
  await expect(selection).toHaveAttribute("aria-current", "true");
  await expect(page.locator("#zine-editor-title")).toHaveText("Browser Zine");
  await expect(page.locator(".zine-slot-groups > section > h3")).toHaveText([
    "Front",
    "Pages 1–2",
    "Pages 3–4",
    "Pages 5–6",
    "Back",
  ]);
  await expect(page.locator("#zine-front")).toHaveCount(1);
  await expect(page.locator("#zine-back")).toHaveCount(1);
  await expect(page.locator(".status-text").first()).toHaveAttribute("role", "status");

  await expect(page.locator("#zine-preview-section")).toBeVisible();
  await page.locator(".fullscreen-image-button:has(#zine-preview)").click();
  const imageDialog = page.locator(".fullscreen-image-overlay");
  await expect(imageDialog).toBeVisible();
  await expect(imageDialog.getByRole("button", { name: "Close full-size image" })).toBeFocused();
  const fullscreenLayout = await imageDialog.evaluate((dialog) => {
    const image = dialog.querySelector(":scope > img");
    const imageRect = image.getBoundingClientRect();
    return {
      dialogHeight: dialog.getBoundingClientRect().height,
      dialogWidth: dialog.getBoundingClientRect().width,
      hasHorizontalScroll: dialog.scrollWidth > dialog.clientWidth,
      hasVerticalScroll: dialog.scrollHeight > dialog.clientHeight,
      imageHeight: imageRect.height,
      imageWidth: imageRect.width,
      viewportHeight: window.innerHeight,
      viewportWidth: window.innerWidth,
    };
  });
  expect(fullscreenLayout.hasHorizontalScroll).toBe(false);
  expect(fullscreenLayout.hasVerticalScroll).toBe(false);
  expect(fullscreenLayout.dialogHeight).toBe(fullscreenLayout.viewportHeight);
  expect(fullscreenLayout.dialogWidth).toBe(fullscreenLayout.viewportWidth);
  expect(fullscreenLayout.imageHeight).toBeLessThanOrEqual(fullscreenLayout.dialogHeight);
  expect(fullscreenLayout.imageWidth).toBeLessThanOrEqual(fullscreenLayout.dialogWidth);
  await page.keyboard.press("Escape");
  await expect(imageDialog).not.toBeVisible();
});





test("@desktop-smoke scene workflow keeps context and production tools show all work", async ({ page }) => {
  await openPage(page, "scenes");
  await page.locator("#header-scene-select").selectOption("Closing-Scene");

  await page.evaluate(() => activatePage("render-console", { skipAutosave: true }));
  await expect(page.locator("#scene-batches-page")).toHaveClass(/active/);
  await expect(page.locator("#header-story-select")).toHaveValue("Alpha-Story");
  await expect(page.locator("#header-scene-select")).toHaveValue("Closing-Scene");

  await page.locator("#scene-workflow-menu").selectOption("prompt-review");
  await expect(page.locator("#prompt-review-page")).toHaveClass(/active/);
  await expect(page.locator("#header-story-select")).toHaveValue("Alpha-Story");
  await expect(page.locator("#header-scene-select")).toHaveValue("Closing-Scene");

  await page.locator("#scene-workflow-menu").selectOption("locked-image");
  await expect(page.locator(".fullscreen-image-overlay")).toBeVisible();
  await expect(page.locator(".fullscreen-image-overlay > img")).toHaveAttribute("src", /Closing-Scene\.png/);
  await page.keyboard.press("Escape");
});

test("@desktop-smoke Scene Builder creates and selects a reference set without losing context", async ({ page }) => {
  await openPage(page, "scenes");
  await page.locator("#scene-builder-open").click();
  await page.getByRole("button", { name: "Add Element" }).click();
  await page.locator("#builder-element-resource-type").selectOption("Object");
  await page.locator("#builder-element-new-aux").click();
  await page.locator("#builder-element-new-aux-label").fill("Story Lantern");
  const created = page.waitForResponse((response) => (
    response.url().endsWith("/api/image-catalog/reference-sets") && response.request().method() === "POST"
  ));
  await page.locator("#builder-element-new-aux-save").click();
  const createdResponse = await created;
  expect(createdResponse.ok()).toBe(true);
  const resource = (await createdResponse.json()).reference_set;

  await expect(page.locator("#builder-element-modal")).toBeVisible();
  await expect(page.locator("#builder-element-aux")).toHaveValue(resource.reference_set_id);
  await expect(page.locator("#header-story-select")).toHaveValue("Alpha-Story");
  await expect(page.locator("#header-scene-select")).not.toHaveValue("");
  await page.locator("#builder-element-add").click();
  await expect(page.locator(".scene-builder-element-list")).toContainText("Story Lantern");
});






test("@desktop-smoke Scene Builder manages a background render target", async ({ page }) => {
  await openPage(page, "scenes");
  const storySlug = await page.locator("#header-story-select").inputValue();
  const sceneSlug = await page.locator("#header-scene-select").inputValue();
  const detail = await page.request.get(`/api/stories/${storySlug}/scenes/${sceneSlug}/builder`);
  const data = (await detail.json()).document.data;
  data.scene_elements = [
    { id: "hall", display_name: "Hall", resource_type: "Scene-Only", element_type: "Backdrop", fallback_visual_description: "stone hall", subscene_id: "" },
    { id: "hero", display_name: "Hero", resource_type: "Scene-Only", element_type: "Character", fallback_visual_description: "armored hero", subscene_id: "" },
  ];
  data.placements = [
    { id: "hall-placement", scene_element_id: "hall", position_within_cell: "", depth: "distant background" },
    { id: "hero-placement", scene_element_id: "hero", position_within_cell: "center", depth: "foreground" },
  ];
  const saved = await page.request.put(`/api/stories/${storySlug}/scenes/${sceneSlug}/builder`, { data });
  expect(saved.ok()).toBe(true);

  await openPage(page, "scenes");
  await page.locator("#scene-builder-open").click();
  const editorBox = await page.locator(".scene-builder-element-editor").boundingBox();
  const fieldsetBox = await page.locator(".scene-builder-element-editor fieldset").boundingBox();
  expect(Math.abs(editorBox.width - fieldsetBox.width)).toBeLessThan(1);
  const enabled = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname.endsWith("/subscenes/background/enable") && response.request().method() === "POST" && response.ok();
  });
  await page.getByRole("button", { name: "Use background sub-render" }).click();
  await enabled;
  const backgroundTarget = page.locator('.scene-builder-target-tree [data-render-target-id="background"]');
  await expect(backgroundTarget).toHaveClass(/selected/);
  await expect(page.locator(".scene-builder-active-target")).toHaveText("Editing Subscene: Background");
  await expect(page.locator(".scene-builder-element-list")).toContainText("Hall");
  await expect(page.locator(".scene-builder-element-row").filter({ hasText: "Hero" })).toHaveClass(/context-only/);
  await page.locator(".builder-context-toggle input").uncheck();
  await expect(page.locator(".scene-builder-element-list")).not.toContainText("Hero");

  await page.locator(".scene-builder-render").first().click();
  await expect(page.locator("#scene-batches-page")).toHaveClass(/active/);
  await page.evaluate(() => activatePage("scene-builder", { skipAutosave: true }));
  await expect(page.locator("#scene-builder-open")).toBeEnabled();
  await page.locator('.scene-builder-target-tree [data-render-target-id="background"]').click();
  await expect(page.locator('.scene-builder-target-tree [data-render-target-id="background"]')).toHaveClass(/selected/);
  await page.locator('.scene-builder-target-tree [data-render-target-id="main"]').click();

  await page.getByRole("button", { name: "Add Element" }).click();
  await page.locator("#builder-element-resource-type").selectOption("Scene-Only");
  await page.locator("#builder-element-scene-name").fill("Background Statue");
  await page.locator("#builder-element-add").click();
  await expect(page.locator(".scene-builder-element-list")).toContainText("Background Statue");
  await page.locator("[data-builder-element-field='subscene_id']").selectOption("background");
  await expect(page.locator("[data-builder-element-field='subscene_id']")).toHaveValue("background");
  expect(await page.evaluate(() => state.sceneBuilder.scene_elements.find((item) => item.display_name === "Background Statue")?.subscene_id)).toBe("background");

  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await expect.poll(() => page.locator(".scene-builder-sticky-context").evaluate((element) => Math.round(element.getBoundingClientRect().top))).toBe(0);
  await page.evaluate(() => window.scrollTo(0, 0));

  await page.locator('.scene-builder-target-tree [data-render-target-id="main"]').click();
  await expect(page.locator(".scene-builder-active-target")).toHaveText("Editing Full Scene");
  await page.locator(".scene-builder-element-row").filter({ hasText: "Hero" }).evaluate((element) => element.click());
  await page.locator("[data-builder-element-field='subscene_id']").evaluate((select) => {
    select.value = "background";
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await expect(page.locator("[data-builder-element-field='subscene_id']")).toHaveValue("background");
  await expect(page.locator("#scene-builder-save-state")).toContainText("Dirty");
  const fullSceneSaved = page.waitForResponse((response) => response.url().endsWith("/builder") && response.request().method() === "PUT" && response.ok());
  await page.getByRole("button", { name: "Save Full Scene", exact: true }).click();
  await fullSceneSaved;
  const persistedAfterAdd = await page.request.get(`/api/stories/${storySlug}/scenes/${sceneSlug}/builder`);
  const persistedAddedElement = (await persistedAfterAdd.json()).document.data.scene_elements.find((item) => item.display_name === "Background Statue");
  expect(persistedAddedElement?.subscene_id).toBe("background");

  await expect(page.locator(".scene-builder-render").first()).toBeEnabled();
  const disabled = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname.endsWith("/subscenes/background/disable") && response.request().method() === "POST" && response.ok();
  });
  await page.getByRole("button", { name: "Turn off background sub-render" }).click();
  await disabled;
  await expect(page.locator(".scene-builder-render").first()).toBeEnabled();
});

test("@desktop-smoke Scene Builder creates assignable colored sub-scenes", async ({ page }) => {
  await openPage(page, "scenes");
  const storySlug = await page.locator("#header-story-select").inputValue();
  await page.locator("#header-scene-select").selectOption("Opening-Scene");
  await expect(page.locator("#header-scene-select")).toHaveValue("Opening-Scene");
  const sceneSlug = await page.locator("#header-scene-select").inputValue();
  const detail = await page.request.get(`/api/stories/${storySlug}/scenes/${sceneSlug}/builder`);
  const data = (await detail.json()).document.data;
  data.subscenes = [];
  data.scene_elements = [
    { id: "travelers", display_name: "Travelers", resource_type: "Scene-Only", element_type: "Prop", fallback_visual_description: "a roped group of travelers", subscene_id: "" },
    { id: "devil", display_name: "Devil", resource_type: "Scene-Only", element_type: "Monster", fallback_visual_description: "a large devil", subscene_id: "" },
  ];
  data.placements = [
    { id: "travelers-placement", scene_element_id: "travelers", position_within_cell: "left", depth: "midground" },
    { id: "devil-placement", scene_element_id: "devil", position_within_cell: "right", depth: "midground" },
  ];
  const saved = await page.request.put(`/api/stories/${storySlug}/scenes/${sceneSlug}/builder`, { data });
  expect(saved.ok()).toBe(true);

  await openPage(page, "scenes");
  await page.locator("#header-scene-select").selectOption("Opening-Scene");
  await expect(page.locator("#header-scene-select")).toHaveValue("Opening-Scene");
  await page.locator("#scene-builder-open").click();
  await page.locator(".scene-builder-element-row").filter({ hasText: "Travelers" }).click();
  await page.locator(".scene-builder-element-menu summary").click();
  await expect(page.getByRole("button", { name: "Create subscene from this element", exact: true })).toBeVisible();
  const created = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname.endsWith(`/subscenes/elements/${encodeURIComponent("travelers")}/enable`) && response.request().method() === "POST" && response.ok();
  });
  await page.getByRole("button", { name: "Create subscene from this element", exact: true }).click();
  const createdPayload = await (await created).json();
  const targetId = createdPayload.render_target_id;
  const target = page.locator(`.scene-builder-target-tree [data-render-target-id="${targetId}"]`);
  await expect(target).toBeVisible();
  expect(await page.evaluate((id) => state.sceneBuilder.subscenes.find((item) => item.id === id)?.anchor_element_id, targetId)).toBe("travelers");
  await page.getByRole("button", { name: "Color 3" }).click();
  const subsceneSaved = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname.endsWith(`/builder/subscenes/${targetId}`) && response.request().method() === "PUT" && response.ok();
  });
  await page.getByRole("button", { name: "Save Subscene", exact: true }).click();
  await subsceneSaved;
  await expect(target).toHaveAttribute("style", /#F3E1E7/);
});

test("@desktop-smoke subscene save and cancel are scoped to the active target", async ({ page }) => {
  await openPage(page, "scenes");
  const storySlug = await page.locator("#header-story-select").inputValue();
  const sceneSlug = await page.locator("#header-scene-select").inputValue();
  const detail = await page.request.get(`/api/stories/${storySlug}/scenes/${sceneSlug}/builder`);
  const data = (await detail.json()).document.data;
  data.subscenes = [];
  data.scene.story_beat = "Persisted story beat";
  data.scene_elements = [
    { id: "hall", display_name: "Hall", resource_type: "Scene-Only", element_type: "Backdrop", fallback_visual_description: "stone hall", subscene_id: "" },
  ];
  data.placements = [
    { id: "hall-placement", scene_element_id: "hall", position_within_cell: "", depth: "background" },
  ];
  expect((await page.request.put(`/api/stories/${storySlug}/scenes/${sceneSlug}/builder`, { data })).ok()).toBe(true);
  expect((await page.request.post(`/api/stories/${storySlug}/scenes/${sceneSlug}/subscenes/background/enable`)).ok()).toBe(true);

  const withSubscene = await page.request.get(`/api/stories/${storySlug}/scenes/${sceneSlug}/builder`);
  const dialogueData = (await withSubscene.json()).document.data;
  dialogueData.scene_elements.push({ id: "speaker", display_name: "Speaker", resource_type: "Scene-Only", element_type: "Character", fallback_visual_description: "A clear speaking character", subscene_id: "background" });
  dialogueData.placements.push({ id: "speaker-placement", scene_element_id: "speaker", position_within_cell: "left", depth: "foreground" });
  dialogueData.dialogue = [{ id: "line", speaker_element_id: "speaker", subscene_id: "background", text: "Original line.", pointer_target: "speaker mouth" }];
  expect((await page.request.put(`/api/stories/${storySlug}/scenes/${sceneSlug}/builder`, { data: dialogueData })).ok()).toBe(true);

  await page.locator("#scene-builder-open").click();
  await page.locator('[data-builder-field="scene.story_beat"]').fill("Unsaved full-scene beat");
  await page.locator('[data-builder-action="select-render-target"][data-render-target-id="background"]').click();
  const focalPoint = page.locator('[data-builder-subscene-field="focal_point"]');
  await focalPoint.fill("Distant ruined tower");
  const dialogueText = page.locator('[data-builder-dialogue="0"][data-builder-dialogue-field="text"]');
  await expect(dialogueText).toHaveValue("Original line.");
  await dialogueText.fill("Updated line.");
  await page.locator('[data-builder-dialogue="0"][data-builder-dialogue-field="panel_placement"]').selectOption("right");
  const scopedSave = page.waitForRequest((request) => request.url().endsWith("/builder/subscenes/background") && request.method() === "PUT");
  await page.getByRole("button", { name: "Save Subscene", exact: true }).click();
  const saveRequest = await scopedSave;
  expect((await saveRequest.postDataJSON()).subscene.id).toBe("background");
  expect((await saveRequest.postDataJSON()).dialogue_changes.upserts[0].dialogue.text).toBe("Updated line.");
  expect(await page.evaluate(() => state.sceneBuilder.scene.story_beat)).toBe("Unsaved full-scene beat");
  await expect(page.locator("#scene-builder-save-state")).toContainText("other changes dirty");

  const persisted = await page.request.get(`/api/stories/${storySlug}/scenes/${sceneSlug}/builder`);
  const persistedData = (await persisted.json()).document.data;
  expect(persistedData.scene.story_beat).toBe("Persisted story beat");
  expect(persistedData.subscenes.find((item) => item.id === "background").prompt_overrides.focal_point).toBe("Distant ruined tower");
  expect(persistedData.dialogue[0].text).toBe("Updated line.");
  expect(persistedData.dialogue[0].panel_placement).toBe("right");

  await page.locator('[data-builder-action="select-render-target"][data-render-target-id="main"]').first().click();
  const fullSceneSaved = page.waitForResponse((response) => response.url().endsWith("/builder") && response.request().method() === "PUT");
  await page.getByRole("button", { name: "Save Full Scene", exact: true }).click();
  expect((await fullSceneSaved).ok()).toBe(true);
  const persistedFullScene = await page.request.get(`/api/stories/${storySlug}/scenes/${sceneSlug}/builder`);
  expect((await persistedFullScene.json()).document.data.scene.story_beat).toBe("Unsaved full-scene beat");

  await page.locator('[data-builder-action="select-render-target"][data-render-target-id="background"]').click();

  await focalPoint.fill("Wrong target edit");
  await page.getByRole("button", { name: "Cancel Subscene Edits", exact: true }).click();
  await expect(focalPoint).toHaveValue("Distant ruined tower");
  expect(await page.evaluate(() => state.sceneBuilder.scene.story_beat)).toBe("Unsaved full-scene beat");

  await page.locator('[data-builder-action="select-render-target"][data-render-target-id="main"]').first().click();
  await page.locator('[data-builder-field="scene.story_beat"]').fill("Save all before Scene Batches");
  await page.locator('[data-builder-action="select-render-target"][data-render-target-id="background"]').click();
  const slotGroup = (targetId) => ({
    status: "PENDING", candidates: Array.from({ length: 8 }, (_, index) => ({
      candidate_id: `${targetId}-${String(index + 1).padStart(3, "0")}`, slot: index + 1, status: "EMPTY",
    })),
  });
  const slotRun = {
    run_id: "a".repeat(32), status: "QUEUED", targets: [
      { target_id: "background", label: "Background", kind: "background", dependencies: [] },
      { target_id: "main", label: "Full Scene", kind: "main", dependencies: ["background"] },
    ], groups: { background: slotGroup("background"), main: slotGroup("main") },
    selected_views: {}, rankings: {}, view_reviews: {}, ready_targets: ["background"],
  };
  slotRun.groups.main.history_candidates = [
    { candidate_id: "main-old-001", slot: 1, status: "COMPLETE", image_path: "old.png" },
  ];
  slotRun.view_reviews.main = { observations: "Old notes", ai_observations: { status: "COMPLETE", text: "Old analysis" } };
  await page.route(`**/api/stories/${storySlug}/scenes/${sceneSlug}/local-batches**`, async (route) => {
    if (route.request().method() === "GET" && !route.request().url().endsWith(slotRun.run_id)) {
      return route.fulfill({ json: { batches: [slotRun], linked_batch_id: slotRun.run_id } });
    }
    return route.fulfill({ json: slotRun });
  });
  await page.locator(".workflow-tab[data-page='scene-batches']").click();
  const navigationDialog = page.locator("#unsaved-changes-dialog");
  await expect(navigationDialog).toBeVisible();
  const navigationSave = page.waitForResponse((response) => response.url().endsWith("/builder") && response.request().method() === "PUT" && response.ok());
  await navigationDialog.getByRole("button", { name: "Save" }).click();
  await navigationSave;
  await expect(page.locator("#scene-batches-page")).toHaveClass(/active/);
  await expect(page.locator("#scene-batches-page h1")).toHaveText("Scene Renders");
  await expect(page.locator(".scene-batch-candidates .local-pipeline-candidate")).toHaveCount(16);
  await expect(page.locator("#scene-batches-page").getByText("Earlier render")).toHaveCount(0);
  await expect(page.locator("#scene-batches-page").getByText("Observations")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Retry", exact: true })).toHaveCount(16);
  await expect(page.getByRole("button", { name: "Clear", exact: true })).toHaveCount(16);
  const savedBeforeNavigation = await page.request.get(`/api/stories/${storySlug}/scenes/${sceneSlug}/builder`);
  expect((await savedBeforeNavigation.json()).document.data.scene.story_beat).toBe("Save all before Scene Batches");
});

test("@desktop-smoke imported candidate context and prompt analysis use side panels", async ({ page }) => {
  await openPage(page, "scenes");
  await page.locator("#scene-builder-open").click();
  await expect(page.locator("#scene-builder-page")).toHaveClass(/active/);
  await expect(page.locator("#scene-builder-message")).toHaveText("Scene Builder loaded.");
  await expect(page.locator("#scene-builder-panel .scene-builder-toolbar")).toBeVisible();
  await page.evaluate(() => {
    state.sceneBuilder.source_provenance = {
      source_type: "scene_candidate_markdown",
      candidate_id: "adventure-log-entry",
      constraints: {
        exact_details: ["Keep the cracked lantern"],
        continuity_requirements: ["The party remains wet from the storm"],
      },
    };
    state.sceneBuilderReadiness = { status: "needs_attention", blockers: ["Resolve the missing guide"] };
    renderSceneBuilder();
  });
  const attentionBadge = page.locator(".scene-builder-sticky-context .status-badge");
  await expect(attentionBadge).toHaveText("Needs attention");
  await expect(attentionBadge).toHaveAttribute("title", "Resolve the missing guide");
  await expect(attentionBadge).toHaveAttribute("aria-label", "Needs attention: Resolve the missing guide");
  await expect(page.locator("#scene-builder-panel > .scene-builder-card").filter({ hasText: "Imported candidate" })).toHaveCount(0);
  await page.getByRole("button", { name: "Imported candidate details" }).click();
  await expect(page.locator("#scene-builder-context-dialog")).toBeVisible();
  await expect(page.locator("#scene-builder-context-content")).toContainText("Keep the cracked lantern");
  await page.locator("#scene-builder-context-close").click();

  const storySlug = await page.locator("#header-story-select").inputValue();
  const sceneSlug = await page.locator("#header-scene-select").inputValue();
  await page.evaluate(({ storySlug, sceneSlug }) => openPromptAnalysisDialog(storySlug, sceneSlug, "background"), { storySlug, sceneSlug });
  await expect(page.locator("#prompt-analysis-dialog")).toBeVisible();
  await expect(page.locator("#prompt-analysis-frame")).toHaveAttribute("src", /render_target_id=background/);
  expect(await page.locator("#prompt-analysis-dialog").evaluate((element) => Math.abs(element.getBoundingClientRect().right - window.innerWidth) <= 20)).toBe(true);

  await page.route(/\/prompt-analysis\/second-opinion\?render_target_id=background/, (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ pending: true, complete: false, render_target_id: "background" }),
  }));
  const secondOpinionRequest = page.waitForRequest((request) => request.url().includes("/prompt-analysis/second-opinion?") && request.method() === "POST");
  await page.getByRole("button", { name: "2nd Opinion", exact: true }).click();
  await secondOpinionRequest;
  await expect(page.getByRole("button", { name: "Check 2nd Opinion", exact: true })).toBeVisible();
});

test("stale view latest analysis action queues a replacement analysis", async ({ page }) => {
  await openPage(page, "scenes");
  await page.locator("#scene-builder-open").click();
  await expect(page.locator("#scene-builder-page")).toHaveClass(/active/);
  await expect(page.locator("#scene-builder-message")).toHaveText("Scene Builder loaded.");

  await page.route(/\/prompt-analysis\?render_target_id=main$/, async (route) => {
    const pending = route.request().method() === "POST";
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ pending, complete: false, result_path: "AI_Prompt_Analysis.md", render_target_id: "main" }),
    });
  });
  await page.evaluate(() => {
    state.scenePromptAnalysis = { pending: false, complete: true, result_path: "AI_Prompt_Analysis.md" };
    renderSceneBuilder();
  });

  const queued = page.waitForRequest((request) => /\/prompt-analysis\?render_target_id=main$/.test(request.url()) && request.method() === "POST");
  await page.locator(".scene-builder-analysis-action", { hasText: "View latest analysis" }).click();
  await queued;
  await expect(page.locator(".scene-builder-analysis-action")).toHaveText("Check analysis");
  await expect(page.locator("#prompt-analysis-dialog")).toBeHidden();
});

test("running prompt analysis harvests and opens without changing the selected prompt", async ({ page }) => {
  await openPage(page, "scenes");
  await page.route(/\/prompt-analysis\?render_target_id=main$/, (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ pending: true, complete: false, result_path: "AI_Prompt_Analysis.md", render_target_id: "main" }),
  }));
  await page.locator("#scene-builder-open").click();
  await expect(page.locator("#scene-builder-page")).toHaveClass(/active/);

  const analysisButton = page.locator(".scene-builder-analysis-action");
  await expect(analysisButton).toHaveText("Check analysis");
  await expect(analysisButton).toBeEnabled();
  await page.route(/\/prompt-analysis\/harvest\?render_target_id=/, (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      pending: false,
      complete: true,
      result_path: "AI_Prompt_Analysis.md",
      render_target_id: "main",
    }),
  }));

  let queuedAgain = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && /\/prompt-analysis\?render_target_id=/.test(request.url())) queuedAgain += 1;
  });
  const harvested = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return url.pathname.endsWith("/prompt-analysis/harvest") && url.searchParams.get("render_target_id") === "main" && request.method() === "POST";
  });
  await analysisButton.click();
  await harvested;
  await expect(page.locator("#prompt-analysis-dialog")).toBeVisible();
  await expect(page.locator("#scene-builder-message")).toHaveText("Prompt analysis is ready.");
  await expect(page.locator(".scene-builder-analysis-action")).toHaveText("View latest analysis");
  expect(queuedAgain).toBe(0);
});

test("Character Development consolidates local Assets and derived workflows", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("zet:workspace-preferences", JSON.stringify({
    workspace: "local", pages: { character: "local-overview", local: "local-body-reference" },
  })));
  await page.goto("/");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await expect(page.locator("#workspace-character")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#workspace-local")).toHaveCount(0);
  await expect(page.locator("#character-context")).toBeVisible();
  await expect(page.locator("#story-context")).toBeHidden();
  await expect(page.locator("#onboarding-page")).toHaveClass(/active/);

  await page.locator("#local-assets-button").click();
  await expect(page.locator("#local-assets-button")).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator("#local-assets-menu button")).toHaveText([
    "Body-Reference", "Head-Image", "Character-Assembly", "Costume-Dressing",
  ]);
  await page.locator('#local-assets-menu [data-page="local-body-reference"]').click();
  await expect(page.locator("#local-pipeline-page")).toHaveClass(/active/);
  await expect(page.locator("#local-pipeline-title")).toHaveText("Body-Reference");
  await expect(page.locator("#local-pipeline-page #character-select, #local-pipeline-page #phase-select")).toHaveCount(0);
  await expect(page).toHaveURL(/page=local-body-reference/);

  await page.locator('#character-navigation [data-page="turnarounds"]').click();
  await expect(page.locator("#turnarounds-page")).toHaveClass(/active/);
  await page.evaluate(async () => window.activatePage("scene-appearances", { skipAutosave: true }));
  await expect(page.locator("#local-batch-status-page")).toHaveClass(/active/);
  await expect(page.locator("#scene-appearances-page")).not.toHaveClass(/active/);

  await expect(page.locator("#toolbar-local-body-reference")).toHaveCount(0);
  await expect(page.locator("#toolbar-gate-test-rig")).toHaveCount(1);
});

test("Run all Remaining starts independently of the open page", async ({ page, request }) => {
  await page.addInitScript(() => localStorage.setItem("zet:workspace-preferences", JSON.stringify({
    workspace: "local", pages: { character: "local-overview", local: "local-body-reference" },
  })));
  await page.goto("/");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.locator("#local-assets-button").click();
  await page.locator('#toolbar-batches').click();
  const started = page.waitForResponse((response) => response.url().endsWith("/api/local/run-all-remaining")
    && response.request().method() === "POST");
  await page.locator("#local-run-all-remaining").click();
  const response = await started;
  expect(response.ok()).toBeTruthy();
  const campaignId = (await response.json()).campaign_id;
  await expect(page.locator("#local-run-all-status")).toBeVisible();
  await page.close();

  await expect.poll(async () => {
    const status = await request.get(`/api/local/run-all-remaining/${campaignId}`);
    return (await status.json()).status;
  }).toBe("COMPLETE");
});

test("all Local asset routes share batch UI and expose only pipeline-specific inputs", async ({ page }) => {
  const previews = [];
  const runLists = [];
  await page.route("**/api/local-gates/**", (route) => route.fulfill({ json: { gates: {}, statuses: {} } }));
  await page.route("**/api/local/*/runs?**", async (route) => {
    runLists.push(route.request().url());
    await route.fulfill({ json: { runs: [] } });
  });
  await page.route("**/api/costumes?**", (route) => route.fulfill({ json: { costumes: [{ name: "Travel" }] } }));
  await page.route("**/api/local/*/preview", async (route) => {
    previews.push({ url: route.request().url(), body: route.request().postDataJSON() });
    await route.fulfill({ json: { candidate_count: 36, views: ["FRONT"] } });
  });

  await page.addInitScript(() => localStorage.setItem("zet:workspace-preferences", JSON.stringify({
    workspace: "local", pages: { character: "local-overview", local: "local-body-reference" },
  })));
  await page.goto("/");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  for (const [pageName, title] of [
    ["local-body-reference", "Body-Reference"], ["local-head-image", "Head-Image"],
    ["local-character-assembly", "Character-Assembly"], ["local-costume-dressing", "Costume-Dressing"],
  ]) {
    await page.locator("#local-assets-button").click();
    await page.locator(`#local-assets-menu [data-page="${pageName}"]`).click();
    await expect(page.locator("#local-pipeline-title")).toHaveText(title);
    await expect(page.locator("#local-pipeline-runs")).toBeVisible();
    await expect(page.locator("#local-pipeline-create")).toBeEnabled();
    await expect(page.locator("#local-pipeline-front-count")).toBeVisible();
    await expect(page.locator("#local-pipeline-other-count")).toBeVisible();
    await expect(page.locator("#local-pipeline-page #character-select, #local-pipeline-page #phase-select")).toHaveCount(0);
    if (pageName === "local-costume-dressing") await expect(page.locator("#local-pipeline-costume-label")).toBeVisible();
    else await expect(page.locator("#local-pipeline-costume-label")).toBeHidden();
    if (["local-character-assembly", "local-costume-dressing"].includes(pageName)) await expect(page.locator("#local-pipeline-anchor-option")).toBeVisible();
    else await expect(page.locator("#local-pipeline-anchor-option")).toBeHidden();
    if (pageName === "local-head-image") {
      await expect(page.locator("#local-pipeline-source-option")).toBeVisible();
      await expect(page.locator("#local-pipeline-apply-phase-change")).toBeVisible();
      await expect(page.locator("#local-pipeline-apply-phase-change")).not.toBeChecked();
      await expect(page.locator("#local-pipeline-apply-phase-change")).toBeDisabled();
      await page.locator("#local-pipeline-source-file").setInputFiles({
        name: "adult-front.png", mimeType: "image/png",
        buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC", "base64"),
      });
      await expect(page.locator("#local-pipeline-apply-phase-change")).toBeEnabled();
      await page.locator("#local-pipeline-apply-phase-change").check();
      await page.locator("#local-pipeline-preview").click();
      await expect.poll(() => previews.some((item) => item.body.apply_phase_change === true)).toBeTruthy();
    } else await expect(page.locator("#local-pipeline-source-option")).toBeHidden();
  }
  expect(runLists).toHaveLength(4);
  expect(previews).toHaveLength(5);
  for (const call of runLists) {
    expect(call).toMatch(/character=/);
    expect(call).toMatch(/phase=/);
  }
  for (const call of previews) {
    expect(call.body.character).toBeTruthy();
    expect(call.body.phase).toBeTruthy();
  }
  expect(previews.find((item) => item.url.includes("costume-dressing")).body.costume).toBe("Travel");
});

test("all four local pipelines expose the same ranked candidate review and observations", async ({ page }) => {
  const runFor = (pipeline) => ({
    run_id: "shared-review-run", batch_name: "Shared review", pipeline,
    character: "Tsaeytte", phase: "Adult", costume: pipeline === "costume-dressing" ? "Travel" : "",
    status: "COMPLETE", views: ["FRONT"], candidate_count: 1, use_front_anchor: false,
    front_anchor: "F-001", selected_views: {}, local_assets: {}, view_reviews: {
      FRONT: { observations: "Manual observations", ai_observations: { status: "COMPLETE", text: "AI observations" } },
    },
    evaluations: {}, rankings: { FRONT: {
      status: "COMPLETE", ordered_candidate_ids: ["F-001"], luna_ordered_candidate_ids: ["F-001"],
      entries: [{ candidate_id: "F-001", reason: "Best image." }],
    } },
    candidates: [{ candidate_id: "F-001", view: "FRONT", status: "COMPLETE", render_status: "COMPLETE",
      image_path: "/images/shared-review/front.png", human_review: { decision: "undecided" }, gates: {} }],
  });
  await page.route("**/api/local-gates/**", (route) => route.fulfill({ json: { gates: {}, statuses: {} } }));
  await page.route("**/api/costumes?**", (route) => route.fulfill({ json: { costumes: [{ name: "Travel" }] } }));
  await page.route("**/api/local/**", async (route) => {
    const url = new URL(route.request().url());
    const parts = url.pathname.split("/");
    const pipeline = parts[3];
    if (!["body-reference", "head-image", "character-assembly", "costume-dressing"].includes(pipeline)) return route.continue();
    if (parts.at(-1) === "runs" && route.request().method() === "GET") {
      return route.fulfill({ json: { runs: [runFor(pipeline)] } });
    }
    if (parts.at(-1) === "shared-review-run") return route.fulfill({ json: runFor(pipeline) });
    if (parts.at(-2) === "images") {
      return route.fulfill({ status: 200, contentType: "image/svg+xml", body: "<svg xmlns='http://www.w3.org/2000/svg'/>" });
    }
    return route.continue();
  });
  await page.route("**/api/local/*/preview", (route) => route.fulfill({ json: { candidate_count: 1, views: ["FRONT"] } }));

  await page.addInitScript(() => localStorage.setItem("zet:workspace-preferences", JSON.stringify({
    workspace: "local", pages: { character: "local-overview", local: "local-body-reference" },
  })));
  await page.goto("/");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  for (const pageName of ["local-body-reference", "local-head-image", "local-character-assembly", "local-costume-dressing"]) {
    await page.locator("#local-assets-button").click();
    await page.locator(`#local-assets-menu [data-page="${pageName}"]`).click();
    await expect(page.locator("#local-pipeline-runs option")).not.toHaveCount(0);
    await expect(page.locator(".local-pipeline-candidate")).toContainText("Rank #1");
    await page.locator(".local-pipeline-candidate").getByRole("button", { name: "Review", exact: true }).click();
    const dialog = page.locator("#local-pipeline-review-dialog");
    await expect(dialog.getByRole("button", { name: "Rank up" })).toBeVisible();
    await expect(dialog.getByRole("button", { name: "Rank down" })).toBeVisible();
    await dialog.getByRole("button", { name: "Close" }).click();
    await expect(page.locator('[data-view-observations="FRONT"]')).toHaveValue("Manual observations");
    await expect(page.locator('.local-pipeline-view [data-local-action="reanalyze"]')).toBeVisible();
  }
});

test("costume lock remains available when another batch currently owns the lock", async ({ page }) => {
  const costumes = ["Travel", "Evening"];
  const runFor = (costume) => {
    const runId = `batch-${costume.toLowerCase()}`;
    const candidateId = `front-${costume.toLowerCase()}`;
    return {
      run_id: runId, character: "Test", phase: "Adult", costume, status: "AWAITING_HUMAN_SELECTION",
      views: ["FRONT"], candidate_count: 1, use_front_anchor: true, front_anchor: candidateId,
      selected_views: { FRONT: candidateId }, rankings: {},
      local_assets: {
        "costume-dressing:evening:FRONT": {
          pipeline: "Costume-Dressing", view: "FRONT", qualifier: "Evening",
          candidate_id: "older-evening-front", batch_id: "older-evening-batch", locked: true,
        },
      },
      candidates: [{ candidate_id: candidateId, view: "FRONT", status: "COMPLETE", image_path: `/images/${runId}/front` }],
    };
  };
  await page.route("**/api/local-gates/**", (route) => route.fulfill({ json: { gates: {}, statuses: {} } }));
  await page.route("**/api/costumes?**", (route) => route.fulfill({ json: { costumes: costumes.map((name) => ({ name })) } }));
  await page.route("**/api/local/costume-dressing/runs?**", async (route) => {
    const costume = new URL(route.request().url()).searchParams.get("costume");
    const run = runFor(costume);
    await route.fulfill({ json: { runs: [{ run_id: run.run_id, status: run.status }] } });
  });
  await page.route(/\/api\/local\/costume-dressing\/runs\/batch-(travel|evening)\?costume=(Travel|Evening)/, async (route) => {
    const costume = new URL(route.request().url()).searchParams.get("costume");
    await route.fulfill({ json: runFor(costume) });
  });

  await page.addInitScript(() => localStorage.setItem("zet:workspace-preferences", JSON.stringify({
    workspace: "local", pages: { character: "local-overview", local: "local-body-reference" },
  })));
  await page.goto("/");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.locator("#local-assets-button").click();
  await page.locator('#local-assets-menu [data-page="local-costume-dressing"]').click();

  const frontLock = page.locator('#local-pipeline-selected [data-view="FRONT"][data-local-action="lock"]');
  await expect(frontLock).toBeEnabled();
  await expect(page.locator(".local-pipeline-lock-notice")).toBeHidden();
  await page.locator("#local-pipeline-costume").selectOption("Evening");
  await expect(frontLock).toBeEnabled();
  await expect(page.locator(".local-pipeline-lock-notice")).toHaveText("Locked images for this pipeline in another batch.");
});

test("local provisional source batches are chosen by name and sent as API values", async ({ page }) => {
  let previewBody = null;
  await page.route("**/api/local-gates/**", (route) => route.fulfill({ json: { gates: {}, statuses: {} } }));
  await page.route("**/api/local/character-assembly/runs?**", (route) => route.fulfill({ json: { runs: [] } }));
  await page.route("**/api/local/character-assembly/preview", async (route) => {
    previewBody = route.request().postDataJSON();
    await route.fulfill({ json: {
      candidate_count: 8, views: ["FRONT"], can_create: false, blocking_reasons: [],
      source_batch_options: {
        body_reference: [{ run_id: "body-run-id", batch_name: "Body · 2026-09-25 11:05", selected_views: ["FRONT"] }],
        head_image: [{ run_id: "head-run-id", batch_name: "Head · 2026-09-25 11:06", selected_views: ["FRONT"] }],
      },
    } });
  });

  await page.addInitScript(() => localStorage.setItem("zet:workspace-preferences", JSON.stringify({
    workspace: "local", pages: { character: "local-overview", local: "local-body-reference" },
  })));
  await page.goto("/");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.locator("#local-assets-button").click();
  await page.locator('#local-assets-menu [data-page="local-character-assembly"]').click();
  const bodySource = page.locator('#local-pipeline-source-batches select[data-source-role="body_reference"]');
  await expect(bodySource).toBeVisible();
  await expect(bodySource).toContainText("Body · 2026-09-25 11:05");
  await bodySource.selectOption("body-run-id");
  await expect.poll(() => previewBody?.source_batches?.body_reference).toBe("body-run-id");
  await expect(bodySource.locator("option:checked")).not.toContainText("body-run-id");
});

test("local character asset candidates render every view section", async ({ page }) => {
  const run = {
    run_id: "assembly-render-test", character: "Test", phase: "Adult", status: "AWAITING_HUMAN_SELECTION",
    views: ["FRONT", "RIGHT_PROFILE"], candidate_count: 2, selected_views: {}, rankings: {},
    candidates: [
      { candidate_id: "front-1", view: "FRONT", status: "COMPLETE", render_status: "COMPLETE", image_path: "/images/front" },
      { candidate_id: "right-1", view: "RIGHT_PROFILE", status: "COMPLETE", render_status: "COMPLETE", image_path: "/images/right" },
    ],
  };
  await page.route("**/api/local-gates/**", (route) => route.fulfill({ json: { gates: {}, statuses: {} } }));
  await page.route("**/api/local/character-assembly/runs?**", (route) => route.fulfill({ json: { runs: [{ run_id: run.run_id, status: run.status }] } }));
  await page.route("**/api/local/character-assembly/runs/assembly-render-test", (route) => route.fulfill({ json: run }));

  await page.addInitScript(() => localStorage.setItem("zet:workspace-preferences", JSON.stringify({
    workspace: "local", pages: { character: "local-overview", local: "local-body-reference" },
  })));
  await page.goto("/");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.locator("#local-assets-button").click();
  await page.locator('#local-assets-menu [data-page="local-character-assembly"]').click();

  await expect(page.locator("#local-pipeline-views .local-pipeline-view")).toHaveCount(2);
  await expect(page.locator("#local-pipeline-views")).toContainText("FRONT");
  await expect(page.locator("#local-pipeline-views")).toContainText("RIGHT_PROFILE");
});

test("Run remaining is placed after batch review actions and tracks unstarted views", async ({ page }) => {
  const makeRun = (runId, hasMissingView) => ({
    run_id: runId, character: "Test", phase: "Adult", status: "AWAITING_HUMAN_SELECTION",
    views: ["FRONT", "RIGHT_PROFILE"], candidate_count: 2, use_front_anchor: true,
    front_anchor: "front-candidate", selected_views: { FRONT: "front-candidate" },
    rankings: {}, local_assets: {},
    candidates: [
      { candidate_id: "front-candidate", view: "FRONT", status: "COMPLETE", image_path: `/images/${runId}/front` },
      { candidate_id: "right-candidate", view: "RIGHT_PROFILE", status: hasMissingView ? "RUNNING" : "COMPLETE",
        image_path: `/images/${runId}/right`,
        image_filled: !hasMissingView },
    ],
  });
  const remainingRun = makeRun("remaining", true);
  const completeRun = makeRun("complete", false);
  const runs = [remainingRun, completeRun];
  let proceedRequest = null;
  await page.route("**/api/local-gates/**", (route) => route.fulfill({ json: { gates: {}, statuses: {} } }));
  await page.route("**/api/local/body-reference/runs?**", (route) => route.fulfill({ json: { runs: runs.map(({ run_id, status }) => ({ run_id, status })) } }));
  await page.route(/\/api\/local\/body-reference\/runs\/(remaining|complete)$/, (route) => {
    const run = route.request().url().endsWith("/remaining") ? remainingRun : completeRun;
    return route.fulfill({ json: run });
  });
  await page.route("**/api/local/body-reference/runs/remaining/views/FRONT/proceed", async (route) => {
    proceedRequest = route.request().url();
    await route.fulfill({ json: { ...remainingRun, status: "READY_FOR_VIEWS", target_views: ["RIGHT_PROFILE"] } });
  });

  await page.addInitScript(() => localStorage.setItem("zet:workspace-preferences", JSON.stringify({
    workspace: "local", pages: { character: "local-overview", local: "local-body-reference" },
  })));
  await page.goto("/");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.locator("#local-assets-button").click();
  await page.locator('#local-assets-menu [data-page="local-body-reference"]').click();
  const runButton = page.locator("#local-pipeline-proceed");
  await expect(runButton).toHaveText("Run remaining");
  await expect(runButton).toBeEnabled();
  const controlOrder = await runButton.evaluate((button) => Array.from(button.parentElement.children)
    .filter((item) => ["local-pipeline-rerun", "local-pipeline-reevaluate", "local-pipeline-proceed"].includes(item.id))
    .map((item) => item.id));
  expect(controlOrder).toEqual(["local-pipeline-rerun", "local-pipeline-reevaluate", "local-pipeline-proceed"]);

  await page.locator("#local-pipeline-runs").selectOption("complete");
  await expect(runButton).toBeDisabled();
  await page.locator("#local-pipeline-runs").selectOption("remaining");
  await expect(runButton).toBeEnabled();
  await runButton.click();
  await expect.poll(() => proceedRequest).not.toBeNull();
  expect(proceedRequest).toContain("/views/FRONT/proceed");
  await expect(runButton).toBeDisabled();
});

test("Run remaining retries stopped costume images including FRONT without a selection", async ({ page }) => {
  const runs = [
    { run_id: "stopped-front", character: "Test", phase: "Adult", costume: "Travel",
      status: "CANCELLED", stop_requested: true, error: "Render failed", use_front_anchor: true,
      views: ["FRONT"], candidate_count: 1, selected_views: {}, rankings: {}, local_assets: {},
      candidates: [{ candidate_id: "F-001", view: "FRONT", status: "FAILED", image_filled: false,
        image_path: "/missing-front.png", render_error: "Render failed" }] },
    { run_id: "stopped-other", character: "Test", phase: "Adult", costume: "Travel",
      status: "CANCELLED", stop_requested: true, error: "Render failed", use_front_anchor: true,
      views: ["FRONT", "FRONT_RIGHT_3_4"], candidate_count: 2, front_anchor: "F-001",
      selected_views: { FRONT: "F-001" }, rankings: {}, local_assets: {},
      candidates: [
        { candidate_id: "F-001", view: "FRONT", status: "COMPLETE", image_path: "/front.png", image_filled: true },
        { candidate_id: "FR-005", view: "FRONT_RIGHT_3_4", status: "FAILED", image_filled: false,
          image_path: "/missing-other.png", render_error: "Render failed" },
      ] },
  ];
  const proceeded = [];
  await page.route("**/api/local-gates/**", (route) => route.fulfill({ json: { gates: {}, statuses: {} } }));
  await page.route("**/api/costumes?**", (route) => route.fulfill({ json: { costumes: [{ name: "Travel" }] } }));
  await page.route("**/api/local/costume-dressing/runs?**", (route) => route.fulfill({
    json: { runs: runs.map(({ run_id, status }) => ({ run_id, status })) },
  }));
  await page.route(/\/api\/local\/costume-dressing\/runs\/stopped-(front|other)\?/, (route) => {
    const run = runs.find((item) => route.request().url().includes(item.run_id));
    return route.fulfill({ json: run });
  });
  await page.route("**/api/local/costume-dressing/runs/*/views/FRONT/proceed?costume=Travel", (route) => {
    const run = runs.find((item) => route.request().url().includes(item.run_id));
    proceeded.push(run.run_id);
    return route.fulfill({ json: { ...run, status: "READY_FOR_VIEWS", stop_requested: false, error: "",
      target_views: [run.run_id === "stopped-front" ? "FRONT" : "FRONT_RIGHT_3_4"] } });
  });
  await page.addInitScript(() => localStorage.setItem("zet:workspace-preferences", JSON.stringify({
    workspace: "local", pages: { character: "local-overview", local: "local-body-reference" },
  })));
  await page.goto("/");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.locator("#local-assets-button").click();
  await page.locator('#local-assets-menu [data-page="local-costume-dressing"]').click();
  const button = page.locator("#local-pipeline-proceed");
  for (const run of runs) {
    await page.locator("#local-pipeline-runs").selectOption(run.run_id);
    await expect(button).toBeEnabled();
    await button.click();
    await expect.poll(() => proceeded.includes(run.run_id)).toBe(true);
    await expect(button).toBeDisabled();
  }
});

test("Character Development is the only character workspace and keeps its production summary", async ({ page }) => {
  const summaryRequests = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname === "/api/production-work-summary") summaryRequests.push(request.url());
  });

  await page.addInitScript(() => localStorage.setItem("zet:workspace-preferences", JSON.stringify({
    workspace: "local", pages: { character: "local-overview", local: "local-body-reference" },
  })));
  await page.goto("/");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await expect(page.locator("#workspace-character")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#workspace-local")).toHaveCount(0);
  expect(summaryRequests.some((url) => new URL(url).searchParams.get("workspace") === "local")).toBe(false);
  await page.locator("#local-assets-button").click();
  await page.locator('#toolbar-batches').click();
  expect(summaryRequests.some((url) => new URL(url).searchParams.get("workspace") === "local")).toBe(false);
});

test("AI Queue stacks queue lists and Config manages Zet processes", async ({ page }) => {
  await openPage(page, "ai-controls");
  await expect(page.locator("#ai-controls-page h1")).toHaveText("AI Queue");
  const queueSections = page.locator(".queue-tables > section");
  await expect(queueSections.locator("h3")).toHaveText(["Running", "Ask", "Answer"]);
  const widths = await queueSections.evaluateAll((sections) => sections.map((section) => section.getBoundingClientRect().width));
  expect(Math.max(...widths) - Math.min(...widths)).toBeLessThan(1);
  await expect(page.locator("#ai-controls-page #process-table")).toHaveCount(0);
  const recentHarvests = page.locator("#recent-harvest-table tbody tr");
  const fixtureHarvest = recentHarvests.filter({ hasText: "Ask_Harvested" });
  await expect(fixtureHarvest).toHaveCount(1);
  await expect(fixtureHarvest).toContainText("SUCCESS");
  await expect(fixtureHarvest).toContainText("Recent browser-test job completed.");
  expect(await page.locator(".recent-harvests-panel").evaluate((panel) => panel.getBoundingClientRect().top)).toBeGreaterThan(
    await page.locator(".ai-render-console-panel:has(#manual-render-table)").evaluate((panel) => panel.getBoundingClientRect().top),
  );

  await openPage(page, "local-image-config");
  await expect(page.locator("#local-image-config-page h1")).toHaveText("Config");
  await expect(page.locator("#setting-ai-asset-workflow-model")).toBeVisible();
  await expect(page.locator("#setting-prompt-condense-model")).toBeVisible();
  await expect(page.locator("#setting-ai-prompt-analysis-model")).toBeVisible();
  await expect(page.locator("#setting-ai-scene-builder-model")).toBeVisible();
  await expect(page.locator('[data-llm-role="image_description"]')).toContainText("Image Inventory catalog metadata");
  await expect(page.locator('[data-llm-role="image_description"]')).toContainText("Creates Image Inventory catalog identity and costume metadata.");
  await page.getByRole("button", { name: "Edit Analysis instructions" }).click();
  await expect(page.locator("#template-editor-page")).toHaveClass(/active/);
  await expect(page.locator("#source-editor-text")).toHaveValue("Analyze the compiled prompt.\n");
  await page.locator("#source-editor-text").fill("Updated analysis instructions.\n");
  await page.locator("#source-editor-save").click();
  await expect(page.locator("#source-editor-save-state")).toHaveText("Saved");
  await openPage(page, "local-image-config");
  const processes = page.locator("#process-table tbody tr");
  await expect(processes).toHaveCount(2);
  await expect(processes.nth(0)).toContainText("Zet Web Dashboard");
  await expect(processes.nth(1)).toContainText("Auto Harvester");
  await expect(processes.locator("button")).toHaveCount(6);
  await expect(page.locator("#local-image-config-page > .control-panel").first().locator("h2")).toHaveText("Processes");

  const restart = page.locator("#toolbar-restart-zet");
  await expect(restart).toHaveText("♻");
  await expect(restart).toHaveAttribute("aria-label", "Restart Zet");
  expect(await restart.evaluate((button) => button.getBoundingClientRect().left)).toBeLessThan(
    await page.locator("#toolbar-settings-button").evaluate((button) => button.getBoundingClientRect().left),
  );
});
