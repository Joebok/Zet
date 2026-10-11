import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { restorePristineProjectState } from "./scene-fixtures.mjs";

test.beforeEach(restorePristineProjectState);

for (const decision of ["promote", "keep-current"]) {
  test(`scene batch publication compares existing locks and applies ${decision}`, async ({ page }) => {
    const scene = "/api/stories/Alpha-Story/scenes/Opening-Scene";
    const created = await page.request.post(`${scene}/local-batches`, { data: {} });
    expect(created.ok(), await created.text()).toBeTruthy();
    const run = await created.json();
    const base = `${scene}/local-batches/${run.run_id}`;
    const image = await readFile(path.resolve("test-results/dashboard-browser-project/Stories/Alpha-Story/Opening-Scene.png"));
    run.status = "READY_TO_PUBLISH";
    run.ready_targets = [];
    const targets = run.targets.map((target, index) => {
      const candidate = run.groups[target.target_id].candidates[0];
      candidate.status = "COMPLETE";
      candidate.image_path = "fixture-candidate.png";
      run.groups[target.target_id].active_candidates = run.groups[target.target_id].candidates;
      run.selected_views[target.target_id] = candidate.candidate_id;
      return { target_id: target.target_id, label: target.label, candidate_id: candidate.candidate_id,
        candidate_sha256: `candidate-${index}`, locked_exists: target.target_id === "main",
        locked_sha256: target.target_id === "main" ? "previous-lock" : "" };
    });
    const submissions = [];
    await page.route(`**${base}`, route => route.fulfill({ json: run }));
    await page.route(`**${base}/publication-review`, route => route.fulfill({ json: { run_id: run.run_id, targets } }));
    await page.route(`**${base}/targets/**/images/*`, route => route.fulfill({ contentType: "image/png", body: image }));
    await page.route(`**${base}/targets/**/locked?*`, route => route.fulfill({ contentType: "image/png", body: image }));
    await page.route(`**${base}/actions/publish`, route => {
      submissions.push(route.request().postDataJSON());
      run.status = "COMPLETE";
      return route.fulfill({ json: run });
    });
    await page.route("**/api/local/batch-status", route => route.fulfill({ json: {
      batch_count: 2, groups: [{ status: "READY_TO_PUBLISH", label: "Ready to publish", batches: [
        { pipeline: "scene", pipeline_label: "Scene", run_id: run.run_id,
          story_slug: "Alpha-Story", scene_slug: "Opening-Scene", status: "READY_TO_PUBLISH",
          href: `/?page=scene-batches&story_slug=Alpha-Story&scene_slug=Opening-Scene&batch=${run.run_id}` },
        { pipeline: "head-image", pipeline_label: "Head-Image", run_id: "character-batch",
          character: "Mira", phase: "Adult", status: "READY_TO_PUBLISH" },
      ] }],
    } }));
    await page.goto("/?page=scenes&story_slug=Alpha-Story&scene_slug=Opening-Scene");
    await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
    await expect(page.locator("#toolbar-batches")).toBeVisible();
    await page.locator("#toolbar-batches").click();
    await expect(page.locator("#local-batch-status-page")).toHaveClass(/active/);
    await expect(page.locator("#workspace-story")).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator("#local-assets-button")).not.toHaveClass(/active/);
    const cards = page.locator(".batch-status-card");
    await expect(cards).toHaveCount(2);
    const colors = await cards.evaluateAll(nodes => nodes.map(node => getComputedStyle(node).backgroundColor));
    expect(colors[0]).not.toBe(colors[1]);
    await cards.first().getByRole("link", { name: "Review & Publish" }).click();
    const dialog = page.locator("#scene-batch-publication-dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText("Current locked image", { exact: true })).toHaveCount(targets.length);
    const submit = page.locator("#scene-batch-publication-submit");
    await expect(submit).toBeDisabled();
    expect(submissions).toHaveLength(0);
    await page.locator("#scene-batch-publication-close").click();
    await expect(dialog).not.toBeVisible();
    expect(submissions).toHaveLength(0);
    await page.locator("#scene-batch-publish").click();
    await expect(dialog).toBeVisible();
    for (const target of targets) {
      const select = dialog.getByRole("combobox", { name: `${target.label} publication decision`, exact: true });
      if (!target.locked_exists) await expect(select.locator('option[value="keep-current"]')).toHaveCount(0);
      await select.selectOption(target.locked_exists ? decision : "promote");
    }
    for (const img of await dialog.locator("img").all()) {
      await expect.poll(() => img.evaluate(node => node.complete && node.naturalWidth > 0)).toBeTruthy();
    }
    await expect(submit).toBeEnabled();
    if (decision === "keep-current") await dialog.screenshot({ path: "test-results/batch-publication-review.png" });
    await submit.click();
    await expect(dialog).not.toBeVisible();
    await expect(page.locator("#scene-batch-status")).toContainText("COMPLETE");
    expect(submissions).toHaveLength(1);
    expect(submissions[0].reviews.main).toEqual({ decision, candidate_id: run.selected_views.main,
      candidate_sha256: targets.find(target => target.target_id === "main").candidate_sha256,
      locked_sha256: "previous-lock" });
  });
}
