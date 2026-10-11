import { expect, test } from "@playwright/test";
import { restorePristineProjectState } from "./scene-fixtures.mjs";

test.beforeEach(restorePristineProjectState);

test("costume batch displays saved render errors with expandable details", async ({ page }) => {
  const message = "Qwen Image 2.1 supports at most ten reference images; received 11.\nMissing reference: <image4>";
  const run = {
    run_id: "failed-costume-batch", character: "Test", phase: "Adult", costume: "Test Outfit",
    status: "AWAITING_HUMAN_SELECTION", views: ["FRONT"], candidate_count: 2,
    selected_views: {}, rankings: {}, local_assets: {},
    candidates: [
      { candidate_id: "F-001", view: "FRONT", status: "FAILED", render_status: "FAILED", render_error: message },
      { candidate_id: "F-002", view: "FRONT", status: "PENDING", render_status: "PENDING" },
    ],
  };
  await page.route("**/api/local-gates/**", (route) => route.fulfill({ json: { gates: {}, statuses: {} } }));
  await page.route("**/api/costumes?**", (route) => route.fulfill({ json: { costumes: [{ name: run.costume }] } }));
  await page.route("**/api/local/costume-dressing/**", (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/preview")) {
      return route.fulfill({ json: { views: run.views, candidate_count: 2 } });
    }
    if (url.pathname.endsWith("/runs")) {
      return route.fulfill({ json: { runs: [{ run_id: run.run_id, status: run.status }] } });
    }
    if (url.pathname.endsWith(`/runs/${run.run_id}`)) return route.fulfill({ json: run });
    return route.fulfill({ body: "" });
  });
  await page.addInitScript(() => localStorage.setItem("zet:workspace-preferences", JSON.stringify({
    workspace: "local", pages: { character: "local-overview", local: "local-body-reference" },
  })));
  await page.goto("/");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.locator("#local-assets-button").click();
  await page.locator('#local-assets-menu [data-page="local-costume-dressing"]').click();
  const failed = page.locator('.local-pipeline-candidate[data-candidate="F-001"]');
  const details = failed.locator("details.local-pipeline-render-error");
  await expect(details.locator("summary")).toHaveText(`Render error: ${message.split("\n")[0]}`);
  await details.locator("summary").click();
  await expect(details.locator("p")).toBeVisible();
  await expect(details.locator("p")).toHaveText(message);
  await expect(details.locator("image4")).toHaveCount(0);
  await expect(page.locator('.local-pipeline-candidate[data-candidate="F-002"] details')).toHaveCount(0);
  await page.reload();
  await expect(details.locator("summary")).toContainText("received 11");
});
