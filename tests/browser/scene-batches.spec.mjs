import { expect, test } from "@playwright/test";
import { mkdir, readFile, writeFile, copyFile } from "node:fs/promises";
import path from "node:path";

const fixtureRoot = path.resolve("test-results/dashboard-browser-project");
const scene = "/api/stories/Alpha-Story/scenes/Opening-Scene";
const batches = `${scene}/local-batches`;

test("scene batches keep authoring context, checkpoints, references, publication and Zines", async ({ page }) => {
  test.setTimeout(90_000);
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  const response = await page.request.get(`${scene}/builder`);
  expect(response.ok()).toBeTruthy();
  const data = (await response.json()).document.data;
  data.scene.story_beat = "A traveler crosses a quiet woodland clearing.";
  data.scene_elements = [{id: "traveler", display_name: "Traveler", resource_type: "Scene-Only",
    element_type: "Character", fallback_visual_description: "A cloaked traveler carrying a staff"}];
  data.placements = [{id: "p1", scene_element_id: "traveler", depth: "midground", position_within_cell: "center"}];
  data.subscenes = [{id: "background", name: "Background", kind: "background", enabled: true},
    {id: "traveler_view", name: "Traveler View", kind: "element", enabled: true, anchor_element_id: "traveler"}];
  const saved = await page.request.put(`${scene}/builder`, {data});
  expect(saved.ok(), await saved.text()).toBeTruthy();
  await page.goto("/?page=scenes&story_slug=Alpha-Story&scene_slug=Opening-Scene");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await expect(page.locator("#scenes-page")).toHaveClass(/active/);
  await page.locator("#scene-builder-open").click();
  await expect(page.locator("#scene-builder-page")).toHaveClass(/active/);
  await page.locator("[data-builder-action=render]").first().click();
  await expect(page.locator("#scene-batches-page")).toHaveClass(/active/);
  await expect(page.locator("#scene-batch-plan input")).toHaveCount(3);
  await page.getByText("New batch candidate counts", {exact: true}).click();
  for (const input of await page.locator("#scene-batch-plan input").all()) {
    await expect(input).toHaveValue("4");
    await input.fill("1");
  }
  await page.locator("#scene-batch-name").fill("Browser scene study");
  let releaseCreation;
  const creationReady = new Promise(resolve => { releaseCreation = resolve; });
  await page.route("**/local-batches", async route => {
    if (route.request().method() === "POST") await creationReady;
    await route.continue();
  });
  await page.locator("#scene-batch-new").click();
  await expect(page.locator("#scene-batch-new")).toBeDisabled();
  await expect(page.locator("#scene-batch-message")).toHaveText("Creating scene batch…");
  releaseCreation();
  await expect(page.locator("#scene-batch-status")).toContainText("Browser scene study");
  const runId = new URL(page.url()).searchParams.get("batch");
  expect(runId).toMatch(/^[a-f0-9]{32}$/);
  await page.reload();
  await expect(page.locator("#scene-batch-name")).toHaveValue("Browser scene study");
  const fullScene = page.locator("#scene-batch-groups > section").filter({has: page.getByRole("heading", {name: "Full Scene", exact: true})});
  await expect(fullScene.getByRole("button", {name: "Render", exact: true})).toBeDisabled();
  for (const [target, label] of [["background", "Background"], ["traveler_view", "Traveler View"], ["main", "Full Scene"]]) {
    await page.locator("#scene-batch-start").click();
    const section = page.locator("#scene-batch-groups > section").filter({has: page.getByRole("heading", {name: label, exact: true})});
    await expect(section).toContainText("QUEUED");
    await expect(section.getByRole("link", {name: "Image prompt", exact: true})).toBeVisible();
    const run = await (await page.request.get(`${batches}/${runId}`)).json();
    const candidate = run.groups[target].candidates[0];
    const ask = path.join(fixtureRoot, "Queue/File_Proxy/Ask/zet", candidate.ask_id);
    const answer = path.join(fixtureRoot, "Queue/File_Proxy/Answer/zet", candidate.ask_id);
    expect(answer.startsWith(fixtureRoot + path.sep)).toBeTruthy();
    await mkdir(answer, {recursive: true});
    await copyFile(path.join(ask, "ask_manifest.json"), path.join(answer, "ask_manifest.json"));
    await copyFile(path.join(fixtureRoot, "Stories/Alpha-Story/Opening-Scene.png"), path.join(answer, "render.png"));
    await writeFile(path.join(answer, "answer_manifest.json"), JSON.stringify({ask_id: candidate.ask_id, status: "SUCCESS", expected_output: "render.png"}));
    await expect.poll(async () => (await (await page.request.get(`${batches}/${runId}`)).json()).rankings[target]?.status).toBe("COMPLETE");
    await page.locator("#scene-batch-refresh").click();
    await expect(section.getByRole("button", {name: "Select", exact: true})).toBeEnabled();
    expect((await (await page.request.get(`${batches}/${runId}`)).json()).selected_views[target]).toBeUndefined();
    if (target === "main") {
      let releaseReview;
      const reviewReady = new Promise(resolve => { releaseReview = resolve; });
      await page.route("**/actions/review", async route => { await reviewReady; await route.continue(); });
      const review = section.getByRole("combobox", {name: `${candidate.candidate_id} human review`, exact: true});
      await review.selectOption("keep");
      await expect(review).toBeDisabled();
      await expect(section.getByRole("button", {name: "Select", exact: true})).toBeDisabled();
      releaseReview();
      await expect(review).toBeEnabled();
      await expect(review).toHaveValue("keep");
      await expect(section.locator(".local-pipeline-sources img")).toHaveCount(2);
      await expect(section.locator("figcaption").first()).toContainText("Image 1");
      await expect(section.locator("figcaption").nth(1)).toContainText("Image 2");
      for (const image of await section.locator(".local-pipeline-sources img").all()) {
        await expect.poll(() => image.evaluate(node => node.complete && node.naturalWidth > 0)).toBeTruthy();
      }
    }
    await section.getByRole("button", {name: "Select", exact: true}).click();
    await expect(section).toContainText("Selected");
  }
  await expect(page.locator("#scene-batch-publish")).toBeEnabled();
  await page.locator("#scene-batch-publish").click();
  await expect(page.locator("#scene-batch-status")).toContainText("COMPLETE");
  const provenance = JSON.parse(await readFile(path.join(fixtureRoot, "Pipelines/Stories/Alpha-Story/Opening-Scene/Locked_Render.render.json"), "utf8"));
  expect(provenance.batch_id).toBe(runId);
  await page.screenshot({path: "test-results/scene-batches.png", fullPage: true});
  await expect(page.locator(".tab[data-page=render-console]")).toHaveCount(0);
  await expect(page.locator(".tab[data-page=render-review]")).toHaveCount(0);
  await page.locator(".tab[data-page=zine]").click();
  await expect(page.locator("#zine-page")).toHaveClass(/active/);
  const sources = await page.request.get("/api/zines/story-scenes/Alpha-Story");
  expect(sources.ok()).toBeTruthy();
  expect((await sources.json()).scenes.some(item => item.tag === "{{SCENE:Alpha-Story:Opening-Scene}}")).toBeTruthy();
  expect(errors).toEqual([]);
});
