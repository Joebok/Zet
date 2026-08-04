import { expect, test } from "@playwright/test";

const DESKTOP_VIEWPORTS = [
  [1920, 911],
  [1600, 900],
  [1440, 900],
  [1366, 768],
  [1280, 800],
  [1920, 768],
];

async function openPage(page, pageName) {
  const contextResponse = page.waitForResponse((response) => response.url().endsWith("/api/context"));
  await page.goto("/");
  await page.waitForFunction(() => typeof window.activatePage === "function");
  await contextResponse;
  await expect(page.locator("#character-select option")).not.toHaveCount(0);
  await page.evaluate(async (name) => window.activatePage(name, { skipAutosave: true }), pageName);
  await expect(page.locator(`#${pageName}-page`)).toHaveClass(/active/);
}

test("desktop layouts do not overflow and match approved snapshots", async ({ page }) => {
  for (const [width, height] of DESKTOP_VIEWPORTS) {
    await page.setViewportSize({ width, height });
    await openPage(page, "assets");
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth))
      .toBe(true);
    await expect(page).toHaveScreenshot(`dashboard-assets-${width}x${height}.png`, {
      fullPage: false,
    });
  }
});

test("shared action and disabled styles remain distinguishable", async ({ page }) => {
  await openPage(page, "assets");
  const classes = ["primary-action", "update-action", "create-action", "navigation-action", "neutral-action", "danger-action"];
  const styles = await page.evaluate((actionClasses) => {
    const host = document.body.appendChild(document.createElement("div"));
    return actionClasses.map((className) => {
      const button = host.appendChild(document.createElement("button"));
      button.className = className;
      button.disabled = true;
      const style = getComputedStyle(button);
      return {
        className,
        display: style.display,
        cursor: style.cursor,
        opacity: Number(style.opacity),
        background: style.backgroundColor,
      };
    });
  }, classes);
  for (const style of styles) {
    expect(style.display).not.toBe("none");
    expect(style.cursor).toBe("not-allowed");
    expect(style.opacity).toBeLessThan(1);
  }
  await expect(page.locator("#source-editor-recompile")).toHaveCount(0);
  await expect(page.locator("#source-editor-clear-review-aids")).toHaveCount(0);
  await expect(page.locator(".fullscreen-image-overlay")).not.toHaveAttribute("open", "");
  await expect(page.locator(".fullscreen-image-close")).toBeHidden();
});

test("toolbar is a keyboard-operable disclosure", async ({ page }) => {
  await openPage(page, "assets");
  const toggle = page.locator("#toolbar-settings-button");
  await toggle.focus();
  await page.keyboard.press("Enter");
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator("#toolbar-settings-menu button").first()).toBeFocused();
  const menuOverlaysContent = await page.locator("#toolbar-settings-menu").evaluate((menu) => {
    const rect = menu.getBoundingClientRect();
    const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + 8);
    return rect.top > 0 && rect.bottom <= window.innerHeight && Boolean(hit?.closest("#toolbar-settings-menu"));
  });
  expect(menuOverlaysContent).toBe(true);
  await page.keyboard.press("Escape");
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(toggle).toBeFocused();
});

test("Aux Images is accessible from the main button row", async ({ page }) => {
  await openPage(page, "assets");
  await page.getByRole("button", { name: "Aux Images" }).click();
  await expect(page.locator("#auxiliary-resources-page")).toHaveClass(/active/);
});

test("To Do saves when dismissed", async ({ page }) => {
  let savedText = null;
  await page.route("**/api/todo", async (route) => {
    if (route.request().method() === "POST") {
      savedText = route.request().postDataJSON().text;
      await route.fulfill({ status: 200, contentType: "application/json", body: '{"message":"To Do saved."}' });
    } else {
      await route.continue();
    }
  });
  await openPage(page, "assets");
  await page.locator("#toolbar-todo-button").click();
  await page.locator("#todo-text").fill("Saved on dismiss");
  await page.keyboard.press("Escape");
  await expect(page.locator("#todo-dialog")).not.toBeVisible();
  await expect.poll(() => savedText).toBe("Saved on dismiss");
});

test("story changes autosave before selection changes", async ({ page }) => {
  await openPage(page, "stories");
  const rows = page.locator("#story-table .row-selection-button");
  await expect(rows).toHaveCount(3);
  await rows.nth(0).click();
  const editor = page.locator("#story-text");
  await editor.fill("Title: `[Alpha Story]`\n\nAutosaved browser change.\n");
  await expect(page.locator("#story-save-state")).toContainText("Dirty");
  await rows.nth(1).click();
  await expect(page.locator("#story-save-state")).toContainText("Saved");
  const saved = await page.request.get("/api/stories/Alpha-Story");
  expect((await saved.json()).document.text).toContain("Autosaved browser change.");
});

test("story and scene lists show titles with visible order controls", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await openPage(page, "stories");
  await expect(page.locator("#story-table th")).toHaveText(["Title", "Order"]);
  await expect(page.locator("#story-table .order-controls").first()).toBeVisible();

  await page.evaluate(() => window.activatePage("scenes", { skipAutosave: true }));
  await expect(page.locator("#scenes-page")).toHaveClass(/active/);
  await expect(page.locator("#scene-table th")).toHaveText(["Scene", "Order"]);
  await expect(page.locator("#scene-table .order-controls").first()).toBeVisible();
  await expect(page.locator(".scene-picker-panel")).toBeHidden();
});

test("failed and rapid story transitions preserve a current selection", async ({ page }) => {
  await openPage(page, "stories");
  const rows = page.locator("#story-table .row-selection-button");
  await rows.nth(0).click();
  await page.route("**/api/stories/Alpha-Story", async (route) => {
    if (route.request().method() === "PUT") {
      await route.fulfill({ status: 500, contentType: "application/json", body: '{"detail":"Seeded save failure"}' });
    } else {
      await route.continue();
    }
  });
  await page.locator("#story-text").fill("Title: `[Alpha Story]`\n\nFailed change.\n");
  await rows.nth(1).click();
  await expect(rows.nth(0)).toHaveAttribute("aria-current", "true");
  await expect(page.locator("#story-save-state")).toContainText("Error");

  await page.unroute("**/api/stories/Alpha-Story");
  await page.locator("#story-save").click();
  await rows.nth(1).click();
  await rows.nth(2).click();
  await expect(page.locator("#story-editor-title")).toHaveText("Gamma Story");
  await expect(rows.nth(2)).toHaveAttribute("aria-current", "true");
});

test("scene and Scene Builder changes autosave on navigation", async ({ page }) => {
  await openPage(page, "scenes");
  const rows = page.locator("#scene-table .row-selection-button");
  await expect(rows).toHaveCount(2);
  const initialSceneSlug = await page.locator("#scene-table tr.selected").getAttribute("data-scene-slug");
  const initialSceneText = await page.locator("#scene-text").inputValue();
  const initialSceneTitle = initialSceneText.split("\n", 1)[0];
  await page.locator("#scene-text").fill(`${initialSceneTitle}\n\nAutosaved scene change.\n`);
  await page.locator("#scene-table tr:not(.selected) .row-selection-button").click();
  await expect
    .poll(() => page.locator("#scene-table tr.selected").getAttribute("data-scene-slug"))
    .not.toBe(initialSceneSlug);
  const saved = await page.request.get(`/api/stories/Alpha-Story/scenes/${initialSceneSlug}`);
  expect((await saved.json()).document.text).toContain("Autosaved scene change.");

  const selectedSceneSlug = await page.locator("#scene-table tr.selected").getAttribute("data-scene-slug");
  await page.route(`**/api/stories/Alpha-Story/scenes/${selectedSceneSlug}`, async (route) => {
    if (route.request().method() === "PUT") {
      await route.fulfill({ status: 500, contentType: "application/json", body: '{"detail":"Seeded scene save failure"}' });
    } else {
      await route.continue();
    }
  });
  await page.locator("#scene-text").fill("Scene save must fail.");
  await page.locator("#scene-table tr:not(.selected) .row-selection-button").click();
  await expect(page.locator("#scene-save-state")).toContainText("Error");
  await expect(page.locator("#scene-table tr.selected")).toHaveAttribute("data-scene-slug", selectedSceneSlug);
  await page.unroute(`**/api/stories/Alpha-Story/scenes/${selectedSceneSlug}`);
  await page.locator("#scene-save").click();

  await rows.nth(0).click();
  const referencesRefreshed = page.waitForResponse((response) => response.url().includes("/api/scene-image-picker"));
  await page.locator("#scene-builder-open").click();
  await referencesRefreshed;
  await expect(page.locator("#scene-builder-page")).toHaveClass(/active/);
  const storyBeat = page.locator('[data-builder-field="scene.story_beat"]');
  await storyBeat.fill("Autosaved builder beat.");
  await page.locator("button[data-page='stories']").click();
  await expect(page.locator("#stories-page")).toHaveClass(/active/);
  await openPage(page, "scenes");
  await page.locator("#scene-builder-open").click();
  await expect(page.locator('[data-builder-field="scene.story_beat"]')).toHaveValue("Autosaved builder beat.");
  await page.route("**/api/stories/*/scenes/*/builder", async (route) => {
    if (route.request().method() === "PUT") {
      await route.fulfill({ status: 500, contentType: "application/json", body: '{"detail":"Seeded builder save failure"}' });
    } else {
      await route.continue();
    }
  });
  await page.locator('[data-builder-field="scene.story_beat"]').fill("Builder save must fail.");
  await page.locator("button[data-page='stories']").click();
  await expect(page.locator("#scene-builder-page")).toHaveClass(/active/);
  await expect(page.locator("#scene-builder-message")).toContainText("Seeded builder save failure");
  await page.unroute("**/api/stories/*/scenes/*/builder");
});

test("Scene Builder text changes do not consume the next control click", async ({ page }) => {
  await openPage(page, "scenes");
  await page.locator("#scene-builder-open").click();
  const storyBeat = page.locator('[data-builder-field="scene.story_beat"]');
  const orientation = page.locator('[data-builder-field="setup.canvas.orientation"]');
  await storyBeat.fill("Changed before selecting an orientation.");
  await orientation.evaluate((control) => { window.sceneBuilderClickedControl = control; });
  const box = await orientation.boundingBox();
  expect(box).not.toBeNull();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await expect.poll(() => page.evaluate(() => window.sceneBuilderClickedControl.isConnected)).toBe(true);
  await page.mouse.up();
  await expect.poll(() => page.evaluate(() => (
    window.sceneBuilderClickedControl === document.querySelector('[data-builder-field="setup.canvas.orientation"]')
  ))).toBe(true);
});

test("source editor guards dirty navigation with Cancel and Discard", async ({ page }) => {
  await openPage(page, "assets");
  await page.locator("#asset-table .row-selection-button").first().click();
  await page.locator("#open-governing-template").click();
  await expect(page.locator("#template-editor-page")).toHaveClass(/active/);
  await page.locator("#source-editor-text").fill("Unsaved source editor change");
  await page.locator("button[data-page='stories']").click();
  const dialog = page.locator("#unsaved-changes-dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(page.locator("#template-editor-page")).toHaveClass(/active/);
  await page.locator("button[data-page='stories']").click();
  await dialog.getByRole("button", { name: "Discard" }).click();
  await expect(page.locator("#stories-page")).toHaveClass(/active/);

  await openPage(page, "assets");
  await page.locator("#asset-table .row-selection-button").first().click();
  await page.locator("#open-governing-template").click();
  await page.locator("#source-editor-text").fill("Saved source editor change");
  await page.locator("button[data-page='stories']").click();
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(page.locator("#stories-page")).toHaveClass(/active/);
});

test("dirty editors register beforeunload protection", async ({ page }) => {
  await openPage(page, "assets");
  await page.locator("#asset-table .row-selection-button").first().click();
  await page.locator("#open-governing-template").click();
  await page.locator("#source-editor-text").fill("Dirty before unload");
  let beforeUnloadSeen = false;
  page.on("dialog", async (dialog) => {
    beforeUnloadSeen = dialog.type() === "beforeunload";
    await dialog.accept();
  });
  await page.reload();
  expect(beforeUnloadSeen).toBe(true);
});

test("project settings support Cancel, Discard, and Save", async ({ page }) => {
  await openPage(page, "local-image-config");
  const scale = page.locator("#setting-zine-print-scale");
  await scale.fill("0.91");
  await page.locator("button[data-page='stories']").click();
  const dialog = page.locator("#unsaved-changes-dialog");
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(page.locator("#local-image-config-page")).toHaveClass(/active/);
  await page.locator("button[data-page='stories']").click();
  await dialog.getByRole("button", { name: "Discard" }).click();
  await expect(page.locator("#stories-page")).toHaveClass(/active/);

  await openPage(page, "local-image-config");
  await scale.fill("0.92");
  await page.locator("button[data-page='stories']").click();
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(page.locator("#stories-page")).toHaveClass(/active/);
  const controls = await page.request.get("/api/pipeline-controls?character=Test&phase=Adult");
  expect((await controls.json()).automation.zine_print_scale).toBe(0.92);
});

test("selection, zine ordering, live status, and image dialogs are accessible", async ({ page }) => {
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

test("scene fullscreen navigation follows scene order and reports missing images", async ({ page }) => {
  await openPage(page, "scenes");
  await page.locator("#scene-table .row-selection-button").first().click();
  await page.locator("#scene-toggle-image").click();
  await page.locator(".fullscreen-image-button:has(#scene-image-preview)").click();

  const imageDialog = page.locator(".fullscreen-image-overlay");
  const previous = imageDialog.getByRole("button", { name: "Previous scene" });
  const next = imageDialog.getByRole("button", { name: "Next scene" });
  await expect(previous).toBeVisible();
  await expect(previous).toBeDisabled();
  await expect(next).toBeEnabled();
  const initialSource = await imageDialog.locator(":scope > img").getAttribute("src");
  await page.keyboard.press("ArrowLeft");
  await expect(imageDialog.locator(":scope > img")).toHaveAttribute("src", initialSource);

  await page.route("**/api/stories/Alpha-Story/scenes/Opening-Scene", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.document.image_exists = false;
    body.document.image_path = null;
    await route.fulfill({ response, json: body });
  });
  await page.keyboard.press("ArrowRight");
  await expect(imageDialog.locator(".fullscreen-image-empty")).toHaveText("No Image for Opening Scene");
  await expect(next).toBeDisabled();
  await page.keyboard.press("ArrowRight");
  await expect(imageDialog.locator(".fullscreen-image-empty")).toHaveText("No Image for Opening Scene");
});

test("pending scene image links open the matching side-by-side review", async ({ page }) => {
  await openPage(page, "scenes");
  await page.locator('#scene-table tr[data-scene-slug="Closing-Scene"] .row-selection-button').click();
  await page.locator("#scene-toggle-image").click();
  const pendingLink = page.locator("#scene-image-candidate-link");
  await expect(pendingLink).toHaveText("Candidate Image Pending");
  await expect(pendingLink).toHaveAttribute("href", /story_slug=Alpha-Story.*scene_slug=Closing-Scene/);
  await pendingLink.click();

  await expect(page.locator("#render-review-page")).toHaveClass(/active/);
  await expect(page.locator("#render-review-title")).toContainText("Closing Scene");
  await expect(page.locator("#candidate-render img")).toBeVisible();
  await expect(page.locator("#locked-render img")).toBeVisible();
});

test("View Story opens the selected story in scene order", async ({ page }) => {
  await openPage(page, "stories");
  await page.locator("#story-table .row-selection-button", { hasText: "Alpha Story" }).click();
  await page.locator("#story-view").click();

  const imageDialog = page.locator(".fullscreen-image-overlay");
  await expect(imageDialog).toBeVisible();
  await expect(imageDialog.getByRole("button", { name: "Previous scene" })).toBeDisabled();
  await expect(imageDialog.getByRole("button", { name: "Next scene" })).toBeEnabled();
  await expect(imageDialog.locator(":scope > img")).toHaveAttribute("src", /Closing-Scene\.png/);
  await page.keyboard.press("ArrowRight");
  await expect(imageDialog.locator(":scope > img")).toHaveAttribute("src", /Opening-Scene\.png/);
  await page.keyboard.press("Escape");
});

test("scene render tasks open their scene in Scene Builder", async ({ page }) => {
  await openPage(page, "scenes");
  await page.locator('#scene-table tr[data-scene-slug="Opening-Scene"] .row-selection-button').click();
  await page.locator("#scene-stage-render").click();
  await expect(page.locator("#render-console-page")).toHaveClass(/active/);
  const sceneBuilder = page.locator("#render-console-scene-builder");
  await expect(sceneBuilder).toBeVisible();
  await expect(sceneBuilder).toBeEnabled();
  await sceneBuilder.click();
  await expect(page.locator("#scene-builder-page")).toHaveClass(/active/);
  await expect(page.locator("#scene-builder-status")).toHaveText("Alpha-Story / Opening-Scene");
});

test("scene prompts and Scene Builder show analysis in a dismissible popup", async ({ page }) => {
  await openPage(page, "scenes");
  await page.locator('#scene-table tr[data-scene-slug="Opening-Scene"] .row-selection-button').click();
  await page.locator("#scene-stage-render").click();
  await expect(page.locator("#render-console-scene-builder")).toBeVisible();
  await page.locator("#render-console-review-prompt").click();
  await expect(page.locator("#prompt-review-page")).toHaveClass(/active/);

  const sceneBuilder = page.locator("#prompt-review-scene-builder");
  const promptEye = page.locator("#view-prompt-analysis");
  const analysisDialog = page.locator("#prompt-analysis-dialog");
  await expect(sceneBuilder).toBeVisible();
  await expect(promptEye).toHaveClass(/complete/);
  await promptEye.click();
  await expect(analysisDialog).toBeVisible();
  await expect(page.locator("#prompt-analysis-frame")).toHaveAttribute("src", /prompt-analysis\/view$/);
  await page.mouse.click(1, 1);
  await expect(analysisDialog).not.toBeVisible();

  await sceneBuilder.click();
  await expect(page.locator("#scene-builder-page")).toHaveClass(/active/);
  const builderEye = page.locator('[data-builder-action="view-analysis"]');
  await expect(builderEye).toBeVisible();
  await expect(page.locator('[data-builder-action="analyze-prompt"]')).toHaveCount(0);
  await builderEye.click();
  await expect(analysisDialog).toBeVisible();
  await page.mouse.click(1, 1);
  await expect(analysisDialog).not.toBeVisible();
});

test("zine changes support Cancel, Discard, and Save", async ({ page }) => {
  await openPage(page, "zine");
  await expect(page.locator("#zine-editor-title")).toHaveText("Browser Zine");
  const dialog = page.locator("#unsaved-changes-dialog");
  await page.locator("#zine-front").fill("{{SCENE:Beta-Story:Opening-Scene}}");
  await page.locator("button[data-page='stories']").click();
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(page.locator("#zine-page")).toHaveClass(/active/);
  await page.locator("button[data-page='stories']").click();
  await dialog.getByRole("button", { name: "Discard" }).click();
  await expect(page.locator("#stories-page")).toHaveClass(/active/);

  await openPage(page, "zine");
  await page.locator("#zine-front").fill("{{SCENE:Beta-Story:Opening-Scene}}");
  await page.locator("button[data-page='stories']").click();
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(page.locator("#stories-page")).toHaveClass(/active/);
});

test("local image previews use the full fixed review region", async ({ page }) => {
  await openPage(page, "local-image-review");
  await page.locator("#local-image-review-task-table .row-selection-button").first().click();
  const previews = page.locator(".local-image-review-preview");
  await expect(previews).toHaveCount(3);
  for (const preview of await previews.all()) {
    const box = await preview.boundingBox();
    expect(box.height).toBeGreaterThanOrEqual(359);
    const image = preview.locator("img");
    const fit = await image.evaluate((node) => getComputedStyle(node).objectFit);
    expect(fit).toBe("contain");
  }
  await expect(page.locator("#local-image-review-task-table th")).toHaveCount(1);
  await expect(page.locator("#local-image-review-task-table tbody tr").first().locator("td")).toHaveCount(1);
  expect(await page.locator("#local-image-review-task-table").evaluate((table) => table.scrollWidth <= table.clientWidth)).toBe(true);
});

test("Prompts, Render, and Local Images share the same asset sidebar", async ({ page }) => {
  const sidebars = [
    ["prompt-review", "prompt-review-task-table", "prompt-review-refresh"],
    ["render-console", "render-console-task-table", "render-console-refresh"],
    ["local-image-review", "local-image-review-task-table", "local-image-review-refresh"],
  ];
  const widths = [];
  for (const [pageName, tableId, refreshId] of sidebars) {
    await openPage(page, pageName);
    await expect(page.locator(`#${refreshId}`)).toBeVisible();
    await expect(page.locator(`#${tableId} th`)).toHaveCount(1);
    await expect(page.locator(`#${tableId} tbody tr`).first().locator("td")).toHaveCount(1);
    expect(await page.locator(`#${tableId}`).evaluate((table) => table.scrollWidth <= table.clientWidth)).toBe(true);
    widths.push((await page.locator(`#${tableId}`).boundingBox()).width);
  }
  expect(Math.max(...widths) - Math.min(...widths)).toBeLessThanOrEqual(1);
});

test("scoped destructive confirmations cancel and complete explicitly", async ({ page }) => {
  await openPage(page, "local-image-review");
  await page.locator("#local-image-review-task-table .row-selection-button").first().click();
  await page.locator("#local-image-review-clear").click();
  const dialog = page.locator("#confirmation-dialog");
  await expect(dialog).toContainText("Clear 3 local image(s)");
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(page.locator(".local-image-review-preview")).toHaveCount(3);

  await page.locator("#local-image-review-clear").click();
  await dialog.getByRole("button", { name: "Clear Images" }).click();
  await expect(page.locator(".local-image-review-preview")).toHaveCount(0);

  await openPage(page, "ai-controls");
  await page.locator("#archive-harvested-ai").click();
  await expect(dialog).toContainText("1 harvested answer");
  await dialog.getByRole("button", { name: "Cancel" }).click();

  await openPage(page, "pipeline-controls");
  await page.locator("#batch-render-reset").click();
  await expect(dialog).toContainText(/affected|No assets/i);
  if (await dialog.isVisible()) {
    await dialog.getByRole("button", { name: "Cancel" }).click();
  }
});

test("AI Controls stacks queue lists and manages Zet processes", async ({ page }) => {
  await openPage(page, "ai-controls");
  const queueSections = page.locator(".queue-tables > section");
  await expect(queueSections.locator("h3")).toHaveText(["Running", "Ask", "Answer"]);
  const widths = await queueSections.evaluateAll((sections) => sections.map((section) => section.getBoundingClientRect().width));
  expect(Math.max(...widths) - Math.min(...widths)).toBeLessThan(1);

  const processes = page.locator("#process-table tbody tr");
  await expect(processes).toHaveCount(2);
  await expect(processes.nth(0)).toContainText("Zet Web Dashboard");
  await expect(processes.nth(1)).toContainText("Auto Harvester");
  await expect(processes.locator("button")).toHaveCount(6);
});
