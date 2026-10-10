import { expect, test } from "@playwright/test";

const PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/pXcAAAAASUVORK5CYII=", "base64");

async function inventory(page) {
  await page.goto("/");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.evaluate(() => window.activatePage("auxiliary-resources", { skipAutosave: true }));
  await expect(page.locator("#quick-character-wizard-open")).toBeVisible();
}

async function wizardApi(page, { questions = false, failProfile = false } = {}) {
  let session;
  let intake;
  const requests = [];
  await page.route("**/api/quick-character-wizard**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    if (path.includes("/images/") || path.includes("/references/")) return route.fulfill({ body: PNG, contentType: "image/png" });
    if (path === "/api/quick-character-wizard" && method === "GET") return route.fulfill({ json: { sessions: session && session.status !== "ACCEPTED" ? [session] : [] } });
    const data = method === "GET" ? {} : route.request().postDataJSON();
    requests.push({ path, data });
    if (path === "/api/quick-character-wizard") {
      intake = data;
      const side = data.side.toUpperCase();
      session = { session_id: "0123456789abcdef0123456789abcdef", name: data.name, framing: data.framing, side: data.side,
        status: questions ? "NEEDS_INPUT" : "DRAFT_READY", revision_id: "revision-1", description: "White-haired warrior in brown armor.",
        identity: "White-haired warrior", observations: ["White hair"], proposals: ["Matching rear armor"], proposals_approved: false,
        questions: questions ? ["Which outfit should be used?"] : [], selected: {}, candidates: [], busy: false,
        references: [{ index: 0, caption: data.references[data.primary_index].caption, url: "/api/quick-character-wizard/ref/references/0" }],
        views: ["FRONT", `FRONT_${side}_3_4`, `${side}_PROFILE`], job: { kind: "draft", status: "COMPLETE", error: "" } };
    } else if (path.endsWith("/draft")) {
      session.description = data.description; session.identity = data.identity; session.proposals = data.proposals; session.proposals_approved = data.proposals_approved;
    } else if (path.endsWith("/answers")) {
      session.questions = []; session.status = "DRAFT_READY";
    } else if (path.endsWith("/render") || path.endsWith("/refine")) {
      const failure = failProfile && data.view.endsWith("PROFILE") && !session.candidates.some((c) => c.view === data.view);
      const id = `candidate-${session.candidates.length + 1}`;
      session.candidates.push({ candidate_id: id, view: data.view, revision_id: session.revision_id, stale: false,
        status: failure ? "FAILED" : "READY", error: failure ? "Render failed; retry this view." : "", review: "Identity and angle match.",
        refinements: [], image_url: failure ? "" : `/api/quick-character-wizard/${session.session_id}/images/${id}` });
      session.status = failure ? "FAILED" : "REVIEW_READY";
    } else if (path.endsWith("/select")) {
      const candidate = session.candidates.find((c) => c.candidate_id === data.candidate_id);
      if (candidate.view === "FRONT" && session.selected.FRONT !== candidate.candidate_id) session.selected = {};
      session.selected[candidate.view] = candidate.candidate_id;
      session.status = session.views.every((v) => session.selected[v]) ? "READY_TO_SAVE" : "REVIEW_READY";
    } else if (path.endsWith("/accept")) {
      session.status = "ACCEPTED";
      const ids = Object.fromEntries(session.views.map((v, i) => [v, `saved-${i}`]));
      session.publication = { set_id: "saved-set", asset_ids: ids, tags: Object.fromEntries(session.views.map((v, i) => [v, `{{LIB:ASSET:saved-${i}}}`])) };
    } else if (path.endsWith("/abandon")) session.status = "ABANDONED";
    return route.fulfill({ json: { session } });
  });
  return { intake: () => intake, requests };
}

test("upload intake, front approval, individual retry and three-view save", async ({ page }) => {
  const errors = []; page.on("pageerror", (error) => errors.push(error.message));
  const mock = await wizardApi(page, { failProfile: true });
  await inventory(page);
  await page.locator("#quick-character-wizard-open").click();
  const dialog = page.locator("#quick-character-wizard-dialog");
  await expect(dialog.locator(".qc-reference-slot")).toHaveCount(3);
  await dialog.locator("#qc-name").fill("Freydis");
  await dialog.locator('input[type="file"]').first().setInputFiles({ name: "reference.png", mimeType: "image/png", buffer: PNG });
  await dialog.locator("#qc-create").click();
  await expect(dialog.locator("#qc-message")).toContainText("Describe what each reference conveys");
  await dialog.getByLabel("Reference 1 caption").fill("Identity and clothing");
  await dialog.locator("#qc-create").click();
  await expect(dialog.locator("#qc-description")).toHaveValue("White-haired warrior in brown armor.");
  await dialog.screenshot({ path: "test-results/quick-character-wizard-draft.png" });
  expect(mock.intake().framing).toBe("full_body");
  expect(mock.intake().side).toBe("left");
  const front = dialog.locator('[data-view="FRONT"]');
  const angled = dialog.locator('[data-view="FRONT_LEFT_3_4"]');
  const profile = dialog.locator('[data-view="LEFT_PROFILE"]');
  await expect(angled.getByRole("button", { name: "Generate view", exact: true })).toBeDisabled();
  await dialog.locator("#qc-approved").check();
  await dialog.locator("#qc-save-draft").click();
  await front.getByRole("button", { name: "Generate view", exact: true }).click();
  await front.getByRole("button", { name: "Approve front", exact: true }).click();
  await angled.getByRole("button", { name: "Generate view", exact: true }).click();
  await angled.getByRole("button", { name: "Approve view", exact: true }).click();
  await profile.getByRole("button", { name: "Generate view", exact: true }).click();
  await expect(profile).toContainText("Render failed; retry this view");
  await expect(front).toContainText("Approved");
  await profile.getByRole("button", { name: "Generate another", exact: true }).click();
  await profile.getByRole("button", { name: "Approve view", exact: true }).click();
  await expect(dialog.locator("#qc-message")).not.toContainText("Render failed");
  await expect(dialog.locator("#qc-accept")).toBeEnabled();
  await dialog.locator("#qc-accept").click();
  await expect(dialog.locator("#qc-publication")).toContainText("Three character views saved");
  await expect(dialog.locator("#qc-publication a")).toHaveCount(4);
  expect(mock.requests.filter((r) => r.path.endsWith("/render"))).toHaveLength(4);
  expect(errors).toEqual([]);
});

test("library launch preloads identity, supports portrait/right, questions and resume", async ({ page }) => {
  const mock = await wizardApi(page, { questions: true });
  await inventory(page);
  const imported = await page.request.post("/api/entity-library/assets?label=Wizard+Source", { data: PNG, headers: { "content-type": "image/png" } });
  const asset = (await imported.json()).asset;
  await page.locator("#entity-library-search").fill("Wizard Source");
  await page.locator("#entity-library-refresh").click();
  await page.locator("#entity-library-results .image-catalog-card").filter({ hasText: "Wizard Source" }).getByRole("button", { name: "Details" }).click();
  await page.locator("#quick-character-wizard-from-asset").click();
  const dialog = page.locator("#quick-character-wizard-dialog");
  await expect(dialog.locator("#qc-name")).toHaveValue("Wizard Source");
  await expect(dialog.locator(".qc-reference-slot img").first()).toBeVisible();
  await dialog.locator("#qc-framing").selectOption("portrait");
  await dialog.locator("#qc-side").selectOption("right");
  await dialog.locator("#qc-create").click();
  expect(mock.intake().references[0].asset_id).toBe(asset.asset_id);
  expect(mock.intake().framing).toBe("portrait");
  await dialog.locator("#qc-questions textarea").fill("Brown armor");
  await dialog.locator("#qc-answer").click();
  await expect(dialog.locator("#qc-questions textarea")).toHaveCount(0);
  await dialog.locator("#qc-description").fill("Updated description retained on close.");
  await dialog.locator("#qc-close").click();
  await page.locator("#quick-character-wizard-from-asset").click();
  await dialog.locator("#qc-sessions").selectOption("0123456789abcdef0123456789abcdef");
  await dialog.locator("#qc-resume").click();
  await expect(dialog.locator('[data-view="RIGHT_PROFILE"]')).toBeVisible();
  await expect(dialog.locator("#qc-description")).toHaveValue("Updated description retained on close.");
});

test("library picker and pasted references participate in primary selection", async ({ page }) => {
  const mock = await wizardApi(page);
  await inventory(page);
  const imported = await page.request.post("/api/entity-library/assets?label=Wizard+Picker", { data: PNG, headers: { "content-type": "image/png" } });
  const asset = (await imported.json()).asset;
  await page.locator("#quick-character-wizard-open").click();
  const dialog = page.locator("#quick-character-wizard-dialog");
  await dialog.locator("#qc-name").fill("Picker character");
  await dialog.locator(".qc-reference-slot").first().getByRole("button", { name: "Choose from library" }).click();
  const picker = page.locator("#builder-image-picker-modal");
  await expect(picker).toBeVisible();
  await picker.locator("tr").filter({ hasText: "Wizard Picker" }).click();
  await expect(picker).not.toBeVisible();
  const slot = dialog.locator(".qc-reference-slot").nth(1);
  await slot.locator(".paste-zone").evaluate((element, data) => {
    const bytes = Uint8Array.from(atob(data), (c) => c.charCodeAt(0));
    const transfer = new DataTransfer(); transfer.items.add(new File([bytes], "paste.png", { type: "image/png" }));
    element.dispatchEvent(new ClipboardEvent("paste", { clipboardData: transfer, bubbles: true }));
  }, PNG.toString("base64"));
  await expect(slot.locator("img")).toBeVisible();
  await slot.locator("textarea").fill("Face detail");
  await slot.locator('input[type="radio"]').check();
  await dialog.locator("#qc-create").click();
  await expect(dialog.locator("#qc-description")).toBeVisible();
  expect(mock.intake().references[0].asset_id).toBe(asset.asset_id);
  expect(mock.intake().references[1].image).toMatch(/^data:image\/png/);
  expect(mock.intake().primary_index).toBe(1);
});
