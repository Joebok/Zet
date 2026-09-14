import { expect, test } from "@playwright/test";

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

test("navigation cancels a delayed review load and ignores its late response", async ({ page }) => {
  await openPage(page, "stories");
  let markStarted;
  const requestStarted = new Promise((resolve) => { markStarted = resolve; });
  const delayedResponse = delayedGate();
  await page.route(/\/api\/render-review\/tasks/, async (route) => {
    markStarted();
    await delayedResponse.promise;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ tasks: [{ review_key: "late-review", review_kind: "asset", asset_id: 999 }] }),
    }).catch(() => {});
  });

  await page.evaluate(() => { window.wp02DelayedPage = window.activatePage("render-review", { skipAutosave: true }); });
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
  await expect(page.locator("#render-review-task-table tbody")).not.toContainText("999");
});

test("a late review error cannot replace the newly active page", async ({ page }) => {
  await openPage(page, "stories");
  let markStarted;
  const requestStarted = new Promise((resolve) => { markStarted = resolve; });
  const delayedResponse = delayedGate();
  await page.route(/\/api\/render-review\/tasks/, async (route) => {
    markStarted();
    await delayedResponse.promise;
    await route.fulfill({ status: 503, body: "late failure" }).catch(() => {});
  });

  await page.evaluate(() => { window.wp02DelayedError = window.activatePage("render-review", { skipAutosave: true }); });
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
  await page.route("**/api/stories/Alpha-Story/scenes/Opening-Scene/builder", async (route) => {
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
  await openPage(page, "assets");
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
  await page.evaluate(() => activatePage("assets", { skipAutosave: true }));
  await page.locator("#help-menu-button").click();
  await page.locator("#help-menu button[data-page='help']").click();
  await expect(page.locator("#action-message")).toContainText(
    "Unable to open Template Instruction Manuals: Seeded manuals failure",
  );
});

test("@desktop-smoke desktop layout does not overflow", async ({ page }) => {
  for (const [width, height] of DESKTOP_VIEWPORTS) {
    await page.setViewportSize({ width, height });
    await openPage(page, "assets");
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth))
      .toBe(true);
  }
});

test("Scene Appearances selects a locked preview and reports edits", async ({ page }) => {
  const appearance = {
    appearance_id: "hell-adventures",
    name: "Hell Adventures",
    costume: "Canonical Adventure Gear",
    instructions: "Morrow on anatomical left shoulder; tusk in anatomical right hand.",
    supporting_references: [
      { role: "companion", label: "Morrow", tag: "{{AUX:person:morrow:morrow-raven-form}}" },
      { role: "prop", label: "Utility Tusk", tag: "{{AUX:thing:utility-tusk:tusk-reference}}" },
    ],
    asset_count: 8,
    path: "SceneAppearances/hell-adventures.json",
    locked_preview_path: "Turnarounds/hell-adventures.png",
    locked_preview_exists: true,
  };
  await page.route(/\/api\/scene-appearances\?/, async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ scene_appearances: [appearance] }) });
  });
  await page.route(/\/api\/scene-appearances\/hell-adventures\?/, async (route) => {
    const updated = { ...appearance, name: "Hell Expeditions" };
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ scene_appearance: updated, scene_appearances: [updated], message: "Updated Hell Expeditions." }),
    });
  });
  await openPage(page, "scene-appearances");
  await expect(page.locator("#scene-appearance-status")).toContainText("1 Scene Appearance set");
  await page.locator("#scene-appearance-table tbody tr").click();
  await expect(page.locator("#scene-appearance-preview-section")).toBeVisible();
  await expect(page.locator("#scene-appearance-preview img")).toHaveAttribute("alt", "Locked Scene Appearance turnaround");
  await page.locator("#scene-appearance-name").fill("Hell Expeditions");
  await page.locator("#scene-appearance-save").click();
  await expect(page.locator("#scene-appearance-message")).toContainText("Updated Hell Expeditions");
});

test("Image Inventory filters base outputs and edits logical metadata", async ({ page }) => {
  await openPage(page, "auxiliary-resources");
  const cards = page.locator("#image-catalog-grid .image-catalog-card");
  await expect(cards).toHaveCount(0);
  await expect(page.locator("#image-catalog-count")).toContainText("then refresh");
  await expect(page.locator("#image-catalog-include-base")).not.toBeChecked();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await expect(page.locator("#image-catalog-import-zone")).toBeVisible();
  await expect(page.locator("#image-catalog-set-select")).toBeVisible();
  const initialRefresh = page.waitForResponse((response) => response.url().includes("/api/image-catalog?") && response.ok());
  await page.locator("#image-catalog-refresh").click();
  await initialRefresh;
  const initialCount = await cards.count();
  expect(initialCount).toBeGreaterThan(0);
  await expect(cards.filter({ hasText: "Head-Image" })).toHaveCount(0);

  await page.locator("#image-catalog-include-base").check();
  await expect(cards).toHaveCount(0);
  const baseRefresh = page.waitForResponse((response) => response.url().includes("/api/image-catalog?") && response.ok());
  await page.locator("#image-catalog-refresh").click();
  await baseRefresh;
  await expect(cards).toHaveCount(initialCount + 1);
  await cards.filter({ hasText: "Head-Image" }).click();
  await expect(page.locator("#image-catalog-editor-title")).toContainText("Head-Image");
  await expect(page.locator("#image-catalog-identity-mode")).toHaveValue("inherit");
  await expect(page.locator("#image-catalog-identity-text")).toBeDisabled();
  await expect(page.locator("#image-catalog-costume-text")).toBeDisabled();
  await page.locator("#image-catalog-identity-mode").selectOption("override");
  await expect(page.locator("#image-catalog-identity-text")).toBeEnabled();
  await page.locator("#image-catalog-identity-mode").selectOption("inherit");
  await expect(page.locator("#image-catalog-identity-text")).toBeDisabled();
  await page.locator("#image-catalog-preview").click();
  await expect(page.locator(".fullscreen-image-overlay")).toBeVisible();
  await page.keyboard.press("Escape");

  const selectors = page.locator("#image-catalog-grid .image-catalog-card > input[type=checkbox]");
  await selectors.nth(0).check();
  await expect(page.locator("#image-catalog-bulk")).toBeHidden();
  await selectors.nth(1).check();
  await expect(page.locator("#image-catalog-bulk")).toBeVisible();
  await page.locator("#image-catalog-bulk-clear").click();

  await page.locator("#image-catalog-new-collection").fill("Heroes");
  const created = page.waitForResponse((response) => response.url().includes("/api/image-catalog/organization/collections") && response.ok());
  await page.locator("#image-catalog-add-collection").click();
  await created;
  await expect(page.locator("#image-catalog-edit-collections option")).toContainText(["Heroes (0)"]);
  await page.locator("#image-catalog-edit-collections").selectOption("heroes");
  await page.locator("#image-catalog-identity-mode").selectOption("override");
  await page.locator("#image-catalog-identity-text").fill("Distinct approved identity markers.");
  const saved = page.waitForResponse((response) => response.url().includes("/api/image-catalog/img_") && response.request().method() === "PATCH" && response.ok());
  await page.locator("#image-catalog-save").click();
  await saved;
  await expect(page.locator("#image-catalog-identity-text")).toHaveValue("Distinct approved identity markers.");
  await expect(page.locator("#image-catalog-edit-collections option:checked")).toHaveAttribute("value", "heroes");
});

test("Image Inventory reports queued AI descriptions and harvests drafts without reload", async ({ page }) => {
  await openPage(page, "auxiliary-resources");
  const refreshed = page.waitForResponse((response) => response.url().includes("/api/image-catalog?") && response.ok());
  await page.locator("#image-catalog-refresh").click();
  await refreshed;
  await page.locator("#image-catalog-grid .image-catalog-card").first().click();
  const item = await page.evaluate(() => selectedImageCatalogItem());

  await page.route(/\/api\/image-catalog\/[^/]+\/ai-description$/, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ item: { ...item, description_status: "ai_queued" }, message: "Image description job queued." }),
    });
  });
  await page.route(/\/api\/image-catalog\/[^/]+\/ai-description\/harvest$/, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        item: {
          ...item,
          description_status: "ai_review_required",
          ai_draft_identity: "Stable physical identity.",
          ai_draft_costume: "Visible costume details.",
        },
        message: "AI image description harvested.",
      }),
    });
  });

  await page.locator("#image-catalog-ai").click();
  await expect(page.locator("#image-catalog-ai-status")).toContainText("initiated and awaiting");
  await expect(page.locator("#image-catalog-ai-check")).toBeEnabled();
  await page.locator("#image-catalog-ai-check").click();
  await expect(page.locator("#image-catalog-ai-review")).toBeVisible();
  await expect(page.locator("#image-catalog-ai-identity")).toHaveValue("Stable physical identity.");
  await expect(page.locator("#image-catalog-ai-costume")).toHaveValue("Visible costume details.");
  await expect(page.locator("#image-catalog-ai-status")).toContainText("answer harvested");

  await page.evaluate(() => window.activatePage("stories", { skipAutosave: true }));
  await page.evaluate(() => window.activatePage("auxiliary-resources", { skipAutosave: true }));
  await expect(page.locator("#image-catalog-ai-review")).toBeVisible();
  await expect(page.locator("#image-catalog-ai-status")).toContainText("answer harvested");

  await page.route(/\/api\/image-catalog\/[^/]+\/ai-description\/approve$/, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        item: {
          ...item,
          description_status: "approved",
          ai_draft_identity: "",
          ai_draft_costume: "",
          identity_text: "Approved identity.",
          costume_text: "Approved costume.",
        },
        message: "Image description approved.",
      }),
    });
  });
  await page.locator("#image-catalog-ai-approve").click();
  await expect(page.locator("#image-catalog-ai-review")).toBeHidden();
  await expect(page.locator("#image-catalog-ai-status")).toBeHidden();
});

test("Image Inventory manages imported images and optional reference sets", async ({ page }) => {
  await openPage(page, "auxiliary-resources");
  await page.locator("#image-catalog-set-label").fill("Browser Props");
  const setCreated = page.waitForResponse((response) => response.url().endsWith("/api/image-catalog/reference-sets") && response.request().method() === "POST" && response.ok());
  await page.locator("#image-catalog-set-save").click();
  await setCreated;

  await page.locator("#image-catalog-import-file").setInputFiles({
    name: "lantern.png",
    mimeType: "image/png",
    buffer: Buffer.from("browser image"),
  });
  await page.locator("#image-catalog-import-label").fill("Browser Lantern");
  const referenceSetValue = await page.locator("#image-catalog-import-set option").filter({ hasText: "Browser Props" }).first().getAttribute("value");
  await page.locator("#image-catalog-import-set").selectOption(referenceSetValue);
  const imported = page.waitForResponse((response) => response.url().includes("/api/image-catalog/imports?") && response.ok());
  await page.locator("#image-catalog-import-save").click();
  await imported;

  await expect(page.locator("#image-catalog-managed-actions")).toBeVisible();
  await expect(page.locator("#image-catalog-managed-label")).toHaveValue("Browser Lantern");
  await expect(page.locator("#image-catalog-add-upload")).toBeHidden();
  await expect(page.locator("#image-catalog-replace-upload")).toBeHidden();
  await page.locator("#image-catalog-add").click();
  await expect(page.locator("#image-catalog-add-upload")).toBeVisible();
  await page.locator("#image-catalog-add-label").fill("Browser Lantern Alternate");
  await page.locator("#image-catalog-add-file").setInputFiles({
    name: "lantern-alternate.png",
    mimeType: "image/png",
    buffer: Buffer.from("alternate image"),
  });
  const added = page.waitForResponse((response) => response.url().includes("/api/image-catalog/imports?") && response.ok());
  await page.locator("#image-catalog-add-submit").click();
  await added;
  await expect(page.locator("#image-catalog-editor-title")).toContainText("Browser Lantern Alternate");
  await page.getByRole("button", { name: "Edit Browser Props - Browser Lantern", exact: true }).click();
  await page.locator("#image-catalog-managed-label").fill("Renamed Lantern");
  await page.locator("#image-catalog-managed-set").selectOption("");
  const saved = page.waitForResponse((response) => response.url().includes("/api/image-catalog/img_") && response.request().method() === "PATCH" && response.ok());
  await page.locator("#image-catalog-save").click();
  await saved;
  await expect(page.locator("#image-catalog-editor-title")).toHaveText("Renamed Lantern");
  await expect(page.locator("#aux-resource-message")).toContainText("Image metadata saved.");
  await expect(page.locator("#image-catalog-managed-label")).toHaveValue("Renamed Lantern");

  await expect(page.locator("#image-catalog-replace-upload")).toBeHidden();
  await page.locator("#image-catalog-replace").click();
  await expect(page.locator("#image-catalog-replace-upload")).toBeVisible();
  await page.locator("#image-catalog-replace-file").setInputFiles({
    name: "lantern.jpg",
    mimeType: "image/jpeg",
    buffer: Buffer.from("replacement image"),
  });
  const replaced = page.waitForResponse((response) => response.url().endsWith("/content") && response.ok());
  await page.locator("#image-catalog-replace-submit").click();
  await replaced;

  page.once("dialog", (dialog) => dialog.accept());
  const deleted = page.waitForResponse((response) => response.url().includes("/api/image-catalog/img_") && response.request().method() === "DELETE" && response.ok());
  await page.locator("#image-catalog-delete").click();
  await deleted;
  await expect(page.locator("#image-catalog-grid").getByText("Renamed Lantern", { exact: true })).toHaveCount(0);
});


test("Prompt Evolution v3 uses global role models, blinded prompt grids, and post-selection audits", async ({ page }) => {
  await openPage(page, "prompt-evolution");
  await page.locator("#prompt-evolution-show-setup").click();
  await expect(page.locator("#prompt-evolution-setup-pane")).toBeVisible();
  await page.locator("#prompt-evolution-show-review").click();
  await expect(page.locator("#prompt-evolution-review-pane")).toBeVisible();
  await expect(page.locator("#prompt-evolution-setup-pane")).toBeHidden();
  await page.locator("#prompt-evolution-show-setup").click();
  await expect(page.locator("#prompt-evolution-critic-model-a, #prompt-evolution-critic-model-b, #prompt-evolution-analysis-model, #prompt-evolution-check-model")).toHaveCount(0);
  await expect(page.locator("#prompt-evolution-backend")).toBeVisible();
  await expect(page.locator("#prompt-evolution-backend")).toHaveValue("stable_matrix");
  await expect(page.locator("#prompt-evolution-comfy-controls")).toBeHidden();
  await expect(page.locator("#prompt-evolution-fixed-seed-count")).toHaveValue("3");
  await expect(page.locator("#prompt-evolution-mode, #prompt-evolution-metadata")).toHaveCount(0);
  await page.locator("#prompt-evolution-show-review").click();

  const batch = {
    index: 0, prompt_version_id: "prompt-000", status: "REVIEWED",
    positive_prompt: "hidden black bob, gray background", negative_prompt: "hidden blonde hair, cropped",
    positive_core: "hidden black bob", negative_core: "hidden blonde hair",
    renders: [{ seed: 11, seed_role: "fixed", file: "fixed.png" }, { seed: 22, seed_role: "fresh", file: "fresh.png" }],
    candidates: [{ seed: 11, seed_role: "fixed", file: "fixed.png", critics: { a: { major_differences: [{ reference: "teal coat", candidate: "blue coat" }], stable_matches: ["black bob"] }, b: { stable_matches: ["black bob"] } }, checks: [{ id: "hair", pass: true, evidence: "Hair is black." }] }],
    synthesis: { recurrent_deviations: [], stable_successes: ["black bob"] },
    diagnosis: { interventions: [] }, edit: {},
  };
  const nextBatch = {
    ...batch, index: 1, prompt_version_id: "prompt-001", status: "RENDERING", renders: [],
    positive_prompt: "hidden black bob, teal coat, gray background", positive_core: "hidden black bob, teal coat",
  };
  await page.evaluate((value) => renderPromptEvolutionDetail(value), {
    version: 3, run_id: "run-1", character: "Character", phase: "Adult", costume: "Costume", view: "Front",
    reference_image: "reference.png", checkpoint: "checkpoint", status: "RENDERING", batches: [batch, nextBatch],
  });
  const activePromptHistory = page.locator(".prompt-evolution-prompt-history").nth(1);
  await activePromptHistory.click();
  await expect(activePromptHistory).toContainText("hidden black bob, teal coat");
  await expect(activePromptHistory.locator(".prompt-diff-added")).toContainText("teal coat");

  await page.evaluate(({ run, sourceBatch }) => renderPromptEvolutionDetail({
    ...run,
    batches: [{ ...sourceBatch, status: "AWAITING_PROMPT_REVIEW", synthesis: { next_round_priorities: [{ problem: "coat color" }] }, diagnosis: { interventions: [{ rationale: "color drift" }] }, edit: { positive_core: "black bob, red coat", negative_core: "blue coat", changes: [{ reason: "correct drift" }] } }],
  }), { run: {
    version: 3, run_id: "run-1", character: "Character", phase: "Adult", costume: "Costume", view: "Front",
    reference_image: "reference.png", checkpoint: "checkpoint", status: "AWAITING_PROMPT_REVIEW", current_batch: 0,
  }, sourceBatch: batch });
  await expect(page.locator(".prompt-evolution-manual-review")).toContainText("Reasoning for this change");
  await expect(page.locator(".prompt-evolution-change-list")).toContainText("correct drift");
  await expect(page.locator(".prompt-evolution-summary-diff")).toContainText("red coat");
  await expect(page.locator("[data-prompt-evolution-review-positive]")).toHaveValue("black bob, red coat");
  await expect(page.locator("[data-prompt-evolution-review-negative]")).toHaveValue("blue coat");
  await expect(page.locator("[data-prompt-evolution-review-accept]")).toBeVisible();

  await page.evaluate((value) => renderPromptEvolutionDetail(value), {
    version: 3, run_id: "run-1", character: "Character", phase: "Adult", costume: "Costume", view: "Front",
    reference_image: "reference.png", checkpoint: "checkpoint", status: "AWAITING_FINAL_REVIEW",
    prompt_versions: [{ prompt_version_id: "prompt-000", fixed_renders: [batch.renders[0]], fresh_renders: [batch.renders[1]] }], batches: [batch, nextBatch],
  });
  await expect(page.locator("#prompt-evolution-detail")).toContainText("Choice A");
  await expect(page.locator(".prompt-evolution-prompt-versions")).toContainText("Prompt version 2");
  await expect(page.locator("[data-prompt-evolution-final-version='prompt-000']")).toBeVisible();

  await page.evaluate((value) => renderPromptEvolutionDetail(value), {
    version: 3, run_id: "run-1", character: "Character", phase: "Adult", costume: "Costume", view: "Front",
    reference_image: "reference.png", checkpoint: "checkpoint", status: "COMPLETE",
    selected_prompt_version: "prompt-000", prompt_versions: [], batches: [batch],
    activity_log: [{ at: "2026-08-10T14:00:00", level: "info", message: "Batch 1 — queued seed 11 for Critic A visual comparison." }],
  });
  await expect(page.locator("#prompt-evolution-detail")).toContainText("Selected prompt version");
  await expect(page.locator(".prompt-evolution-log")).toContainText("queued seed 11 for Critic A");
  await page.locator("#prompt-evolution-detail details").filter({ hasText: "Automatic decision audit" }).click();
  await expect(page.locator("#prompt-evolution-detail")).toContainText("Cross-seed priorities");
  await expect(page.locator("#prompt-evolution-detail")).toContainText("black bob");
  await expect(page.locator("#prompt-evolution-detail")).toContainText("teal coat");
  await expect(page.locator("#prompt-evolution-detail")).toContainText("Hair is black.");

  const refreshed = page.waitForResponse((response) => response.url().endsWith("/api/prompt-evolution/runs") && response.ok());
  await page.locator("#prompt-evolution-refresh").click();
  await refreshed;
});





test("@desktop-smoke workspace shell switches adaptive context and remembers the last page", async ({ page }) => {
  await openPage(page, "assets");
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
  await expect(page.locator("#assets-page")).toHaveClass(/active/);
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

test("render console labels references in attachment order", async ({ page }) => {
  await openPage(page, "render-console");
  await page.evaluate(() => renderConsoleReferenceFiles([
    { image_index: 1, prompt_role: "edit_base", label: "Canvas", path: "canvas.png" },
    { image_index: 2, prompt_role: "subject_reference", label: "Hero", path: "hero.png" },
  ]));

  const titles = page.locator("#render-console-reference-files h3");
  await expect(titles.nth(0)).toHaveText("Image 1 — edit_base — Canvas");
  await expect(titles.nth(1)).toHaveText("Image 2 — subject_reference — Hero");
});

test("render console captures optional refinement telemetry", async ({ page }) => {
  await openPage(page, "render-console");
  const checkbox = page.locator("#render-console-refinement-required");
  const fields = page.locator("#render-console-refinement-fields");
  await expect(checkbox).not.toBeChecked();
  await expect(fields).toBeHidden();
  await checkbox.check();
  await expect(fields).toBeVisible();
  await page.locator("#render-console-refinement-count").fill("3");
  await page.locator("#render-console-refinement-note").fill("Corrected orientation.");
  await checkbox.uncheck();
  await expect(fields).toBeHidden();
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







test("@desktop-smoke source editor guards dirty navigation with Cancel and Discard", async ({ page }) => {
  await openPage(page, "assets");
  await page.locator("#asset-table .row-selection-button").first().click();
  await page.locator("#open-governing-template").click();
  await expect(page.locator("#template-editor-page")).toHaveClass(/active/);
  await page.locator("#source-editor-text").fill("Unsaved source editor change");
  await page.locator("#workspace-story").click();
  const dialog = page.locator("#unsaved-changes-dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(page.locator("#template-editor-page")).toHaveClass(/active/);
  await page.locator("#workspace-story").click();
  await dialog.getByRole("button", { name: "Discard" }).click();
  await expect(page.locator("#stories-page")).toHaveClass(/active/);

  await openPage(page, "assets");
  await page.locator("#asset-table .row-selection-button").first().click();
  await page.locator("#open-governing-template").click();
  await page.locator("#source-editor-text").fill("Saved source editor change");
  await page.locator("#workspace-story").click();
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(page.locator("#stories-page")).toHaveClass(/active/);
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

  const allRequest = page.waitForRequest((request) => request.url().includes("/api/render-console/tasks?"));
  await page.locator("#scene-workflow-menu").selectOption("render-console");
  const allUrl = new URL((await allRequest).url());
  expect(allUrl.searchParams.has("story_slug")).toBe(false);
  expect(allUrl.searchParams.has("scene_slug")).toBe(false);
  await expect(page.locator("#header-story-select")).toHaveValue("Alpha-Story");
  await expect(page.locator("#header-scene-select")).toHaveValue("Closing-Scene");
  await expect(page.locator(".production-scope-toggle")).toHaveCount(0);
  await expect(page.locator("#story-navigation [data-production-count='render_waiting']")).toHaveText(/[1-9]/);
  await expect(page.locator("#story-navigation [data-production-count='image_review_waiting']")).toHaveText(/[1-9]/);
  expect(await page.locator(".render-console-layout").evaluate((element) => (
    getComputedStyle(element).gridTemplateColumns.split(" ").length
  ))).toBe(3);

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

  await page.locator("#scene-builder-open").click();
  const editorBox = await page.locator(".scene-builder-element-editor").boundingBox();
  const fieldsetBox = await page.locator(".scene-builder-element-editor fieldset").boundingBox();
  expect(Math.abs(editorBox.width - fieldsetBox.width)).toBeLessThan(1);
  const enabled = page.waitForResponse((response) => response.url().endsWith("/subscenes/background/enable") && response.ok());
  await page.getByRole("button", { name: "Use background sub-render" }).click();
  await enabled;
  await expect(page.getByRole("button", { name: "Background", exact: true })).toHaveClass(/selected/);
  await expect(page.locator(".scene-builder-active-target")).toHaveText("Editing Subscene: Background");
  await expect(page.locator(".scene-builder-element-list")).toContainText("Hall");
  await expect(page.locator(".scene-builder-element-list")).not.toContainText("Hero");

  const stagedForConsole = page.waitForResponse((response) => response.url().includes("/render-targets/background/stage-render") && response.ok());
  await page.locator(".scene-builder-render").first().click();
  await stagedForConsole;
  await expect(page.locator("#render-console-page")).toHaveClass(/active/);
  const returnedFromConsole = page.waitForResponse((response) => response.url().endsWith("/builder") && response.request().method() === "GET" && response.ok());
  await page.locator("#render-console-scene-builder").click();
  await returnedFromConsole;
  await expect(page.locator("#scene-builder-open")).toBeEnabled();
  await expect(page.getByRole("button", { name: "Background", exact: true })).toHaveClass(/selected/);

  const stagedForPrompt = page.waitForResponse((response) => response.url().includes("/render-targets/background/stage-render") && response.ok());
  await page.locator(".scene-builder-render").first().click();
  await stagedForPrompt;
  await page.locator("#render-console-review-prompt").click();
  await expect(page.locator("#prompt-review-page")).toHaveClass(/active/);
  const returnedFromPrompt = page.waitForResponse((response) => response.url().endsWith("/builder") && response.request().method() === "GET" && response.ok());
  await page.locator("#prompt-review-scene-builder").click();
  await returnedFromPrompt;
  await expect(page.locator("#scene-builder-open")).toBeEnabled();
  await expect(page.getByRole("button", { name: "Background", exact: true })).toHaveClass(/selected/);

  await page.getByRole("button", { name: "Add Element" }).click();
  await page.locator("#builder-element-resource-type").selectOption("Scene-Only");
  await page.locator("#builder-element-scene-name").fill("Background Statue");
  await page.locator("#builder-element-add").click();
  await expect(page.locator(".scene-builder-element-list")).toContainText("Background Statue");
  await expect(page.locator("[data-builder-element-field='subscene_id']")).toHaveValue("background");
  expect(await page.evaluate(() => state.sceneBuilder.scene_elements.find((item) => item.display_name === "Background Statue")?.subscene_id)).toBe("background");

  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await expect.poll(() => page.locator(".scene-builder-sticky-context").evaluate((element) => Math.round(element.getBoundingClientRect().top))).toBe(0);
  await page.evaluate(() => window.scrollTo(0, 0));

  await page.getByRole("button", { name: "Full Scene", exact: true }).click();
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

  await expect(page.locator(".scene-builder-render").first()).toBeDisabled();
  const disabled = page.waitForResponse((response) => response.url().endsWith("/subscenes/background/disable") && response.ok());
  await page.getByRole("button", { name: "Turn off background sub-render" }).click();
  await disabled;
  await expect(page.locator(".scene-builder-render").first()).toBeEnabled();
});

test("@desktop-smoke Scene Builder creates assignable colored sub-scenes", async ({ page }) => {
  await openPage(page, "scenes");
  const storySlug = await page.locator("#header-story-select").inputValue();
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

  await page.locator("#scene-builder-open").click();
  await page.locator(".scene-builder-element-row").filter({ hasText: "Travelers" }).click();
  await page.locator(".scene-builder-element-menu summary").click();
  await expect(page.locator(".scene-builder-menu-panel").filter({ has: page.getByRole("button", { name: "Duplicate" }) })).not.toContainText("sub-scene");
  const created = page.waitForResponse((response) => response.url().endsWith("/subscenes") && response.request().method() === "POST" && response.ok());
  await page.getByRole("button", { name: "Add Sub-Scene" }).click();
  const createdPayload = await (await created).json();
  const targetId = createdPayload.render_target_id;
  await expect(page.getByRole("button", { name: "Sub-Scene 1", exact: true })).toBeVisible();
  await page.locator("[data-builder-element-field='subscene_id']").selectOption(targetId);
  const fullSceneSaved = page.waitForResponse((response) => response.url().endsWith("/builder") && response.request().method() === "PUT" && response.ok());
  await page.getByRole("button", { name: "Save Full Scene", exact: true }).click();
  await fullSceneSaved;
  await expect(page.locator("#scene-builder-save-state")).toHaveText("Saved");
  await expect(page.locator(".scene-builder-element-workspace")).toHaveClass(/subscene-member/);
  await page.getByRole("button", { name: "Sub-Scene 1", exact: true }).click();
  await page.getByRole("button", { name: "Color 3" }).click();
  const subsceneSaved = page.waitForResponse((response) => response.url().endsWith(`/builder/subscenes/${targetId}`) && response.request().method() === "PUT" && response.ok());
  await page.getByRole("button", { name: "Save Subscene", exact: true }).click();
  await subsceneSaved;
  await expect(page.getByRole("button", { name: "Sub-Scene 1", exact: true })).toHaveAttribute("style", /#F3E1E7/);
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

  await page.locator("#scene-builder-open").click();
  await page.locator('[data-builder-field="scene.story_beat"]').fill("Unsaved full-scene beat");
  await page.getByRole("button", { name: "Background", exact: true }).click();
  const focalPoint = page.locator('[data-builder-subscene-field="focal_point"]');
  await focalPoint.fill("Distant ruined tower");
  const scopedSave = page.waitForRequest((request) => request.url().endsWith("/builder/subscenes/background") && request.method() === "PUT");
  await page.getByRole("button", { name: "Save Subscene", exact: true }).click();
  const saveRequest = await scopedSave;
  expect((await saveRequest.postDataJSON()).id).toBe("background");
  expect(await page.evaluate(() => state.sceneBuilder.scene.story_beat)).toBe("Unsaved full-scene beat");
  await expect(page.locator("#scene-builder-save-state")).toContainText("other changes dirty");

  const persisted = await page.request.get(`/api/stories/${storySlug}/scenes/${sceneSlug}/builder`);
  const persistedData = (await persisted.json()).document.data;
  expect(persistedData.scene.story_beat).toBe("Persisted story beat");
  expect(persistedData.subscenes.find((item) => item.id === "background").prompt_overrides.focal_point).toBe("Distant ruined tower");

  await page.getByRole("button", { name: "Full Scene", exact: true }).click();
  const fullSceneSaved = page.waitForResponse((response) => response.url().endsWith("/builder") && response.request().method() === "PUT");
  await page.getByRole("button", { name: "Save Full Scene", exact: true }).click();
  expect((await fullSceneSaved).ok()).toBe(true);
  const persistedFullScene = await page.request.get(`/api/stories/${storySlug}/scenes/${sceneSlug}/builder`);
  expect((await persistedFullScene.json()).document.data.scene.story_beat).toBe("Unsaved full-scene beat");

  await page.getByRole("button", { name: "Background", exact: true }).click();

  await focalPoint.fill("Wrong target edit");
  await page.getByRole("button", { name: "Cancel Subscene Edits", exact: true }).click();
  await expect(focalPoint).toHaveValue("Distant ruined tower");
  expect(await page.evaluate(() => state.sceneBuilder.scene.story_beat)).toBe("Unsaved full-scene beat");
});

test("@desktop-smoke imported candidate context and prompt analysis use side panels", async ({ page }) => {
  await openPage(page, "scenes");
  await page.locator("#scene-builder-open").click();
  await expect(page.locator("#scene-builder-page")).toHaveClass(/active/);
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
});

test("running prompt analysis harvests and opens without changing the selected prompt", async ({ page }) => {
  await openPage(page, "prompt-review");
  await expect(page.locator("#prompt-review-title")).not.toHaveText("Select a prompt");
  await page.evaluate(() => {
    state.promptReviewDetail.manifest.story_slug = "Alpha-Story";
    state.promptReviewDetail.manifest.scene_slug = "Opening-Scene";
    state.promptReviewDetail.manifest.render_target_id = "main";
    state.promptReviewDetail.prompt_analysis = {
      pending: true,
      complete: false,
      result_path: "AI_Prompt_Analysis.md",
    };
    renderPromptReview(state.promptReviewDetail);
  });

  const analysisButton = page.locator("#analyze-prompt");
  await expect(analysisButton).toHaveText("Analysis running");
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
  const harvested = page.waitForRequest((request) => request.url().includes("/prompt-analysis/harvest?") && request.method() === "POST");
  await analysisButton.click();
  await harvested;
  await expect(page.locator("#prompt-analysis-dialog")).toBeVisible();
  await expect(page.locator("#prompt-review-message")).toHaveText("Prompt analysis is ready.");
  await expect(page.locator("#analyze-prompt")).toHaveText("Run analysis again");
  expect(queuedAgain).toBe(0);
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
  await expect(recentHarvests).toHaveCount(1);
  await expect(recentHarvests.first()).toContainText("Ask_Harvested");
  await expect(recentHarvests.first()).toContainText("SUCCESS");
  await expect(recentHarvests.first()).toContainText("Recent browser-test job completed.");
  expect(await page.locator(".recent-harvests-panel").evaluate((panel) => panel.getBoundingClientRect().top)).toBeGreaterThan(
    await page.locator(".ai-render-console-panel").evaluate((panel) => panel.getBoundingClientRect().top),
  );

  await openPage(page, "local-image-config");
  await expect(page.locator("#local-image-config-page h1")).toHaveText("Config");
  await expect(page.locator("#setting-ai-asset-workflow-model")).toBeVisible();
  await expect(page.locator("#setting-prompt-condense-model")).toBeVisible();
  await expect(page.locator("#setting-ai-prompt-analysis-model")).toBeVisible();
  await expect(page.locator("#setting-ai-scene-builder-model")).toBeVisible();
  await expect(page.locator("#setting-ai-prompt-evolution-critic-a-model")).toBeVisible();
  await expect(page.locator("#setting-ai-prompt-evolution-critic-b-model")).toBeVisible();
  await expect(page.locator("#setting-ai-prompt-evolution-analysis-model")).toBeVisible();
  await expect(page.locator("#setting-ai-prompt-evolution-check-model")).toBeVisible();
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
