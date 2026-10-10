import { expect, test } from "@playwright/test";

test("scene builder starts when legacy character assets are unavailable and can create an element subscene", async ({ page }) => {
  await page.route("**/api/assets?*", route => route.fulfill({
    status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Assets.json not found" }),
  }));
  await page.goto("/?page=scene-builder&story_slug=Alpha-Story&scene_slug=Opening-Scene");
  await expect(page.locator("#scene-builder-page")).toHaveClass(/active/);
  await expect(page.getByRole("button", { name: "Open/Create Scene Batch", exact: true })).toBeVisible();
  await expect(page.locator("#header-story-select")).toHaveValue("Alpha-Story");
  const response = await page.request.get("/api/stories/Alpha-Story/scenes/Opening-Scene/builder");
  const data = (await response.json()).document.data;
  data.subscenes = [];
  data.scene_elements = [{ id: "students", display_name: "Students", resource_type: "Scene-Only",
    element_type: "Character", fallback_visual_description: "Three academy students" }];
  data.placements = [{ id: "students-placement", scene_element_id: "students", depth: "background" }];
  expect((await page.request.put("/api/stories/Alpha-Story/scenes/Opening-Scene/builder", { data })).ok()).toBeTruthy();
  await page.reload();
  await page.locator(".scene-builder-element-row").filter({ hasText: "Students" }).click();
  await page.locator(".scene-builder-element-menu summary").click();
  await page.getByRole("button", { name: "Use element sub-render", exact: true }).click();
  await expect(page.getByRole("button", { name: "Turn off element sub-render", exact: true })).toBeVisible();
  const created = (await (await page.request.get("/api/stories/Alpha-Story/scenes/Opening-Scene/builder")).json()).document.data;
  expect(created.subscenes).toContainEqual(expect.objectContaining({ kind: "element", enabled: true, anchor_element_id: "students" }));
});
