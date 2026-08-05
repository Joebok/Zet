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
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await expect(page.locator("#character-select option")).not.toHaveCount(0);
  await page.evaluate(async (name) => window.activatePage(name, { skipAutosave: true }), pageName);
  await expect(page.locator(`#${pageName}-page`)).toHaveClass(/active/);
}

async function expectNoHorizontalOverflow(page) {
  const overflowing = await page.evaluate(() => {
    const selectors = [
      "html", "body", "main", ".page.active", ".page.active .scene-builder-card",
      ".page.active .review-main", ".page.active .review-sidebar", ".page.active .asset-table-panel",
      ".page.active table", ".page.active form",
    ];
    return selectors.flatMap((selector) => Array.from(document.querySelectorAll(selector)))
      .filter((element) => element.getClientRects().length > 0 && element.scrollWidth > element.clientWidth + 1)
      .map((element) => element.id || element.className || element.tagName);
  });
  expect(overflowing).toEqual([]);
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

test("shared action roles and control states use the semantic design system", async ({ page }) => {
  await openPage(page, "assets");
  const classes = ["primary-action", "update-action", "create-action", "navigation-action", "neutral-action", "danger-action"];
  const styles = await page.evaluate((actionClasses) => {
    const host = document.body.appendChild(document.createElement("div"));
    return actionClasses.map((className) => {
      const button = host.appendChild(document.createElement("button"));
      button.className = className;
      const enabledStyle = getComputedStyle(button);
      const enabled = {
        background: enabledStyle.backgroundColor,
        border: enabledStyle.borderColor,
        color: enabledStyle.color,
        minHeight: enabledStyle.minHeight,
      };
      button.disabled = true;
      const disabledStyle = getComputedStyle(button);
      return {
        className,
        enabled,
        disabled: {
          background: disabledStyle.backgroundColor,
          cursor: disabledStyle.cursor,
          display: disabledStyle.display,
          opacity: Number(disabledStyle.opacity),
        },
      };
    });
  }, classes);
  const byClass = Object.fromEntries(styles.map((style) => [style.className, style]));
  expect(byClass["primary-action"].enabled.background).toBe(byClass["update-action"].enabled.background);
  expect(byClass["primary-action"].enabled.background).toBe(byClass["create-action"].enabled.background);
  expect(byClass["navigation-action"].enabled.background).toBe(byClass["neutral-action"].enabled.background);
  expect(byClass["danger-action"].enabled.background).not.toBe(byClass["primary-action"].enabled.background);
  expect(new Set(styles.map((style) => style.disabled.background)).size).toBe(1);
  for (const style of styles) {
    expect(style.enabled.minHeight).toBe("36px");
    expect(style.disabled.display).not.toBe("none");
    expect(style.disabled.cursor).toBe("not-allowed");
    expect(style.disabled.opacity).toBeLessThan(1);
  }
  const chrome = await page.evaluate(() => ({
    focus: getComputedStyle(document.documentElement).getPropertyValue("--focus").trim(),
    headerImage: getComputedStyle(document.querySelector(".header-middle")).backgroundImage,
    headerBackground: getComputedStyle(document.querySelector(".header-middle")).backgroundColor,
    tabsBackground: getComputedStyle(document.querySelector(".tabs")).backgroundColor,
  }));
  expect(chrome.focus).toBe("#7c3aed");
  expect(chrome.headerImage).toBe("none");
  expect(chrome.headerBackground).not.toBe(chrome.tabsBackground);
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

test("workspace shell switches adaptive context and remembers the last page", async ({ page }) => {
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

test("first visit chooses Story Overview for a ready character and Character Overview when setup is incomplete", async ({ page }) => {
  await page.goto("/");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await expect(page.locator("#workspace-story")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#stories-page")).toHaveClass(/active/);

  await page.context().clearCookies();
  await page.evaluate(() => window.localStorage.clear());
  await page.route("**/api/context", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.onboarding_statuses.Test.Adult.complete = false;
    await route.fulfill({ response, json: body });
  });
  await page.goto("/");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await expect(page.locator("#workspace-character")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#onboarding-page")).toHaveClass(/active/);
});

test("workspace overviews show readiness, image states, and scene navigation", async ({ page }) => {
  await openPage(page, "onboarding");
  await expect(page.locator("#character-workflow > li")).toHaveCount(5);
  await expect(page.locator("#character-overview-metrics .overview-metric")).toHaveCount(6);
  await expect(page.locator("#character-recommended-label")).not.toBeEmpty();

  await page.locator("#workspace-story").click();
  await expect(page.locator("#stories-page .overview-recommendation")).toHaveCount(0);
  await expect(page.locator("#story-overview-scenes .story-overview-scene")).toHaveCount(2);
  await expect(page.locator("#story-overview-scenes")).toContainText("Candidate ready");
  await expect(page.locator("#header-story-select")).toHaveValue("Alpha-Story");
  await expect(page.locator("#header-scene-select option")).toHaveCount(2);
  await page.locator("#story-overview-scenes .story-overview-scene").first().click();
  await expect(page.locator("#scene-builder-page")).toHaveClass(/active/);
  await expect(page.locator("#header-scene-select")).toHaveValue("Closing-Scene");
});

test("adaptive context and workspace changes preserve dirty story edits", async ({ page }) => {
  await openPage(page, "stories");
  await page.locator("#story-text").fill("Title: `[Alpha Story]`\n\nSaved from adaptive context.\n");
  const contextSave = page.waitForResponse((response) => response.url().endsWith("/api/stories/Alpha-Story") && response.request().method() === "PUT");
  await page.locator("#header-story-select").selectOption("Beta-Story");
  await contextSave;
  const savedByContext = await page.request.get("/api/stories/Alpha-Story");
  expect((await savedByContext.json()).document.text).toContain("Saved from adaptive context.");
  await expect(page.locator("#header-story-select")).toHaveValue("Beta-Story");

  await page.locator("#story-text").fill("Title: `[Beta Story]`\n\nSaved on workspace switch.\n");
  const workspaceSave = page.waitForResponse((response) => response.url().endsWith("/api/stories/Beta-Story") && response.request().method() === "PUT");
  await page.locator("#workspace-character").click();
  await workspaceSave;
  const savedByWorkspace = await page.request.get("/api/stories/Beta-Story");
  expect((await savedByWorkspace.json()).document.text).toContain("Saved on workspace switch.");
  await expect(page.locator("#workspace-character")).toHaveAttribute("aria-pressed", "true");
});

test("New menu follows the active workspace", async ({ page }) => {
  await openPage(page, "assets");
  await page.locator("#new-menu-button").click();
  await expect(page.locator("#new-character")).toBeVisible();
  await expect(page.locator("#new-story")).toBeHidden();
  await page.keyboard.press("Escape");

  await page.locator("#workspace-story").click();
  await page.locator("#new-menu-button").click();
  await expect(page.locator("#new-character")).toBeHidden();
  await expect(page.locator("#new-story")).toBeVisible();
});

test("Aux Images is accessible from the main button row", async ({ page }) => {
  await openPage(page, "assets");
  await page.locator("#workspace-story").click();
  await page.getByRole("button", { name: "Aux Images" }).click();
  await expect(page.locator("#auxiliary-resources-page")).toHaveClass(/active/);
  const thumbnailFit = await page.evaluate(() => {
    const image = document.body.appendChild(document.createElement("img"));
    image.className = "aux-resource-thumb";
    return getComputedStyle(image).objectFit;
  });
  expect(thumbnailFit).toBe("contain");
});

test("pipeline inspection filters pipelines and previews text and images", async ({ page }) => {
  await openPage(page, "assets");
  await page.locator("#toolbar-settings-button").click();
  await page.locator("#toolbar-settings-menu button[data-page='pipeline-inspection']").click();
  await expect(page.locator("#pipeline-inspection-page")).toHaveClass(/active/);
  const previewHeight = await page.locator(".pipeline-inspection-preview").evaluate((element) => element.getBoundingClientRect().height);
  expect(previewHeight).toBeGreaterThan(page.viewportSize().height - 150);
  await expect(page.locator("#pipeline-inspection-list button")).toHaveCount(5);
  await page.locator("#pipeline-inspection-search").fill("Alpha-Story / Opening");
  await expect(page.locator("#pipeline-inspection-list button")).toHaveCount(1);
  await page.locator("#pipeline-inspection-list button").click();
  await page.getByRole("button", { name: "AI_Prompt_Analysis.md", exact: true }).click();
  await expect(page.locator("#pipeline-inspection-text")).toContainText("Deterministic browser-test analysis");
  await expect(page.locator("#pipeline-inspection-path")).toContainText("AI_Prompt_Analysis.md");
  await expect(page.locator("#pipeline-inspection-copy")).toBeEnabled();
  await expect(page.locator("#pipeline-inspection-open-folder")).toBeEnabled();

  await page.locator("#pipeline-inspection-search").fill("Alpha-Story / Closing");
  await page.locator("#pipeline-inspection-list button").click();
  await page.getByRole("button", { name: "Candidate/Closing-Scene.png", exact: true }).click();
  await expect(page.locator("#pipeline-inspection-image")).toBeVisible();

  await page.locator("#pipeline-inspection-search").fill("Test / Adult / Body-Reference");
  await page.getByRole("button", { name: "Front · Asset 1", exact: true }).click();
  await page.getByRole("button", { name: "_stage.txt", exact: true }).click();
  await expect(page.locator("#pipeline-inspection-text")).toHaveText("RENDER");
  await page.getByRole("button", { name: "_history.log", exact: true }).click();
  await expect(page.locator("#pipeline-inspection-text")).toContainText("Asset 1 created");
});

test("pipeline inspection ignores stale file-list responses", async ({ page }) => {
  await page.route("**/api/pipeline-inspection/files?*", async (route) => {
    const pipelineId = new URL(route.request().url()).searchParams.get("pipeline_id");
    if (pipelineId === "Stories/Alpha-Story/Opening-Scene") {
      await new Promise((resolve) => setTimeout(resolve, 300));
    }
    await route.continue();
  });
  await openPage(page, "pipeline-inspection");
  const search = page.locator("#pipeline-inspection-search");
  await search.fill("Alpha-Story / Opening");
  await page.locator("#pipeline-inspection-list button").click();
  await search.fill("Alpha-Story / Closing");
  await page.locator("#pipeline-inspection-list button").click();
  await expect(page.getByRole("button", { name: "Candidate/Closing-Scene.png", exact: true })).toBeVisible();
  await page.waitForTimeout(400);
  await expect(page.getByRole("button", { name: "Candidate/Closing-Scene.png", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "AI_Prompt_Analysis.md", exact: true })).toHaveCount(0);
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
  await page.locator("#toolbar-settings-button").click();
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

test("Scene Builder hierarchy streamlines authoring and preserves hidden legacy notes", async ({ page }) => {
  await openPage(page, "scenes");
  let savedBuilder = null;
  await page.route("**/api/stories/*/scenes/*/builder", async (route) => {
    if (route.request().method() === "GET") {
      const response = await route.fetch();
      const payload = await response.json();
      payload.document.data.scene.author_notes = "Preserve private scene note";
      payload.document.data.scene_elements = [{
        id: "Lantern",
        display_name: "Lantern",
        resource_type: "Scene-Only",
        element_type: "Prop",
        reference_images: [],
        element_visual_override: "",
        fallback_visual_description: "brass lantern",
        notes: "Preserve private element note",
      }];
      payload.document.data.placements = [{
        id: "placement_lantern",
        scene_element_id: "Lantern",
        position_within_cell: "center",
        depth: "foreground",
        world_position: "beside the doorway",
        pose: {},
        motion: { state: "stationary", direction_screen: "", cue: "" },
        placement_notes: "Warm light spills across the threshold",
      }];
      payload.document.data.dialogue = [{
        id: "dialogue_lantern",
        speaker_element_id: "Lantern",
        target_element_id: "",
        text: "Light the way.",
        pointer_target: "speaker mouth",
        max_lines: 3,
        notes: "Keep dialogue special instructions",
      }];
      payload.document.data.interactions = [{
        subject_element_id: "Lantern",
        relationship: "illuminates",
        target_element_id: "",
        note: "Keep interaction note",
      }];
      await route.fulfill({ response, json: payload });
      return;
    }
    if (route.request().method() === "PUT") {
      savedBuilder = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          document: { data: savedBuilder, validation_warnings: [] },
          has_story_changes: true,
          message: "Scene Builder saved.",
        }),
      });
      return;
    }
    await route.continue();
  });

  await page.locator("#scene-builder-open").click();
  const columns = page.locator(".scene-builder-grid > .scene-builder-section");
  await expect(columns).toHaveCount(5);
  await expect(page.locator('[data-builder-section-panel="scene"] .scene-builder-card').first()).toContainText("Story Beat");
  await expect(page.locator('[data-builder-section-panel="elements"] .scene-builder-card').first()).toContainText("Scene Elements");
  await expect(page.locator('[data-builder-section-panel="dialogue"] .scene-builder-card').first()).toContainText("Dialogue");
  await expect(page.locator(".scene-builder-element-workspace")).toContainText("Identity and reference");
  await expect(page.locator(".scene-builder-element-workspace")).toContainText("Placement and acting");
  await expect(page.locator(".scene-builder-element-row")).toContainText("Prop");
  await expect(page.locator(".scene-builder-element-row")).toContainText("No reference");
  await expect(page.locator(".scene-builder-element-row")).toContainText("Position: center · Depth: foreground");
  await expect(page.locator(".scene-builder-advanced")).not.toHaveAttribute("open", "");
  await expect(page.locator('[data-builder-section-panel="elements"]').getByRole("button", { name: "Add Element" })).toBeVisible();
  await page.locator(".scene-builder-element-menu > summary").click();
  const elementMenu = page.locator(".scene-builder-element-menu");
  await expect(elementMenu.getByRole("button", { name: "Duplicate", exact: true })).toBeVisible();
  await expect(elementMenu.getByRole("button", { name: "Delete", exact: true })).toBeVisible();
  await page.locator(".scene-builder-element-menu > summary").click();

  await expect(page.locator('[data-builder-field="scene.author_notes"]')).toHaveCount(0);
  await expect(page.locator('[data-builder-element-field="notes"]')).toHaveCount(0);
  await expect(page.locator('[data-builder-field="setup.environment.general_foreground_notes"]')).toBeVisible();
  await expect(page.locator('[data-builder-field="setup.environment.general_background_notes"]')).toBeVisible();
  await expect(page.locator('[data-builder-dialogue-field="notes"]')).toHaveValue("Keep dialogue special instructions");
  await expect(page.locator('[data-builder-interaction-field="note"]')).toHaveValue("Keep interaction note");
  await expect(page.locator('[data-builder-field="scene.story_settings_path"]')).toHaveCount(0);
  await expect(page.locator('[data-builder-field="scene.associated_png_path"]')).toHaveCount(0);
  await expect(page.locator("#scene-builder-panel")).not.toContainText("Render Settings / Validation");
  await expect(page.locator("#scene-builder-panel")).not.toContainText("JSON Preview");
  await expect(page.getByText("Placement instructions — included in prompt", { exact: true })).toBeVisible();
  await expect(page.locator("#scene-builder-save-state")).toHaveText("Saved");
  await expect(page.getByRole("button", { name: "Save", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Render", exact: true })).toBeVisible();
  await expect(page.getByText("Save JSON", { exact: true })).toHaveCount(0);

  const placementInstructions = page.locator('[data-builder-placement-field="placement_notes"]');
  await placementInstructions.fill("Lantern light defines the foreground edge");
  await expect(page.locator("#scene-builder-save-state")).toHaveText("Dirty");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect.poll(() => savedBuilder).not.toBeNull();
  expect(savedBuilder.scene.author_notes).toBe("Preserve private scene note");
  expect(savedBuilder.scene_elements[0].notes).toBe("Preserve private element note");
  expect(savedBuilder.placements[0].placement_notes).toBe("Lantern light defines the foreground edge");
  await expect(page.locator("#scene-builder-save-state")).toHaveText("Saved");

  await page.locator(".scene-builder-more > summary").click();
  await expect(page.getByText("Technical Details", { exact: true })).toBeVisible();
  await page.getByText("Technical Details", { exact: true }).click();
  await expect(page.locator(".scene-builder-technical-details")).toContainText("Story settings");
  await expect(page.locator(".scene-builder-technical-details")).toContainText("Scene image");
});

test("iPad uses compact navigation and a two-pane sectioned Scene Builder", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 });
  await openPage(page, "scenes");
  await expect(page.locator("#responsive-section-menu")).toBeVisible();
  await expect(page.locator("#story-navigation")).toBeHidden();
  await expect(page.locator("#story-context")).toBeVisible();

  await page.locator("#responsive-section-menu").selectOption("scene-builder");
  await expect(page.locator("#scene-builder-page")).toHaveClass(/active/);
  const switcher = page.locator(".builder-section-switcher");
  await expect(switcher).toBeVisible();
  await expect(switcher.getByRole("tab", { name: "Elements" })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator('[data-builder-section-panel="elements"]')).toBeVisible();
  await expect(page.locator('[data-builder-section-panel="scene"]')).toBeHidden();
  const elementColumns = await page.locator('[data-builder-section-panel="elements"]').evaluate((element) => (
    getComputedStyle(element).gridTemplateColumns.split(" ").filter(Boolean).length
  ));
  expect(elementColumns).toBe(2);

  await expect(page.locator(".scene-builder-primary-actions > .scene-builder-save")).toBeHidden();
  await page.locator(".scene-builder-more > summary").click();
  await expect(page.locator(".scene-builder-menu-panel").getByRole("button", { name: "Save", exact: true })).toBeVisible();
  await expect(page.locator(".scene-builder-menu-panel").getByRole("button", { name: "Render", exact: true })).toBeVisible();
  await expect(page.locator(".scene-builder-menu-panel").getByRole("button", { name: "Continue From…" })).toBeVisible();
  await expect(page.locator(".scene-builder-menu-panel").getByRole("button", { name: "Prompt Analysis" })).toBeVisible();
  await expect(page.locator(".scene-builder-menu-panel").getByRole("button", { name: "Candidate Review" })).toBeVisible();
  for (const control of await page.locator("#responsive-section-menu, .builder-section-switcher button, .scene-builder-more > summary").all()) {
    expect((await control.boundingBox()).height).toBeGreaterThanOrEqual(44);
  }
  await expectNoHorizontalOverflow(page);
  await page.locator("#responsive-section-menu").selectOption("ai-controls");
  const queueBox = await page.locator("#ai-controls-page .queue-panel").boundingBox();
  const controlsBox = await page.locator("#ai-controls-page").boundingBox();
  expect(queueBox.width / controlsBox.width).toBeGreaterThan(0.9);
  await expectNoHorizontalOverflow(page);
});

test("responsive navigation restores its selection when dirty navigation is canceled", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 });
  await openPage(page, "assets");
  await page.locator("#asset-table .row-selection-button").first().click();
  await page.locator("#open-governing-template").click();
  await page.locator("#source-editor-text").fill("Unsaved responsive editor change");
  await page.locator("#responsive-section-menu").selectOption("assets");
  const dialog = page.locator("#unsaved-changes-dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(page.locator("#responsive-section-menu")).toHaveValue("template-editor");
  await expect(page.locator("#template-editor-page")).toHaveClass(/active/);
  await page.locator("#responsive-section-menu").selectOption("assets");
  await dialog.getByRole("button", { name: "Discard" }).click();
  await expect(page.locator("#assets-page")).toHaveClass(/active/);
});

test("phone workspaces are view-first and Scene Builder uses single-open accordions", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openPage(page, "stories");
  await expect(page.locator("#responsive-section-menu")).toBeVisible();
  await expect(page.locator("#toolbar-settings-button")).toHaveText("More ▾");
  const viewer = page.locator("#story-phone-viewer");
  await expect(viewer).toBeVisible();
  await expect(viewer.locator("img")).toBeVisible();
  const viewerBox = await viewer.boundingBox();
  const editorBox = await page.locator("#stories-page .story-layout").boundingBox();
  expect(viewerBox.y).toBeLessThan(editorBox.y);
  expect(viewerBox.y).toBeLessThan(844);
  await viewer.locator(".fullscreen-image-button").click();
  await expect(page.locator(".fullscreen-image-overlay")).toBeVisible();
  await page.keyboard.press("Escape");
  const initialTitle = await page.locator("#story-phone-viewer-title").textContent();
  const navigationButton = await page.locator("#story-phone-next:not(:disabled), #story-phone-previous:not(:disabled)").first();
  await navigationButton.click();
  await expect(page.locator("#story-phone-viewer-title")).not.toHaveText(initialTitle);

  await page.locator("#responsive-section-menu").selectOption("scene-builder");
  const toggles = page.locator(".builder-phone-section-toggle");
  await expect(toggles).toHaveCount(5);
  await expect(toggles.filter({ hasText: "Elements" })).toHaveAttribute("aria-expanded", "true");
  await toggles.filter({ hasText: "Dialogue" }).click();
  await expect(page.locator('.builder-phone-section-toggle[aria-expanded="true"]')).toHaveCount(1);
  await expect(page.locator('[data-builder-section-panel="dialogue"]')).toBeVisible();
  await expect(page.locator('[data-builder-section-panel="elements"]')).toBeHidden();

  await page.locator("#responsive-section-menu").selectOption("scenes");
  await expect(page.locator("#scene-table")).toHaveCSS("display", "block");
  await expect(page.locator("#scene-table thead")).toBeHidden();
  await expect(page.locator("#scene-table tbody tr").first()).toHaveCSS("display", "block");
  await expect(page.locator("#scene-table tbody td").first()).toHaveAttribute("data-label", "Scene");

  await page.locator("#responsive-section-menu").selectOption("ai-controls");
  await expect(page.locator("#queue-ask-table")).toHaveClass(/responsive-list-table/);
  await expect(page.locator("#queue-ask-table tbody td").first()).toHaveAttribute("data-label", "Ask ID");
  await expect(page.locator("#queue-ask-table tbody tr").first()).toHaveCSS("display", "block");
  await expectNoHorizontalOverflow(page);

  await page.locator("#workspace-character").click();
  await page.locator("#responsive-section-menu").selectOption("onboarding");
  await expect(page.locator("#character-phone-viewer")).toBeVisible();
  await expect(page.locator("#character-phone-viewer img")).toBeVisible();
  expect(await page.locator(".character-phone-links button").evaluateAll((buttons) => (
    buttons.every((button) => button.scrollWidth <= button.clientWidth + 1)
  ))).toBe(true);
  await expectNoHorizontalOverflow(page);
});

test("source editor guards dirty navigation with Cancel and Discard", async ({ page }) => {
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

test("scene workflow keeps context and production tools default to current work", async ({ page }) => {
  await openPage(page, "scenes");
  await page.locator("#header-scene-select").selectOption("Closing-Scene");

  const scopedRequest = page.waitForRequest((request) => request.url().includes("/api/render-console/tasks?"));
  await page.locator("#scene-workflow-menu").selectOption("render-console");
  const scopedUrl = new URL((await scopedRequest).url());
  expect(scopedUrl.searchParams.get("story_slug")).toBe("Alpha-Story");
  expect(scopedUrl.searchParams.get("scene_slug")).toBe("Closing-Scene");
  await expect(page.locator("#header-story-select")).toHaveValue("Alpha-Story");
  await expect(page.locator("#header-scene-select")).toHaveValue("Closing-Scene");
  await expect(page.locator("#render-console-page .production-scope-label")).toContainText("Alpha-Story / Closing-Scene");

  const allRequest = page.waitForRequest((request) => request.url().includes("/api/render-console/tasks?"));
  await page.locator("#render-console-page .production-scope-toggle").click();
  const allUrl = new URL((await allRequest).url());
  expect(allUrl.searchParams.has("story_slug")).toBe(false);
  expect(allUrl.searchParams.has("scene_slug")).toBe(false);
  await expect(page.locator("#render-console-page .production-scope-label")).toHaveText("All work");

  await page.locator("#scene-workflow-menu").selectOption("prompt-review");
  await expect(page.locator("#prompt-review-page")).toHaveClass(/active/);
  await expect(page.locator("#header-story-select")).toHaveValue("Alpha-Story");
  await expect(page.locator("#header-scene-select")).toHaveValue("Closing-Scene");

  await page.locator("#scene-workflow-menu").selectOption("locked-image");
  await expect(page.locator(".fullscreen-image-overlay")).toBeVisible();
  await expect(page.locator(".fullscreen-image-overlay > img")).toHaveAttribute("src", /Closing-Scene\.png/);
  await page.keyboard.press("Escape");
});

test("Scene Builder creates and selects an auxiliary resource without losing context", async ({ page }) => {
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
  const resource = (await (await created).json()).resource;

  await expect(page.locator("#builder-element-modal")).toBeVisible();
  await expect(page.locator("#builder-element-aux")).toHaveValue(resource.resource_id);
  await expect(page.locator("#header-story-select")).toHaveValue("Alpha-Story");
  await expect(page.locator("#header-scene-select")).not.toHaveValue("");
  await page.locator("#builder-element-add").click();
  await expect(page.locator(".scene-builder-element-list")).toContainText("Story Lantern");
});

test("scene prompts and Scene Builder show analysis in a dismissible popup", async ({ page }) => {
  await openPage(page, "scenes");
  await page.locator('#scene-table tr[data-scene-slug="Opening-Scene"] .row-selection-button').click();
  await page.locator("#scene-stage-render").click();
  await expect(page.locator("#render-console-scene-builder")).toBeVisible();
  await page.locator("#story-production-menu").selectOption("prompt-review");
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
  await page.locator(".scene-builder-more > summary").click();
  const builderEye = page.locator('[data-builder-action="view-analysis"]');
  await expect(builderEye).toBeVisible();
  await expect(page.locator('[data-builder-action="analyze-prompt"]')).toHaveCount(0);
  await builderEye.click();
  await expect(analysisDialog).toBeVisible();
  await page.mouse.click(1, 1);
  await expect(analysisDialog).not.toBeVisible();

  await page.locator("#story-production-menu").selectOption("render-console");
  const queued = page.waitForRequest((request) => (
    request.method() === "POST" && request.url().includes("/prompt-analysis")
  ));
  await page.locator("#render-console-review-prompt").click();
  await queued;
  await expect(page.locator("#prompt-review-page")).toHaveClass(/active/);
  await expect(promptEye).toHaveClass(/pending/);
  await expect(promptEye).toHaveAttribute("title", "Prompt analysis pending");
  await expect(promptEye).toHaveAttribute("aria-label", "Prompt analysis pending");
  const promptActions = await page.locator("#prompt-review-title + .button-row button").allTextContents();
  expect(promptActions.slice(0, 3)).toEqual(["Scene Builder", "Render Console", "Copy Prompt"]);
  await page.locator("#prompt-review-render-console").click();
  await expect(page.locator("#render-console-page")).toHaveClass(/active/);
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
  await openPage(page, "assets");
  await page.evaluate(() => window.activatePage("local-image-review", { skipAutosave: true }));
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
  await openPage(page, "assets");
  await page.evaluate(() => window.activatePage("local-image-review", { skipAutosave: true }));
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
