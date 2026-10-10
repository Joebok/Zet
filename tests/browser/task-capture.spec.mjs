import { expect, test } from "@playwright/test";

const metadata = { configured: true, project_id: "project-aaaaaaaa", board_url: "http://127.0.0.1:8000/",
  report_context_version: 1, zet_revision: "a".repeat(40) };
const receipt = { task_id: "task-aaaaaaaa", board_url: "http://127.0.0.1:8000/?task_id=task-aaaaaaaa", created: true };

async function setup(page, pageName = "onboarding") {
  await page.route("**/api/tasks/config", (route) => route.fulfill({ json: metadata }));
  await page.goto(`/?page=${pageName}`);
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await expect(page.locator(`#${pageName}-page`)).toHaveClass(/active/);
  await page.locator("#toolbar-create-task").click();
  await expect(page.locator("#task-capture-submit")).toBeEnabled();
}

async function context(page) {
  return JSON.parse(await page.locator("#task-capture-context").textContent());
}

test("task capture sends only explicit page context and links the created ticket", async ({ page }) => {
  let report;
  await page.route("**/api/tasks", (route) => {
    report = route.request().postDataJSON();
    return route.fulfill({ status: 201, json: receipt });
  });
  await setup(page);
  const snapshot = await context(page);
  expect(snapshot).toMatchObject({ version: 1, page_id: "onboarding", universe_id: "Moonsea",
    zet_revision: "a".repeat(40), selections: { character: { state: "selected", id: "Test" }, phase: { state: "selected", id: "Adult" } } });
  expect(new URL(snapshot.source_url).searchParams.get("page")).toBe("onboarding");
  expect(Object.keys(snapshot.selections).sort()).toEqual(["character", "phase"]);
  await page.locator("#task-capture-title").fill("Wrong preview");
  await page.locator("#task-capture-description").fill("Preview did not update.");
  await page.locator("#task-capture-expected").fill("Show new preview");
  await page.locator("#task-capture-submit").click();
  await expect(page.locator("#task-capture-ticket")).toHaveAttribute("href", receipt.board_url);
  expect(report.context).toEqual(snapshot);
  expect(report).toMatchObject({ title: "Wrong preview", project_id: metadata.project_id, expected_behavior: "Show new preview" });
  expect(await page.evaluate(() => localStorage.getItem("zet.task-draft.v1"))).toBeNull();
  await expect(page.locator("#toolbar-open-board")).toHaveAttribute("href", metadata.board_url);
});

test("selection changes and navigation do not silently replace a frozen draft", async ({ page }) => {
  await setup(page);
  const original = await context(page);
  await page.locator("#task-capture-title").fill("Frozen report");
  await page.locator("#task-capture-close").click();
  await page.evaluate(() => window.activatePage("help", { skipAutosave: true }));
  await page.locator("#toolbar-create-task").click();
  expect(await context(page)).toEqual(original);
  await expect(page.locator("#task-capture-title")).toHaveValue("Frozen report");
  await page.locator("#task-capture-refresh").click();
  await expect.poll(async () => (await context(page)).page_id).toBe("help");
  expect((await context(page)).selections).toEqual({});
});

test("failed delivery survives reload and retries the identical body and ID", async ({ page }) => {
  const attempts = [];
  await page.route("**/api/tasks", (route) => {
    attempts.push(route.request().postData());
    return attempts.length === 1
      ? route.fulfill({ status: 504, json: { detail: "Kanban timed out" } })
      : route.fulfill({ status: 200, json: { ...receipt, created: false } });
  });
  await setup(page);
  await page.locator("#task-capture-title").fill("Retry safely");
  await page.locator("#task-capture-submit").click();
  await expect(page.locator("#task-capture-status")).toContainText("Draft retained");
  await expect(page.locator("#task-capture-title")).toBeDisabled();
  await expect(page.locator("#task-capture-refresh")).toBeDisabled();
  await page.reload();
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.locator("#toolbar-create-task").click();
  await expect(page.locator("#task-capture-submit")).toHaveText("Retry submission");
  await page.locator("#task-capture-submit").click();
  await expect(page.locator("#task-capture-ticket")).toBeVisible();
  expect(attempts).toHaveLength(2);
  expect(attempts[1]).toBe(attempts[0]);
});

test("unsent edits survive reload and non-bug reports omit bug detail contents", async ({ page }) => {
  let report;
  await page.route("**/api/tasks", (route) => {
    report = route.request().postDataJSON();
    return route.fulfill({ status: 201, json: receipt });
  });
  await setup(page);
  const original = await context(page);
  await page.locator("#task-capture-title").fill("Add a shortcut");
  await page.locator("#task-capture-expected").fill("Bug-only text");
  await page.locator("#task-capture-type").selectOption("feature");
  await expect(page.locator("#task-capture-bug-details")).toBeHidden();
  await page.reload();
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.locator("#toolbar-create-task").click();
  await expect(page.locator("#task-capture-title")).toHaveValue("Add a shortcut");
  expect(await context(page)).toEqual(original);
  await page.locator("#task-capture-submit").click();
  await expect(page.locator("#task-capture-ticket")).toBeVisible();
  expect(report.type).toBe("feature");
  expect(report.expected_behavior).toBe("");
});

test("an in-flight submission has one writer and leaves uncertain delivery retryable", async ({ page }) => {
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  let count = 0;
  await page.route("**/api/tasks", async (route) => {
    count++;
    await gate;
    await route.fulfill({ status: 409, json: { detail: "Project mapping changed" } });
  });
  await setup(page);
  await page.locator("#task-capture-title").fill("One writer");
  await page.locator("#task-capture-submit").click();
  await expect(page.locator("#task-capture-submit")).toBeDisabled();
  await expect(page.locator("#task-capture-new")).toBeDisabled();
  release();
  await expect(page.locator("#task-capture-status")).toContainText("Project mapping changed");
  expect(count).toBe(1);
});

test("malformed success receipt retains the report rather than claiming success", async ({ page }) => {
  await page.route("**/api/tasks", (route) => route.fulfill({ status: 201,
    json: { ...receipt, board_url: "https://other.example/" } }));
  await setup(page);
  await page.locator("#task-capture-title").fill("Bad receipt");
  await page.locator("#task-capture-submit").click();
  await expect(page.locator("#task-capture-status")).toContainText("Invalid task receipt");
  await expect(page.locator("#task-capture-ticket")).toBeHidden();
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("zet.task-draft.v1")).delivery.title)).toBe("Bad receipt");
});

test("an unconfigured board preserves intake as a local draft", async ({ page }) => {
  await page.route("**/api/tasks/config", (route) => route.fulfill({ json: { ...metadata, configured: false, project_id: null } }));
  await page.goto("/?page=onboarding");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.locator("#toolbar-create-task").click();
  await expect(page.locator("#task-capture-status")).toContainText("Kanban.ProjectID");
  await expect(page.locator("#task-capture-submit")).toBeDisabled();
  await page.locator("#task-capture-title").fill("Set up the board later");
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("zet.task-draft.v1")).report.title)).toBe("Set up the board later");
});

test("context-free pages exclude stale character selections and arbitrary URL fields", async ({ page }) => {
  await setup(page, "help");
  await page.evaluate(() => history.replaceState({}, "", "/?page=help&secret=not-for-report#sensitive"));
  await page.locator("#task-capture-refresh").click();
  const snapshot = await context(page);
  expect(snapshot.page_id).toBe("help");
  expect(snapshot.selections).toEqual({});
  expect(snapshot.source_url).not.toContain("secret");
  expect(snapshot.source_url).not.toContain("sensitive");
});

test("task capture fits a narrow screen and shows readable context", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await setup(page);
  await expect(page.locator("#task-capture-context")).toContainText("onboarding");
  const fits = await page.locator("#task-capture-dialog").evaluate((node) => {
    const rect = node.getBoundingClientRect();
    return rect.left >= 0 && rect.right <= innerWidth && node.scrollWidth <= node.clientWidth;
  });
  expect(fits).toBe(true);
  await page.screenshot({ path: "test-results/task-capture-mobile.png" });
});

test("opening freezes context before delayed configuration resolves", async ({ page }) => {
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  await page.route("**/api/tasks/config", async (route) => {
    await gate;
    await route.fulfill({ json: metadata });
  });
  await page.goto("/?page=onboarding");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.locator("#toolbar-create-task").click();
  const original = await context(page);
  await expect(page.locator("#task-capture-submit")).toBeDisabled();
  await page.evaluate(() => window.activatePage("help", { skipAutosave: true }));
  release();
  await expect(page.locator("#task-capture-submit")).toBeEnabled();
  expect(await context(page)).toEqual({ ...original, zet_revision: metadata.zet_revision });
});

test("main context distinguishes absent, loading, and unavailable selections", async ({ page }) => {
  await setup(page);
  await page.evaluate(() => { state.character = "Deleted character"; state.phase = null; });
  await page.locator("#task-capture-refresh").click();
  let snapshot = await context(page);
  expect(snapshot.selections.character.state).toBe("unavailable");
  expect(snapshot.selections.character.id).toBe("Deleted character");
  expect(snapshot.selections.character.label).toBe("Deleted character");
  expect(snapshot.selections.phase).toEqual({ state: "absent" });
  await page.evaluate(() => { state.character = null; document.body.dataset.dashboardReady = "false"; });
  await page.locator("#task-capture-refresh").click();
  snapshot = await context(page);
  expect(snapshot.selections.character).toEqual({ state: "loading" });
  expect(snapshot.selections.phase).toEqual({ state: "loading" });
});

test("explicit discard after uncertain delivery creates a fresh request ID", async ({ page }) => {
  await page.route("**/api/tasks", (route) => route.fulfill({ status: 503, json: { detail: "Unavailable" } }));
  await setup(page);
  await page.locator("#task-capture-title").fill("Original report");
  await page.locator("#task-capture-submit").click();
  await expect(page.locator("#task-capture-status")).toContainText("Draft retained");
  const oldId = await page.evaluate(() => JSON.parse(localStorage.getItem("zet.task-draft.v1")).report.request_id);
  page.once("dialog", async (dialog) => {
    expect(dialog.message()).toContain("duplicate");
    await dialog.accept();
  });
  await page.locator("#task-capture-new").click();
  await expect(page.locator("#task-capture-title")).toBeEnabled();
  const newId = await page.evaluate(() => JSON.parse(localStorage.getItem("zet.task-draft.v1")).report.request_id);
  expect(newId).not.toBe(oldId);
});
