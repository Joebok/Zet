import { expect, test } from "@playwright/test";
import { mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import { resultsRoot } from "./results-path.mjs";

test.afterEach(async ({ page }, testInfo) => {
  if (testInfo.status !== testInfo.expectedStatus) {
    await page.request.post("/__test/retain-failure", { data: { title: testInfo.title } });
  } else {
    expect(page.__zetPageErrors ?? [], "uncaught browser exceptions").toEqual([]);
  }
});

test("Costume Wizard privately tests a published Assembly FRONT before accepting", async ({ page }) => {
  const reset = await page.request.post("/__test/reset");
  expect(reset.ok()).toBeTruthy();
  const context = await (await page.request.get("/__test/context")).json();
  const queue = context.queue;
  const fixtureImage = path.join(resultsRoot, "narrative-e2e", "fast", "render-1344x768.png");
  const sessionRoot = path.join(context.library, "Test", "_state", "CostumeWizard");
  const seenAsks = new Set();
  let sessionId = "";
  let assemblyCandidateId = "";
  let costumePath = "";
  let completed = false;
  page.on("pageerror", error => {
    page.__zetPageErrors ??= [];
    page.__zetPageErrors.push(error.message);
  });

  try {
    const assembly = await renderAndPublishAssembly(page, queue, fixtureImage);
    assemblyCandidateId = assembly.candidate_id;
    const ordinaryDressingBefore = await getDressingContainer(page, "Test_Travel_Outfit");

    await page.goto("/");
    await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
    await page.getByRole("button", { name: "Character Development" }).click();
    const sections = page.locator("#responsive-section-menu");
    if (await sections.isVisible()) await sections.selectOption("costumes");
    else await page.getByRole("button", { name: "Costumes", exact: true }).click();
    await page.locator("#costume-wizard-open").click();
    const dialog = page.locator("#costume-wizard-dialog");
    await expect(dialog).toBeVisible();
    await page.locator("#costume-wizard-name").fill("E2E Cloaked Traveler");
    await page.locator("#costume-wizard-extra").fill("A fitted blue travel coat with a brass clasp, charcoal trousers, and brown ankle boots.");
    const reference = page.locator(".costume-wizard-image-slot[data-slot=\"1\"]");
    await reference.locator(".costume-wizard-file").setInputFiles(path.join(context.library, "Test", "images", "traveler-reference.png"));
    await reference.locator(".costume-wizard-caption").fill("Full-body view for the coat silhouette and layering.");
    const createdResponse = page.waitForResponse(response => response.request().method() === "POST" &&
      response.url().includes("/api/costume-wizard?"));
    await page.locator("#costume-wizard-create").click();
    const created = await (await createdResponse).json();
    sessionId = created.session.session_id;
    expect(created.session.character).toBe("Traveler");
    expect(created.session.phase).toBe("Adult");
    expect(created.session.images[0].caption).toContain("coat silhouette");

    const sectionsToAnswer = [
      ["overview", ["A fitted blue travel coat layers over charcoal trousers in a restrained palette.", "A brass clasp marks the coat front."]],
      ["upper", ["The coat has a high collar, long sleeves, and a fitted waist with a brass front closure."]],
      ["lower", ["The charcoal trousers have a straight cut.", "Footwear: Brown ankle boots with flat soles."]],
      ["equipment", ["Equipment: A small leather satchel hangs from the wearer's right hip."]],
    ];
    for (const [section, facts] of sectionsToAnswer) {
      const ask = await waitForAsk(queue, { task_type: "costume_wizard", llm_role: "costume_observation" }, seenAsks);
      await deliverEnvelope(queue, ask, JSON.stringify({ facts }));
      await expect.poll(async () => {
        const detail = await getWizardSession(page, sessionId);
        return detail.sections?.[section]?.status;
      }).toBe("READY");
    }
    let wizard = await getWizardSession(page, sessionId);
    expect(wizard.status).toBe("DRAFT_READY");
    expect(wizard.validation_errors).toEqual([]);
    expect(wizard.markdown).toContain("E2E Cloaked Traveler");
    expect(wizard.markdown).toContain("Footwear: Brown ankle boots");

    await page.locator("#costume-wizard-test").click();
    const renderResponse = await page.waitForResponse(response => response.request().method() === "POST" &&
      response.url().endsWith(`/api/costume-wizard/${sessionId}/render`));
    expect(renderResponse.ok(), await renderResponse.text()).toBeTruthy();
    const renderAsk = await waitForAsk(queue, { task_type: "local_test_render", pipeline: "Local-Costume-Dressing" }, seenAsks);
    await deliverEnvelope(queue, renderAsk, await readFile(fixtureImage));
    const reviewAsk = await waitForAsk(queue, { task_type: "costume_wizard", llm_role: "costume_render_review" }, seenAsks);
    await deliverEnvelope(queue, reviewAsk, JSON.stringify({ review: "Prepared private FRONT review: the blue coat and boots remain clear.", refinements: [] }));
    await expect.poll(async () => (await getWizardSession(page, sessionId)).status).toBe("TEST_READY");
    wizard = await getWizardSession(page, sessionId);
    expect(wizard.test_renders).toHaveLength(1);
    expect(wizard.review).toContain("Prepared private FRONT review");
    const privateImage = await page.request.get(`/api/costume-wizard/${sessionId}/test-image`);
    expect(privateImage.ok()).toBeTruthy();
    const privateBytes = Buffer.from(await privateImage.body());
    expect(createHash("sha256").update(privateBytes).digest("hex")).toBe(
      createHash("sha256").update(await readFile(fixtureImage)).digest("hex"));
    expect((await getDressingContainer(page, "Test_Travel_Outfit")).boards.FRONT.slots)
      .toEqual(ordinaryDressingBefore.boards.FRONT.slots);

    const acceptResponse = page.waitForResponse(response => response.request().method() === "POST" &&
      response.url().endsWith(`/api/costume-wizard/${sessionId}/accept`));
    await page.locator("#costume-wizard-accept").click();
    const accepted = await (await acceptResponse).json();
    expect(accepted.costume.name).toBe("E2E Cloaked Traveler");
    costumePath = accepted.costume.source.source_path;
    expect(accepted.message).toContain("Accepted costume");
    wizard = await getWizardSession(page, sessionId);
    expect(wizard.status).toBe("ACCEPTED");

    await page.goto(`/?page=character-asset-container&pipeline=costume-dressing&character=Traveler&phase=Adult&costume=E2E_Cloaked_Traveler&view=FRONT&universe_id=Test`);
    await expect(page.locator("#character-asset-container-page")).toHaveClass(/active/);
    await expect(page.locator(".zet-candidate-board article")).toHaveCount(8);
    const acceptedBoard = await getDressingContainer(page, "E2E_Cloaked_Traveler");
    expect(acceptedBoard.boards.FRONT.slots.every(id => id === null)).toBe(true);
    completed = true;
  } finally {
    if (completed) {
      if (sessionId) {
        const ownedSession = path.resolve(sessionRoot, sessionId);
        if (ownedSession.startsWith(path.resolve(sessionRoot) + path.sep)) await rm(ownedSession, { recursive: true, force: true });
      }
      if (costumePath) await rm(costumePath, { force: true });
      if (assemblyCandidateId) {
        const detail = await getCharacterContainer(page, "character-assembly", "Adult");
        await characterBoardAction(page, "character-assembly", "Adult", "FRONT", assemblyCandidateId, "unlock", detail.revision);
      }
      const cleaned = await page.request.post("/__test/reset");
      expect(cleaned.ok()).toBeTruthy();
    }
  }
});

async function renderAndPublishAssembly(page, queue, imagePath) {
  let detail = await getCharacterContainer(page, "character-assembly", "Adult");
  const response = await page.request.post("/api/character-containers/character-assembly/views/FRONT/generate?character=Traveler&phase=Adult&universe_id=Test", {
    data: { count: 1, render_mode: "draft", expected_revision: detail.revision },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  detail = await response.json();
  const candidateId = detail.boards.FRONT.slots.find(Boolean);
  let candidate = detail.boards.FRONT.candidates[candidateId];
  await deliverEnvelope(queue, candidate.ask_id, await readFile(imagePath));
  await expect.poll(async () => {
    detail = await getCharacterContainer(page, "character-assembly", "Adult");
    candidate = detail.boards.FRONT.candidates[candidateId];
    return candidate.status;
  }).toBe("COMPLETE");
  detail = await getCharacterContainer(page, "character-assembly", "Adult");
  detail = await characterBoardAction(page, "character-assembly", "Adult", "FRONT", candidateId, "select", detail.revision);
  detail = await characterBoardAction(page, "character-assembly", "Adult", "FRONT", candidateId, "lock", detail.revision);
  candidate = detail.boards.FRONT.candidates[candidateId];
  expect(candidate.locked).toBe(true);
  expect(candidate.inventory_asset_id).toBeTruthy();
  return candidate;
}

async function getCharacterContainer(page, pipeline, phase) {
  const response = await page.request.get(`/api/character-containers/${pipeline}?character=Traveler&phase=${encodeURIComponent(phase)}&universe_id=Test`);
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

async function characterBoardAction(page, pipeline, phase, view, candidateId, action, revision) {
  const response = await page.request.post(`/api/character-containers/${pipeline}/views/${view}/candidates/${candidateId}/${action}?character=Traveler&phase=${encodeURIComponent(phase)}&universe_id=Test`, {
    data: { expected_revision: revision, expected_candidate_id: candidateId },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

async function getWizardSession(page, sessionId) {
  const response = await page.request.get(`/api/costume-wizard/${sessionId}`);
  expect(response.ok(), await response.text()).toBeTruthy();
  return (await response.json()).session;
}

async function getDressingContainer(page, costume) {
  const response = await page.request.get(`/api/character-containers/costume-dressing?character=Traveler&phase=Adult&costume=${encodeURIComponent(costume)}&universe_id=Test`);
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

async function waitForAsk(queue, matches, seen) {
  let found;
  await expect.poll(async () => {
    found = await findAsk(queue, matches, seen);
    return Boolean(found);
  }).toBe(true);
  seen.add(found.id);
  return found;
}

async function findAsk(queue, matches, seen) {
  for (const state of ["Ask", "Running"]) {
    const root = path.join(queue, "File_Proxy", state, "zet");
    let folders = [];
    try { folders = await readdir(root, { withFileTypes: true }); } catch {}
    for (const folder of folders.filter(item => item.isDirectory())) {
      if (seen.has(folder.name) || folder.name.startsWith(".")) continue;
      try {
        const location = path.join(root, folder.name);
        const manifest = JSON.parse(await readFile(path.join(location, "ask_manifest.json"), "utf8"));
        if (Object.entries(matches).every(([key, value]) => manifest[key] === value)) {
          return { id: folder.name, location, manifest };
        }
      } catch {}
    }
  }
  return null;
}

async function deliverEnvelope(queue, ask, output) {
  if (typeof ask === "string") ask = { id: ask };
  const location = ask.location || path.join(queue, "File_Proxy", "Ask", "zet", ask.id);
  const answer = path.join(queue, "File_Proxy", "Answer", "zet", ask.id);
  const manifest = ask.manifest || JSON.parse(await readFile(path.join(location, "ask_manifest.json"), "utf8"));
  if (!Buffer.isBuffer(output)) output = Buffer.from(output, "utf8");
  await mkdir(answer, { recursive: true });
  await writeFile(path.join(answer, "ask_manifest.json"), await readFile(path.join(location, "ask_manifest.json")));
  await writeFile(path.join(answer, "job.json"), await readFile(path.join(location, "job.json")));
  await writeFile(path.join(answer, manifest.expected_output), output);
  await writeFile(path.join(answer, "answer_manifest.json"), JSON.stringify({
    ask_id: ask.id, status: "SUCCESS", expected_output: manifest.expected_output,
    worker_id: "prepared-costume-wizard-test", ollama_attempt_id: manifest.ollama_attempt_id || ask.id,
  }));
  await writeFile(path.join(answer, "proxy_result.json"), JSON.stringify({ status: "SUCCEEDED", output_files: [
    { path: manifest.expected_output, size: output.length, sha256: createHash("sha256").update(output).digest("hex") },
  ] }));
}
