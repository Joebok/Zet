import { expect, test } from "@playwright/test";

const pipelines = ["body-reference", "head-image", "character-assembly", "costume-dressing"];
const config = { configured: true, project_id: "project-aaaaaaaa", board_url: "http://127.0.0.1:8000/", zet_revision: "a".repeat(40) };
const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/QioAAAAASUVORK5CYII=", "base64");

function run(id = "batch-1", costume = "Travel") {
  return { run_id: id, batch_name: `Named ${id}`, character: "Test", phase: "Adult", costume,
    status: "AWAITING_HUMAN_SELECTION", views: ["FRONT"], candidate_count: 1, selected_views: {}, rankings: {},
    candidates: [{ candidate_id: "F-001", view: "FRONT", status: "COMPLETE", render_status: "COMPLETE", image_path: "/images/front" }] };
}

async function mocks(page, pipeline, runs = [run()], costumes = ["Travel", "Formal"]) {
  await page.route("**/api/tasks/config", (route) => route.fulfill({ json: config }));
  await page.route("**/api/local-gates/**", (route) => route.fulfill({ json: { gates: {}, statuses: {} } }));
  await page.route("**/api/costumes?**", (route) => route.fulfill({ json: { costumes: costumes.map((name) => ({ name })) } }));
  await page.route(`**/api/local/${pipeline}/**`, (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/preview")) return route.fulfill({ json: { can_create: true, views: ["FRONT"], candidate_count: 1 } });
    if (url.pathname.endsWith("/runs")) return route.fulfill({ json: { runs } });
    if (url.pathname.includes("/images/")) return route.fulfill({ body: png, contentType: "image/png" });
    const selected = runs.find((item) => url.pathname.endsWith(`/runs/${item.run_id}`));
    return selected ? route.fulfill({ json: selected }) : route.fulfill({ status: 404, json: { detail: "Missing run" } });
  });
}

async function open(page, pipeline, extra = "") {
  await page.goto(`/?page=local-${pipeline}&character=Test&phase=Adult${extra}`);
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await expect(page.locator("#local-pipeline-title")).toBeVisible();
}

async function capture(page) {
  await page.locator("#toolbar-create-task").click();
  await expect(page.locator("#task-capture-submit")).toBeEnabled();
  return JSON.parse(await page.locator("#task-capture-context").textContent());
}

for (const pipeline of pipelines) {
  test(`capture and return restore ${pipeline} batch context`, async ({ page }) => {
    await mocks(page, pipeline, [run("batch-1"), run("batch-2", "Formal")]);
    await open(page, pipeline, "&local_batch=batch-2&local_costume=Formal");
    await expect(page.locator("#local-pipeline-batch-name")).toHaveValue("Named batch-2");
    const snapshot = await capture(page);
    expect(snapshot.page_id).toBe(`local-${pipeline}`);
    expect(snapshot.selections).toMatchObject({ character: { state: "selected", id: "Test" }, phase: { state: "selected", id: "Adult" },
      pipeline: { state: "selected", id: pipeline }, batch: { state: "selected", id: "batch-2", label: "Named batch-2" }, run: { state: "selected", id: "batch-2" } });
    if (pipeline === "costume-dressing") expect(snapshot.selections.costume).toMatchObject({ state: "selected", id: "Formal" });
    else expect(snapshot.selections.costume).toBeUndefined();
    expect(snapshot.selections.story).toBeUndefined();
    await page.goto(snapshot.source_url);
    await expect(page.locator("#local-pipeline-batch-name")).toHaveValue("Named batch-2");
    await expect(page.locator("#character-select")).toHaveValue("Test");
    await expect(page.locator("#phase-select")).toHaveValue("Adult");
    if (pipeline === "costume-dressing") await expect(page.locator("#local-pipeline-costume")).toHaveValue("Formal");
  });
}

test("a loading batch snapshot stays frozen when its detail arrives", async ({ page }) => {
  await mocks(page, "body-reference");
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  await page.route("**/api/local/body-reference/runs/batch-1", async (route) => {
    await gate;
    await route.fulfill({ json: run() });
  });
  await open(page, "body-reference", "&local_batch=batch-1");
  await expect(page.locator("#local-pipeline-runs")).toHaveValue("batch-1");
  const snapshot = await capture(page);
  expect(snapshot.selections.run).toMatchObject({ state: "loading", id: "batch-1" });
  release();
  await expect(page.locator("#local-pipeline-batch-name")).toHaveValue("Named batch-1");
  expect(JSON.parse(await page.locator("#task-capture-context").textContent())).toEqual(snapshot);
  await page.locator("#task-capture-refresh").click();
  await expect.poll(async () => JSON.parse(await page.locator("#task-capture-context").textContent()).selections.run.state).toBe("selected");
});

test("failed run details are unavailable rather than stale selected data", async ({ page }) => {
  await mocks(page, "head-image");
  await page.route("**/api/local/head-image/runs/batch-1", (route) => route.fulfill({ status: 404, json: { detail: "Missing run" } }));
  await open(page, "head-image", "&local_batch=batch-1");
  await expect(page.locator("#local-pipeline-status")).toContainText("Missing run");
  const snapshot = await capture(page);
  expect(snapshot.selections.run).toMatchObject({ state: "unavailable", id: "batch-1" });
});

test("missing costume and batch show notices while the pipeline page opens", async ({ page }) => {
  await mocks(page, "costume-dressing");
  await open(page, "costume-dressing", "&task_context=1&local_costume=Deleted&local_batch=missing");
  await expect(page.locator("#task-context-notice")).toContainText('costume "Deleted" is unavailable');
  await expect(page.locator("#task-context-notice")).toContainText('batch "missing" is unavailable');
  await expect(page.locator("#local-pipeline-batch-name")).toHaveValue("Named batch-1");
});

test("missing character and phase report fallback explicitly", async ({ page }) => {
  await mocks(page, "body-reference");
  await page.goto("/?page=local-body-reference&task_context=1&character=Deleted&phase=Missing");
  await expect(page.locator("#task-context-notice")).toContainText('character "Deleted" is unavailable');
  await expect(page.locator("#local-pipeline-title")).toBeVisible();
  await page.goto("/?page=local-body-reference&task_context=1&character=Test&phase=Missing");
  await expect(page.locator("#task-context-notice")).toContainText('phase "Missing" is unavailable');
  await expect(page.locator("#local-pipeline-title")).toBeVisible();
});

test("missing universe still opens the recorded page", async ({ page }) => {
  await mocks(page, "body-reference");
  await open(page, "body-reference", "&task_context=1&task_universe=Deleted");
  await expect(page.locator("#task-context-notice")).toContainText('universe "Deleted" is unavailable');
  await expect(page.locator("#local-pipeline-title")).toBeVisible();
});

test("candidate review captures its candidate and backend asset key", async ({ page }) => {
  const detail = run();
  detail.local_assets = { "body-reference:FRONT": { candidate_id: "F-001", batch_id: "batch-1" } };
  await mocks(page, "body-reference", [detail]);
  await open(page, "body-reference");
  await expect(page.locator("#local-pipeline-batch-name")).toHaveValue("Named batch-1");
  await page.locator("#local-pipeline-views").getByRole("button", { name: "Review", exact: true }).first().click();
  await page.locator("#local-pipeline-review-task").click();
  const snapshot = JSON.parse(await page.locator("#task-capture-context").textContent());
  expect(snapshot.selections.candidate).toMatchObject({ state: "selected", id: "F-001" });
  expect(snapshot.selections.asset).toMatchObject({ state: "selected", id: "body-reference:FRONT" });
});

test("a Batches card reports its row and Return to Zet restores the selected card", async ({ page }) => {
  await page.route("**/api/tasks/config", (route) => route.fulfill({ json: config }));
  const batch = { ...run(), pipeline: "costume-dressing", pipeline_label: "Costume-Dressing", character: "Row character", phase: "Row phase" };
  await page.route("**/api/local/batch-status", (route) => route.fulfill({ json: { batch_count: 1, groups: [{ label: "Review", batches: [batch] }] } }));
  await page.goto("/?page=local-batch-status");
  await page.locator('[data-run-id="batch-1"]').getByRole("button", { name: "Create task" }).click();
  const snapshot = JSON.parse(await page.locator("#task-capture-context").textContent());
  expect(snapshot.page_id).toBe("local-batch-status");
  expect(snapshot.selections.character.id).toBe("Row character");
  expect(snapshot.selections.phase.id).toBe("Row phase");
  expect(snapshot.selections.costume.id).toBe("Travel");
  await page.goto(snapshot.source_url);
  await expect(page.locator('[data-run-id="batch-1"]')).toHaveAttribute("aria-current", "true");
  await page.locator("#toolbar-create-task").click();
  expect(JSON.parse(await page.locator("#task-capture-context").textContent())).toEqual(snapshot);
});

test("missing selected Batches card retains the page and reports unavailable", async ({ page }) => {
  await page.route("**/api/tasks/config", (route) => route.fulfill({ json: config }));
  await page.route("**/api/local/batch-status", (route) => route.fulfill({ json: { groups: [] } }));
  await page.goto("/?page=local-batch-status&task_context=1&task_batch=Deleted");
  await expect(page.locator("#task-context-notice")).toContainText('batch "Deleted" is unavailable');
  const snapshot = await capture(page);
  expect(snapshot.selections.batch).toMatchObject({ state: "unavailable", id: "Deleted" });
  expect(snapshot.selections.character).toBeUndefined();
});

test("recorded universe scopes context, pipeline requests, and images without selecting the global default", async ({ page }) => {
  await mocks(page, "body-reference");
  await page.route("**/api/universes", (route) => route.fulfill({ json: { selected_universe_id: "Moonsea",
    universes: [{ universe_id: "Moonsea", name: "Moonsea" }, { universe_id: "Other", name: "Other" }] } }));
  let contextUniverse;
  await page.route("**/api/context", async (route) => {
    contextUniverse = route.request().headers()["x-zet-universe"];
    // Reuse fixture data while testing a separate, mocked universe's transport.
    const response = await route.fetch({ headers: { ...route.request().headers(), "x-zet-universe": "Moonsea" } });
    await route.fulfill({ response });
  });
  const requests = [];
  page.on("request", (request) => { if (request.url().includes("/api/local/body-reference/")) requests.push(request); });
  let selectedDefault = false;
  await page.route("**/api/universes/select", (route) => { selectedDefault = true; return route.fulfill({ json: {} }); });
  await open(page, "body-reference", "&task_context=1&task_universe=Other");
  await expect(page.locator("#local-pipeline-batch-name")).toHaveValue("Named batch-1");
  const snapshot = await capture(page);
  expect(snapshot.universe_id).toBe("Other");
  expect(contextUniverse).toBe("Other");
  expect(selectedDefault).toBe(false);
  const dataRequests = requests.filter((request) => !request.url().includes("/images/"));
  expect(dataRequests.length).toBeGreaterThan(0);
  expect(dataRequests.every((request) => request.headers()["x-zet-universe"] === "Other")).toBe(true);
  await expect(page.locator("#local-pipeline-views img").first()).toHaveAttribute("src", /universe_id=Other/);
});

test("late run details cannot overwrite a newer batch selection", async ({ page }) => {
  await mocks(page, "body-reference", [run("batch-1"), run("batch-2")]);
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  await page.route("**/api/local/body-reference/runs/batch-1", async (route) => {
    await gate;
    await route.fulfill({ json: run("batch-1") });
  });
  await open(page, "body-reference");
  await expect(page.locator("#local-pipeline-runs")).toHaveValue("batch-1");
  await page.locator("#local-pipeline-runs").selectOption("batch-2");
  await expect(page.locator("#local-pipeline-batch-name")).toHaveValue("Named batch-2");
  const lateResponse = page.waitForResponse((response) => new URL(response.url()).pathname.endsWith("/runs/batch-1"));
  release();
  await lateResponse;
  const snapshot = await capture(page);
  expect(snapshot.selections.run).toMatchObject({ state: "selected", id: "batch-2" });
  await expect(page.locator("#local-pipeline-batch-name")).toHaveValue("Named batch-2");
});

test("Batches capture retains row identifiers while a refresh is loading", async ({ page }) => {
  await page.route("**/api/tasks/config", (route) => route.fulfill({ json: config }));
  const batch = { ...run(), pipeline: "costume-dressing", pipeline_label: "Costume-Dressing" };
  let count = 0;
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  await page.route("**/api/local/batch-status", async (route) => {
    if (++count > 1) await gate;
    await route.fulfill({ json: { groups: [{ label: "Review", batches: [batch] }] } });
  });
  await page.goto("/?page=local-batch-status");
  await expect(page.locator('[data-run-id="batch-1"]')).toBeVisible();
  await page.locator("#local-batch-status-refresh").click();
  await expect(page.locator("#local-batch-status-refresh")).toBeDisabled();
  await page.locator('[data-run-id="batch-1"]').getByRole("button", { name: "Create task" }).click();
  const snapshot = JSON.parse(await page.locator("#task-capture-context").textContent());
  expect(snapshot.selections.run).toMatchObject({ state: "loading", id: "batch-1" });
  expect(snapshot.selections.character).toMatchObject({ state: "loading", id: "Test" });
  expect(snapshot.selections.costume).toMatchObject({ state: "loading", id: "Travel" });
  release();
});
