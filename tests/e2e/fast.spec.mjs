import { expect, test } from "@playwright/test";
import { mkdir, readFile, rename, unlink, writeFile } from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import { resultsRoot } from "./results-path.mjs";

const image = (width, height) => path.join(resultsRoot, "narrative-e2e", "fast", `render-${width}x${height}.png`);

test.beforeEach(async ({ page }) => {
  const reset = await page.request.post("/__test/reset");
  expect(reset.ok()).toBeTruthy();
  await page.goto("/narrative");
  await page.waitForFunction(() => document.body.dataset.narrativeReady === "true");
});

test.afterEach(async ({ page }, testInfo) => {
  if (testInfo.status !== testInfo.expectedStatus) {
    await page.request.post("/__test/retain-failure", { data: { title: testInfo.title } });
  }
});

test("library and narrative authoring save and reload through the dashboard", async ({ page }) => {
  const context = await (await page.request.get("/__test/context")).json();
  await page.goto("/");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.getByRole("button", { name: "Character Development" }).click();
  await expect(page.locator("#workspace-character")).toHaveAttribute("aria-pressed", "true");
  const sections = page.locator("#responsive-section-menu");
  if (await sections.isVisible()) await sections.selectOption("onboarding");
  else {
    await page.locator("#local-assets-button").click();
    await page.getByRole("button", { name: "Character Overview", exact: true }).click();
  }
  await page.locator("#character-setup-details > summary").click();
  const character = page.locator("#onboarding-character");
  const phase = page.locator("#onboarding-phase");
  await expect(character).toHaveValue("Traveler");
  await expect(phase).toHaveValue("Adult");
  const characterPath = path.join(context.library, "Test", "Characters", "Traveler", "Adult", "Character.md");
  const originalCharacter = await readFile(characterPath, "utf8");
  const backupCharacterPath = `${characterPath}.e2e-backup`;
  await rename(characterPath, backupCharacterPath);
  await page.reload();
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  const editedCharacter = originalCharacter.replace("Canonical Art Style: `Simple graphic illustration`", "Canonical Art Style: `Warm watercolor illustration`");
  await page.locator("#onboarding-template-file").setInputFiles({ name: "Character.md", mimeType: "text/markdown", buffer: Buffer.from(editedCharacter) });
  await page.getByRole("button", { name: "Upload Template" }).click();
  await expect.poll(async () => readFile(path.join(context.library, "Test", "Characters", "Traveler", "Adult", "Character.md"), "utf8"))
    .toContain("Warm watercolor illustration");
  // Restore the valid fixture directly after exercising the incomplete-phase upload.
  await writeFile(characterPath, originalCharacter, "utf8");
  await unlink(backupCharacterPath);

  if (await sections.isVisible()) {
    await expect(sections.locator('option[value="costumes"]')).toBeEnabled();
    await sections.selectOption("costumes");
  } else {
    await expect(page.getByRole("button", { name: "Costumes", exact: true })).toBeEnabled();
    await page.getByRole("button", { name: "Costumes", exact: true }).click();
  }
  const costumeRow = page.getByRole("row").filter({ hasText: "Test Travel Outfit" });
  await costumeRow.click();
  await page.locator("#costume-name").fill("Test Travel Outfit Edited");
  await page.getByRole("button", { name: "Update Costume" }).click();
  await expect(page.locator("#costume-table")).toContainText("Test Travel Outfit Edited");
  await page.locator("#costume-name").fill("Test Travel Outfit");
  await page.getByRole("button", { name: "Update Costume" }).click();
  await expect(page.locator("#costume-table")).toContainText("Test Travel Outfit");

  await page.goto(`/narrative?story=${context.ids.story}`);
  await page.waitForFunction(() => document.body.dataset.narrativeReady === "true");
  await page.locator("#narrative-title").fill("The Rewritten Test Journey");
  await page.getByRole("button", { name: "Save story" }).click();
  await page.goto(`/narrative?story=${context.ids.story}&scene=${context.ids.scene}`);
  await page.waitForFunction(() => document.body.dataset.narrativeReady === "true");
  await page.locator("#narrative-setting").fill("A pine forest beside the test road");
  await page.getByRole("button", { name: "Save scene" }).click();
  await page.getByRole("button", { name: "Edit", exact: true }).click();
  await page.getByLabel("Appearance notes").fill("Blue travel coat, dark trousers, brown boots.");
  await page.getByRole("button", { name: "Save element" }).click();
  await page.goto(`/narrative?story=${context.ids.story}`);
  await page.waitForFunction(() => document.body.dataset.narrativeReady === "true");
  await expect(page.locator("#narrative-title")).toHaveValue("The Rewritten Test Journey");
  await page.goto(`/narrative?story=${context.ids.story}&scene=${context.ids.scene}`);
  await page.waitForFunction(() => document.body.dataset.narrativeReady === "true");
  await expect(page.locator("#narrative-setting")).toHaveValue("A pine forest beside the test road");
  await expect(page.locator("#narrative-elements img").first()).toBeVisible();
  await expect(page.locator("#narrative-elements img").first()).toHaveJSProperty("naturalWidth", 256);
  expect(context.ids.story).toMatch(/^[a-f0-9]{32}$/);
  const library = path.join(context.library, "Test", "Characters", "Traveler", "Adult");
  expect(await readFile(path.join(library, "Character.md"), "utf8")).toContain("Traveler");
  expect(await readFile(path.join(library, "Costume_Test_Travel_Outfit.md"), "utf8")).toContain("brown boots");
});

test("narrative interview, prompt, render, retry, and final assembly persist", async ({ page }) => {
  const context = await (await page.request.get("/__test/context")).json();
  const ids = context.ids;
  const scene = `/api/narrative/stories/${ids.story}/scenes/${ids.scene}`;
  const targets = [ids.backdrop, ids.subscene];
  const details = await Promise.all(targets.map(async target =>
    (await page.request.get(`${scene}/targets/${target}`)).json()));

  await page.goto(`/narrative?story=${ids.story}&scene=${ids.scene}&target=${ids.subscene}`);
  await page.locator("#narrative-direction").fill("Show the traveler reaching the forest gate.");
  await page.getByRole("button", { name: "Continue interview" }).click();
  await answerJob(page, scene, ids.subscene, "interview", {
    proposals: Object.entries({narrative: "The traveler reaches a forest gate.", staging: "Standing beside the gate.",
      physical_context: "Pine forest.", framing: "Full body."}).map(([field,text]) =>
      ({scope:"moment", field, element_id:"", text, reason:"Describe the arrival."})),
    conflicts: [], questions: [],
  });
  await expect(page.locator("#narrative-narrative")).toHaveValue(details[1].narrative);
  await page.getByRole("button", { name: "Apply", exact: true }).click();
  await expect(page.locator("#narrative-narrative")).toHaveValue("The traveler reaches a forest gate.");
  const writePromptButtons = page.locator('button[data-action="synthesize"]');
  await expect(writePromptButtons).toHaveCount(2);
  expect(await writePromptButtons.evaluateAll(buttons => buttons.every(button => button.dataset.action === "synthesize"))).toBeTruthy();
  await page.locator('button[data-action="synthesize"]').first().click();
  await answerJob(page, scene, ids.subscene, "synthesize", { scene: "A traveler reaches a forest gate.", rendering: "Soft daylight." });

  for (const [index, targetId] of targets.entries()) {
    await page.goto(`/narrative?story=${ids.story}&scene=${ids.scene}&target=${targetId}`);
    if (index === 0) {
      await page.locator("#narrative-prompt").fill("A quiet forest path, soft daylight.");
      await page.getByRole("button", { name: "Save inputs" }).click();
      await page.getByRole("button", { name: "Draft 1" }).click();
      await answerRender(page, scene, targetId, image(1184, 896));
    } else {
      await page.locator("#narrative-prompt").fill("The traveler reaches the forest gate.");
      await page.getByRole("button", { name: "Save inputs" }).click();
      await page.getByRole("button", { name: "Draft 1" }).click();
      await answerRender(page, scene, targetId, null, true);
      await expect(page.locator(".narrative-slot").first()).toContainText("failed");
      await page.locator(".narrative-slot").first().getByRole("button", { name: "Retry" }).click();
      await answerRender(page, scene, targetId, image(1184, 896));
    }
    await page.locator(".narrative-slot").first().getByRole("button", { name: "Select" }).click();
    await page.locator(".narrative-slot").first().getByRole("button", { name: "Lock" }).click();
  }

  await page.goto(`/narrative?story=${ids.story}&scene=${ids.scene}`);
  const assembly = ids.assembly;
  expect(assembly).toMatch(/^[a-f0-9]{32}$/);
  await page.goto(`/narrative?story=${ids.story}&scene=${ids.scene}&target=${assembly}`);
  await page.getByRole("button", { name: "Add selected image" }).click();
  await page.locator("#assembly-source").selectOption(ids.subscene);
  await page.getByRole("button", { name: "Add selected image" }).click();
  await page.getByRole("button", { name: "Write Prompt" }).click();
  await answerJob(page, scene, assembly, "synthesize", { scene: "Blend the placed scene into a finished illustration.", rendering: "Keep the subjects and setting unchanged." });
  const renderReply = page.waitForResponse(response => response.request().method() === "POST" && response.url().includes(`/targets/${assembly}/jobs`));
  await page.getByRole("button", { name: "Draft 1" }).click();
  const renderResponse = await renderReply;
  expect(renderResponse.ok(), await renderResponse.text()).toBeTruthy();
  await answerRender(page, scene, assembly, image(1184, 896));
  await page.locator(".narrative-slot").first().getByRole("button", { name: "Select" }).click();
  await page.locator(".narrative-slot").first().getByRole("button", { name: "Lock" }).click();
  await page.reload();
  await expect(page.locator(".narrative-slot").first()).toContainText("Locked");
  const story = (await (await page.request.get("/api/narrative/stories?universe_id=Test")).json()).find(item => item.id === ids.story);
  expect(story.scenes[0].final_assembly?.target_id).toBe(assembly);
  const candidate = (await (await page.request.get(`${scene}/targets/${assembly}?universe_id=Test`)).json()).selected_id;
  const publishedImage = await page.request.get(`${scene}/targets/${assembly}/candidates/${candidate}/image?universe_id=Test`);
  expect(publishedImage.ok()).toBeTruthy();
  await page.goto("/narrative");
  await page.waitForFunction(() => document.body.dataset.narrativeReady === "true");
  await expect(page.locator(".narrative-story-scene img")).toHaveCount(1);
  await expect(page.locator(".narrative-story-scene img")).toHaveJSProperty("naturalWidth", 1184);
  expect(details[1].kind).toBe("subscene");
});

test("character-to-costume workflow uses manual container boards and publishes outputs", async ({ page }) => {
  const context = await (await page.request.get("/__test/context")).json();
  const root = "/?page=character-asset-container&character=Traveler&phase=Adult&universe_id=Test";
  await page.goto(root + "&pipeline=character-assembly");
  await page.getByRole("link", {name: "Open FRONT Candidate Board", exact: true}).click();
  const draft = await generateCharacterImage(page, "character-assembly", "", "draft", 1, image(1344, 768));
  const final = await generateCharacterImage(page, "character-assembly", "", "final", 2, image(1216, 832));
  expect(draft.candidate_id).not.toBe(final.candidate_id);

  await page.getByRole("button", {name: "Review slot 1"}).click();
  const review = page.getByRole("dialog", {name: "Review candidate"});
  await expect(review).toContainText("1 of 2 · Draft");
  await review.getByRole("button", {name: "Next candidate"}).click();
  await expect(review).toContainText("2 of 2 · Final");
  await review.locator("summary").first().click();
  const references = review.locator("ol a");
  await expect(references).toHaveText(["body_reference", "head_image"]);
  expect((await page.request.get(await references.first().getAttribute("href"))).ok()).toBeTruthy();
  await expect(review.locator("pre").first()).toHaveText(final.prompt);
  await review.getByRole("button", {name: "Select", exact: true}).click();
  await expect(review).toContainText("Selected");
  await review.getByRole("button", {name: "Lock", exact: true}).click();
  await expect(review).toContainText("Locked and published");
  const assembly = (await characterBoard(page, "character-assembly")).boards.FRONT;
  const locked = assembly.candidates[final.candidate_id];
  const inventory = await page.request.get(`/api/entity-library/assets/${locked.inventory_asset_id}?universe_id=Test`);
  expect(inventory.ok()).toBeTruthy();
  expect((await inventory.json()).asset.status).toBe("approved");

  await page.goto(root + "&pipeline=costume-dressing");
  await page.locator("#character-container-costume").selectOption("Test_Travel_Outfit");
  await page.getByRole("link", {name: "Open FRONT Candidate Board", exact: true}).click();
  const dressing = await generateCharacterImage(page, "costume-dressing", "Test_Travel_Outfit", "draft", 1, image(1344, 768));
  expect(dressing.render_request.inputs.map(input => input.role)).toEqual(["character_assembly"]);
  expect(dressing.render_request.inputs[0].candidate_id).toBe(locked.candidate_id);
  expect(dressing.render_request.inputs[0].sha256).toBe(locked.image_sha256);
  expect(dressing.render_request.provenance.costume).toBe("Test_Travel_Outfit");
  await page.getByRole("button", {name: "Review slot 1"}).click();
  await review.getByRole("button", {name: "Lock", exact: true}).click();
  await expect(review).toContainText("Locked and published");

  const costume = await page.request.get("/api/costumes?character=Traveler&phase=Adult&universe_id=Test");
  expect(costume.ok()).toBeTruthy();
  expect((await costume.json()).costumes.map(item => item.name)).toContain("Test Travel Outfit");
  expect((await page.request.get("/api/local/character-assembly/runs?universe_id=Test")).status()).toBe(404);
  expect((await page.request.get("/api/local/batch-status?universe_id=Test")).status()).toBe(404);
  expect((await page.request.get("/api/local/character-overview/Traveler/Adult/Test_Travel_Outfit/autogenerate?universe_id=Test")).status()).toBe(404);

  await page.goto("/?page=character-asset-container&pipeline=costume-dressing&costume=Test%20Travel%20Outfit&view=FRONT&character=Traveler&phase=Adult&universe_id=Test");
  await expect(page.locator("#character-asset-container-page")).toHaveClass(/active/);
  await expect(page.locator("#character-container-board")).toContainText("Locked");
  await expect(page.locator("#character-container-board article").first().locator("img")).toBeVisible();
  await expect(page.locator("#toolbar-batches")).toHaveCount(0);
  await expect(page.locator("#local-operations-button")).toHaveCount(0);
  expect(context.ids.story).toMatch(/^[a-f0-9]{32}$/);
});

async function answerJob(page, scene, target, kind, output) {
  await expect.poll(async () => {
    const detail = await (await page.request.get(`${scene}/targets/${target}?universe_id=Test`)).json();
    return Object.values(detail.jobs).filter(job => job.kind === kind).at(-1)?.status;
  }).toBe("QUEUED");
  const detail = await (await page.request.get(`${scene}/targets/${target}?universe_id=Test`)).json();
  const job = Object.values(detail.jobs).filter(item => item.kind === kind).at(-1);
  await deliverEnvelope(page, job.id, output);
  await expect.poll(async () => {
    const updated = await (await page.request.get(`${scene}/targets/${target}?universe_id=Test`)).json();
    return updated.jobs[job.id]?.status;
  }).toBe("COMPLETE");
}

async function answerRender(page, scene, target, imagePath, failed = false) {
  await expect.poll(async () => {
    const detail = await (await page.request.get(`${scene}/targets/${target}?universe_id=Test`)).json();
    return Object.values(detail.jobs).filter(job => job.kind === "image").at(-1)?.status;
  }).toBe("QUEUED");
  const detail = await (await page.request.get(`${scene}/targets/${target}?universe_id=Test`)).json();
  const job = Object.values(detail.jobs).filter(item => item.kind === "image").at(-1);
  await deliverEnvelope(page, job.id, failed ? null : await readFile(imagePath), failed);
  await expect.poll(async () => {
    const updated = await (await page.request.get(`${scene}/targets/${target}?universe_id=Test`)).json();
    return updated.jobs[job.id]?.status;
  }).toBe(failed ? "FAILED" : "COMPLETE");
}

async function deliverEnvelope(page, id, output, failed = false) {
  const context = await (await page.request.get("/__test/context")).json();
  const ask = path.join(context.queue, "File_Proxy", "Ask", "zet", id);
  const answer = path.join(context.queue, "File_Proxy", "Answer", "zet", id);
  const manifest = JSON.parse(await readFile(path.join(ask, "ask_manifest.json"), "utf8"));
  if (output && !Buffer.isBuffer(output)) output = Buffer.from(JSON.stringify(output));
  await mkdir(answer, { recursive: true });
  // Keep the immutable request bytes, including 64-bit seeds, intact.
  await writeFile(path.join(answer, "ask_manifest.json"), await readFile(path.join(ask, "ask_manifest.json")));
  await writeFile(path.join(answer, "job.json"), await readFile(path.join(ask, "job.json")));
  if (output) await writeFile(path.join(answer, manifest.expected_output), output);
  const outputFiles = output ? [{ path: manifest.expected_output, size: output.length, sha256: createHash("sha256").update(output).digest("hex") }] : [];
  await writeFile(path.join(answer, "answer_manifest.json"), JSON.stringify({
    ask_id: id, status: failed ? "ERROR" : "SUCCESS", expected_output: manifest.expected_output,
    error_message: failed ? "Prepared render failure" : "", worker_id: "local-test-worker", ollama_attempt_id: id,
  }));
  await writeFile(path.join(answer, "proxy_result.json"), JSON.stringify({ status: failed ? "FAILED" : "SUCCEEDED", output_files: outputFiles }));
  await writeFile(path.join(answer, "harvest_manifest.json"), JSON.stringify({ status: "HARVESTED_FOR_EXTERNAL_CONSUMER" }));
}

async function characterBoard(page, pipeline, costume = "") {
  const params = new URLSearchParams({character: "Traveler", phase: "Adult", universe_id: "Test"});
  if (costume) params.set("costume", costume);
  const result = await page.request.get(`/api/character-containers/${pipeline}?${params}`);
  expect(result.ok()).toBeTruthy();
  return result.json();
}

async function generateCharacterImage(page, pipeline, costume, quality, slot, pngPath) {
  const context = await (await page.request.get("/__test/context")).json();
  await expect(page.locator("#character-container-board article")).toHaveCount(8);
  const label = quality === "draft" ? "Draft 1" : "Final 1";
  await page.getByRole("button", {name: label, exact: true}).click();
  let candidate;
  await expect.poll(async () => {
    const board = (await characterBoard(page, pipeline, costume)).boards.FRONT;
    candidate = board.candidates[board.slots[slot - 1]];
    return candidate?.status;
  }).toBe("QUEUED");
  expect(candidate.render_mode).toBe(quality);
  await answerLocalEnvelope(context.queue, candidate.ask_id, await readFile(pngPath));
  const card = page.locator("#character-container-board article").nth(slot - 1);
  await expect(card.locator("img")).toBeVisible();
  await expect(card).toContainText(quality === "draft" ? "Draft" : "Final");
  return candidate;
}

async function answerLocalEnvelope(queue, id, output) {
  const ask = path.join(queue, "File_Proxy", "Ask", "zet", id);
  const answer = path.join(queue, "File_Proxy", "Answer", "zet", id);
  const manifest = JSON.parse(await readFile(path.join(ask, "ask_manifest.json"), "utf8"));
  await mkdir(answer, { recursive: true });
  await writeFile(path.join(answer, "ask_manifest.json"), await readFile(path.join(ask, "ask_manifest.json")));
  await writeFile(path.join(answer, "job.json"), await readFile(path.join(ask, "job.json")));
  await writeFile(path.join(answer, manifest.expected_output), output);
  await writeFile(path.join(answer, "answer_manifest.json"), JSON.stringify({
    ask_id: id, status: "SUCCESS", expected_output: manifest.expected_output,
    worker_id: "local-test-worker", ollama_attempt_id: manifest.ollama_attempt_id || id,
  }));
  await writeFile(path.join(answer, "proxy_result.json"), JSON.stringify({ status: "SUCCEEDED", output_files: [
    { path: manifest.expected_output, size: output.length, sha256: createHash("sha256").update(output).digest("hex") },
  ] }));
}


test("unified AI queue collects all universes in the background and shares model selection", async ({ page }) => {
  const context = await (await page.request.get("/__test/context")).json();
  const submit = async (universe, model) => {
    const response = await page.request.post("/__test/ai-submit", { data: { universe, model } });
    expect(response.ok(), await response.text()).toBeTruthy();
    return (await response.json()).ask_id;
  };
  const first = await submit("Test", "codex:gpt-6-luna");
  const second = await submit("TestOther", "general:latest");
  await page.goto("/?page=ai-controls");
  await expect(page.locator(`#ai-jobs-table tr[data-job-id="${first}"]`)).toContainText("QUEUED");
  await expect(page.locator(`#ai-jobs-table tr[data-job-id="${second}"]`)).toContainText("TestOther");
  await page.goto("/?page=auxiliary-resources");
  await deliverEnvelope(page, first, Buffer.from(JSON.stringify({ summary: "Cloud prepared answer" })));
  await deliverEnvelope(page, second, Buffer.from(JSON.stringify({ summary: "Local prepared answer" })));
  await expect.poll(async () => {
    const payload = await (await page.request.get("/api/ai/jobs")).json();
    return [first, second].every(id => payload.items.some(item => item.ask_id === id && item.status === "COMPLETE"));
  }, { timeout: 12000 }).toBe(true);
  await page.goto("/?page=ai-controls");
  await expect(page.locator(`#ai-jobs-table tr[data-job-id="${first}"]`)).toContainText("COMPLETE");
  await expect(page.locator("#recent-harvest-table")).toContainText(first);
  await page.reload();
  await expect(page.locator(`#ai-jobs-table tr[data-job-id="${second}"]`)).toContainText("COMPLETE");
  await page.locator("#ai-filter-universe").selectOption("TestOther");
  await expect(page.locator(`#ai-jobs-table tr[data-job-id="${first}"]`)).toHaveCount(0);
  await expect(page.locator(`#ai-jobs-table tr[data-job-id="${second}"]`)).toBeVisible();
  // The same popup is used by controls; capability filtering is also enforced on submission.
  await page.evaluate(() => { void window.ZetModelPicker.open({ value: "codex:gpt-6-luna", required: ["vision"] }); });
  const dialog = page.locator("#ai-model-picker");
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('[data-provider="codex"]')).toHaveValue("codex:gpt-6-luna");
  await expect(dialog.locator('[data-provider="ollama"] option[value="text-only:latest"]')).toHaveCount(0);
  await dialog.locator('[data-provider="ollama"]').selectOption("image-analysis:latest");
  await expect(dialog.locator('[data-provider="codex"]')).toHaveValue("");
  await dialog.locator('[data-provider="codex"]').selectOption("codex:gpt-6-luna");
  await expect(dialog.locator('[data-provider="ollama"]')).toHaveValue("");
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  const invalid = await page.request.post("/__test/ai-submit", { data: { universe: "Test", model: "text-only:latest", vision: true } });
  expect(invalid.status()).toBe(400);
});
