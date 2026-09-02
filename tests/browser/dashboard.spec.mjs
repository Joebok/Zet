import { expect, test } from "@playwright/test";

const DESKTOP_VIEWPORTS = [
  [1600, 900],
];

async function openPage(page, pageName) {
  const contextResponse = page.waitForResponse((response) => response.url().endsWith("/api/context"));
  await page.goto("/");
  await page.waitForFunction(() => typeof window.activatePage === "function");
  await contextResponse;
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await expect(page.locator("#character-select option")).not.toHaveCount(0);
  await page.evaluate(async (name) => window.activatePage(name, { skipAutosave: true }), pageName);
  await expect(page.locator(`#${pageName}-page`)).toHaveClass(/active/);
}

test("@desktop-smoke desktop layout does not overflow", async ({ page }) => {
  for (const [width, height] of DESKTOP_VIEWPORTS) {
    await page.setViewportSize({ width, height });
    await openPage(page, "assets");
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth))
      .toBe(true);
  }
});

test("Image Inventory filters base outputs and edits logical metadata", async ({ page }) => {
  await openPage(page, "auxiliary-resources");
  const cards = page.locator("#image-catalog-grid .image-catalog-card");
  const initialCount = await cards.count();
  expect(initialCount).toBeGreaterThan(1);
  await cards.filter({ hasText: "Head-Image" }).click();
  await expect(page.locator("#image-catalog-editor-title")).toContainText("Head-Image");
  await expect(page.locator("#image-catalog-identity-mode")).toHaveValue("inherit");

  await page.locator("#image-catalog-include-base").uncheck();
  await expect(cards).toHaveCount(initialCount - 1);
  await expect(cards.filter({ hasText: "Head-Image" })).toHaveCount(0);
  await page.locator("#image-catalog-include-base").check();
  await expect(cards).toHaveCount(initialCount);
  await cards.filter({ hasText: "Head-Image" }).click();

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
  await expect(rows).toHaveCount(2);
  const initialSceneSlug = await page.locator("#scene-table tr.selected").getAttribute("data-scene-slug");
  const initialSceneText = await page.locator("#scene-text").inputValue();
  const initialSceneTitle = initialSceneText.split("\n", 1)[0];
  await page.locator("#scene-text").fill(`${initialSceneTitle}\n\nUnsaved scene change.\n`);
  await page.locator("#scene-table tr:not(.selected) .row-selection-button").click();
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

test("@desktop-smoke Scene Builder creates and selects an auxiliary resource without losing context", async ({ page }) => {
  await openPage(page, "scenes");
  await page.locator("#scene-builder-open").click();
  await page.getByRole("button", { name: "Add Element" }).click();
  await page.locator("#builder-element-resource-type").selectOption("Object");
  await page.locator("#builder-element-new-aux").click();
  await page.locator("#builder-element-new-aux-label").fill("Story Lantern");
  const created = page.waitForResponse((response) => (
    response.url().includes("/api/auxiliary-resources?") && response.request().method() === "POST"
  ));
  await page.locator("#builder-element-new-aux-save").click();
  const createdResponse = await created;
  expect(createdResponse.ok()).toBe(true);
  const resource = (await createdResponse.json()).resource;

  await expect(page.locator("#builder-element-modal")).toBeVisible();
  await expect(page.locator("#builder-element-aux")).toHaveValue(resource.resource_id);
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
  await expect(page.locator(".scene-builder-subscene-element-summary")).toContainText("Hall");
  await expect(page.locator(".scene-builder-subscene-element-summary")).not.toContainText("Hero");

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

  await expect(page.locator(".scene-builder-render").first()).toBeDisabled();
  const disabled = page.waitForResponse((response) => response.url().endsWith("/subscenes/background/disable") && response.ok());
  await page.getByRole("button", { name: "Turn off background sub-render" }).click();
  await disabled;
  await expect(page.locator(".scene-builder-render").first()).toBeEnabled();
});

test("@desktop-smoke Scene Builder creates nested element render targets", async ({ page }) => {
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
  const enabled = page.waitForResponse((response) => response.url().endsWith("/subscenes/elements/travelers/enable") && response.ok());
  await page.getByRole("button", { name: "Turn into sub-scene" }).click();
  await enabled;
  await expect(page.locator(".scene-builder-target-breadcrumb")).toHaveText("Full Scene › Travelers");
  await expect(page.getByText("Target element: Travelers", { exact: true })).toBeVisible();

  const travelersTargetId = await page.getByRole("button", { name: "Travelers", exact: true }).getAttribute("data-render-target-id");
  await page.getByRole("button", { name: "Full Scene", exact: true }).click();
  await page.getByRole("button", { name: "Add Element" }).click();
  await page.locator("#builder-element-resource-type").selectOption("Scene-Only");
  await page.locator("#builder-element-scene-name").fill("Rescued travelers");
  await page.locator("#builder-element-add").click();
  await page.locator("[data-builder-element-field='subscene_id']").selectOption(travelersTargetId);
  const fullSceneSaved = page.waitForResponse((response) => response.url().endsWith("/builder") && response.request().method() === "PUT" && response.ok());
  await page.getByRole("button", { name: "Save Full Scene", exact: true }).click();
  await fullSceneSaved;
  await expect(page.locator("#scene-builder-save-state")).toHaveText("Saved");
  await page.locator(".scene-builder-element-menu summary").click();
  const nested = page.waitForResponse((response) => response.url().includes("/subscenes/elements/") && response.url().endsWith("/enable") && response.ok());
  await page.getByRole("button", { name: "Turn into sub-scene" }).click();
  await nested;
  await expect(page.locator(".scene-builder-target-breadcrumb")).toContainText("Full Scene › Travelers › Rescued travelers");
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
  await expect(page.locator(".scene-builder-sticky-context .status-badge")).toHaveText("Needs attention");
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
