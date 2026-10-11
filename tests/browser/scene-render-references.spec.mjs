import { expect, test } from "@playwright/test";
import { restorePristineProjectState } from "./scene-fixtures.mjs";

test.beforeEach(restorePristineProjectState);

test("scene reference previews change URL when a subscene selection changes", async ({ page }) => {
  const base = "/api/stories/Alpha-Story/scenes/Opening-Scene/local-batches";
  const run = {
    run_id: "a".repeat(32), status: "AWAITING_HUMAN_SELECTION", ready_targets: ["main"],
    selected_views: { background: "background-001" }, rankings: {},
    targets: [
      { target_id: "background", label: "Background", kind: "background", dependencies: [] },
      { target_id: "main", label: "Full Scene", kind: "main", dependencies: ["background"] },
    ],
    groups: {
      background: { status: "SELECTED", candidates: [1, 2].map(slot => ({
        candidate_id: `background-00${slot}`, slot, status: "COMPLETE", image_path: `${slot}.png`,
      })) },
      main: { status: "PENDING", candidates: [], next_reference_images: [{
        label: "Background", image_index: 1, prompt_role: "background_reference", sha256: "first-image-hash",
      }] },
    },
  };
  await page.route(`**${base}**`, async route => {
    const url = new URL(route.request().url());
    if (url.pathname.includes("/next-references/") || url.pathname.includes("/images/")) {
      return route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><rect width="8" height="8" fill="blue"/></svg>' });
    }
    if (url.pathname.endsWith("/actions/select")) {
      run.selected_views.background = route.request().postDataJSON().candidate_id;
      run.groups.main.next_reference_images[0].sha256 = "second-image-hash";
    }
    return route.fulfill({ json: url.pathname === base ? { batches: [run] } : run });
  });
  await page.goto("/");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.evaluate(async () => {
    await window.activatePage("scene-batches", { skipAutosave: true });
    await window.SceneBatches.open({ story: "Alpha-Story", scene: "Opening-Scene" });
  });
  const fullScene = page.locator("#scene-batch-groups > section").filter({
    has: page.getByRole("heading", { name: "Full Scene", exact: true }),
  });
  const reference = fullScene.locator(".local-pipeline-sources img");
  await expect.poll(async()=>new URL(await reference.getAttribute("src"),page.url()).searchParams.get("sha256")).toBe("first-image-hash");
  const initialUrl=new URL(await reference.getAttribute("src"),page.url());
  expect(initialUrl.pathname).toMatch(/next-references\/0$/);
  expect(initialUrl.searchParams.get("universe_id")).toBe("Moonsea");
  await expect.poll(() => reference.evaluate(image => image.complete && image.naturalWidth > 0)).toBeTruthy();
  const background = page.locator("#scene-batch-groups > section").filter({
    has: page.getByRole("heading", { name: "Background", exact: true }),
  });
  await background.getByRole("button", { name: "Select", exact: true }).click();
  await expect.poll(async()=>new URL(await reference.getAttribute("src"),page.url()).searchParams.get("sha256")).toBe("second-image-hash");
  await expect.poll(() => reference.evaluate(image => image.complete && image.naturalWidth > 0)).toBeTruthy();
});
