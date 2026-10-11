import { expect, test } from "@playwright/test";
import { restorePristineProjectState } from "./scene-fixtures.mjs";

test.beforeEach(restorePristineProjectState);

for (const costume of ["Canonical Adventure Gear", "School Outfit"]) {
  test(`costume lock displays correctly for ${costume}`, async ({ page }) => {
    const qualifier = costume.replaceAll(" ", "_");
    const assetKey = `costume-dressing:${qualifier.toLowerCase()}:FRONT`;
    const asset = {
      pipeline: "Costume-Dressing", view: "FRONT", qualifier,
      candidate_id: "F-001", batch_id: "costume-batch", locked: false,
    };
    const run = {
      run_id: "costume-batch", character: "Test", phase: "Adult", costume,
      status: "AWAITING_HUMAN_SELECTION", views: ["FRONT"], candidate_count: 1,
      selected_views: { FRONT: "F-001" }, rankings: {},
      local_assets: {
        [assetKey]: asset,
        "costume-dressing:other_outfit:FRONT": { ...asset, qualifier: "Other_Outfit", locked: true },
      },
      candidates: [{ candidate_id: "F-001", view: "FRONT", status: "COMPLETE", image_path: "/images/front" }],
    };
    await page.route("**/api/local-gates/**", (route) => route.fulfill({ json: { gates: {}, statuses: {} } }));
    await page.route("**/api/costumes?**", (route) => route.fulfill({ json: { costumes: [{ name: costume }] } }));
    await page.route("**/api/local/costume-dressing/**", async (route) => {
      const url = new URL(route.request().url());
      if (url.pathname.endsWith("/preview")) {
        await route.fulfill({ json: { views: ["FRONT"], candidate_count: 1 } });
      } else if (url.pathname.endsWith("/runs")) {
        await route.fulfill({ json: { runs: [{ run_id: run.run_id, status: run.status }] } });
      } else if (url.pathname.endsWith("/lock-preview")) {
        await route.fulfill({ json: { changes: [] } });
      } else if (url.pathname.endsWith("/lock") || url.pathname.endsWith("/unlock")) {
        expect(url.searchParams.get("costume")).toBe(costume);
        asset.locked = url.pathname.endsWith("/lock");
        await route.fulfill({ json: asset });
      } else if (url.pathname.endsWith(`/runs/${run.run_id}`)) {
        await route.fulfill({ json: run });
      } else {
        await route.fulfill({ body: "" });
      }
    });
    await page.addInitScript(() => localStorage.setItem("zet:workspace-preferences", JSON.stringify({
      workspace: "local", pages: { character: "local-overview", local: "local-body-reference" },
    })));
    await page.goto("/");
    await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
    await page.locator("#local-assets-button").click();
    await page.locator('#local-assets-menu [data-page="local-costume-dressing"]').click();
    const card = page.locator(".local-pipeline-selected-card");
    await expect(card).toContainText("Selected · not locked");
    page.on("dialog", (dialog) => dialog.accept());
    await card.getByRole("button", { name: "Lock", exact: true }).click();
    await expect(card).toContainText("Locked local asset");
    await expect(card.getByRole("button", { name: "Unlock", exact: true })).toBeVisible();
    await expect(card.getByRole("button", { name: "Unselect", exact: true })).toHaveCount(0);
    await page.reload();
    await expect(card).toContainText("Locked local asset");
    await card.getByRole("button", { name: "Unlock", exact: true }).click();
    await expect(card).toContainText("Selected · not locked");
    await expect(card.getByRole("button", { name: "Lock", exact: true })).toBeVisible();
  });
}
