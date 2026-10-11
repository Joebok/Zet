import { expect, test } from "@playwright/test";
import { restorePristineProjectState } from "./scene-fixtures.mjs";

test.beforeEach(restorePristineProjectState);

test("costume wizard validates image captions and opens a resumable draft", async ({ page }) => {
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  const session = {
    session_id: "0123456789abcdef0123456789abcdef", character: "Test", phase: "Adult", name: "Travel Coat",
    status: "DRAFT_READY", revision_id: "draft-revision-1", markdown: "Costume Name: `[Travel Coat]`\n",
    questions: [], validation_errors: [], draft_review: "Draft review complete.", refinements: [], test_image: false, test_renders: [],
    job: { kind: "draft", status: "COMPLETE", error: "" }, updated_at: "2026-10-04T12:00:00",
  };
  await page.route("**/api/costumes?**", (route) => route.fulfill({ json: { costumes: [] } }));
  await page.route("**/api/costume-wizard?**", async (route) => {
    if (route.request().method() === "GET") return route.fulfill({ json: { sessions: [] } });
    return route.fulfill({ json: { session } });
  });
  await page.addInitScript(() => localStorage.setItem("zet:workspace-preferences", JSON.stringify({
    workspace: "character", pages: { character: "costumes", local: "local-body-reference" },
  })));
  await page.goto("/");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.locator('[data-page="costumes"]').click();
  await page.locator("#costume-wizard-open").click();
  const dialog = page.locator("#costume-wizard-dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.locator(".costume-wizard-image-slot")).toHaveCount(3);
  await dialog.locator("#costume-wizard-name").fill("Travel Coat");
  await dialog.locator(".costume-wizard-image-slot").nth(0).locator("input[type=file]").setInputFiles({
    name: "front.png", mimeType: "image/png", buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/pXcAAAAASUVORK5CYII=", "base64"),
  });
  await dialog.locator("#costume-wizard-create").click();
  await expect(dialog.locator("#costume-wizard-message")).toContainText("Describe what reference image 1 conveys");
  await dialog.locator(".costume-wizard-caption").nth(0).fill("Front of the outfit");
  await dialog.locator("#costume-wizard-create").click();
  await expect(dialog.locator("#costume-wizard-markdown")).toHaveValue(session.markdown);
  await expect(dialog.locator("#costume-wizard-review")).toContainText("Draft review complete.");
  expect(pageErrors).toEqual([]);
});
