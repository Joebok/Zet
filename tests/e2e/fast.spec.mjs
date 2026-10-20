import { expect, test } from "@playwright/test";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";

const image = (width, height) => path.resolve("test-results/narrative-e2e/fast", `render-${width}x${height}.png`);

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
  else await page.getByRole("button", { name: "Overview" }).click();
  await page.locator("#character-setup-details > summary").click();
  const character = page.locator("#onboarding-character");
  const phase = page.locator("#onboarding-phase");
  await expect(character).toHaveValue("Traveler");
  await expect(phase).toHaveValue("Adult");
  const characterPath = path.join(context.library, "Test", "Characters", "Traveler", "Adult", "Character.md");
  const originalCharacter = await readFile(characterPath, "utf8");
  const editedCharacter = originalCharacter.replace("Canonical Art Style: `Simple graphic illustration`", "Canonical Art Style: `Warm watercolor illustration`");
  await page.locator("#onboarding-template-file").setInputFiles({ name: "Character.md", mimeType: "text/markdown", buffer: Buffer.from(editedCharacter) });
  await page.getByRole("button", { name: "Upload Template" }).click();
  await expect.poll(async () => readFile(path.join(context.library, "Test", "Characters", "Traveler", "Adult", "Character.md"), "utf8"))
    .toContain("Warm watercolor illustration");
  await page.locator("#onboarding-template-file").setInputFiles({ name: "Character.md", mimeType: "text/markdown", buffer: Buffer.from(originalCharacter) });
  await page.getByRole("button", { name: "Upload Template" }).click();
  await expect.poll(async () => readFile(characterPath, "utf8")).toContain("Simple graphic illustration");

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
  await page.getByRole("button", { name: "Write Prompt" }).click();
  await answerJob(page, scene, ids.subscene, "synthesize", { scene: "A traveler reaches a forest gate.", rendering: "Soft daylight." });

  for (const [index, targetId] of targets.entries()) {
    await page.goto(`/narrative?story=${ids.story}&scene=${ids.scene}&target=${targetId}`);
    if (index === 0) {
      await page.locator("#narrative-prompt").fill("A quiet forest path, soft daylight.");
      await page.getByRole("button", { name: "Save inputs" }).click();
      await page.getByRole("button", { name: "Render 1" }).click();
      await answerRender(page, scene, targetId, image(1344, 768));
    } else {
      await page.locator("#narrative-prompt").fill("The traveler reaches the forest gate.");
      await page.getByRole("button", { name: "Save inputs" }).click();
      await page.getByRole("button", { name: "Render 1" }).click();
      await answerRender(page, scene, targetId, null, true);
      await expect(page.locator(".narrative-slot").first()).toContainText("failed");
      await page.locator(".narrative-slot").first().getByRole("button", { name: "Retry" }).click();
      await answerRender(page, scene, targetId, image(1216, 832));
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
  await page.getByRole("button", { name: "Render 1" }).click();
  const renderResponse = await renderReply;
  expect(renderResponse.ok(), await renderResponse.text()).toBeTruthy();
  await answerRender(page, scene, assembly, image(1344, 768));
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
  await expect(page.locator(".narrative-story-scene img")).toHaveJSProperty("naturalWidth", 1344);
  expect(details[1].kind).toBe("subscene");
});

test("character-to-costume workflow previews prerequisites and creates a real run", async ({ page }) => {
  const context = await (await page.request.get("/__test/context")).json();
  const preview = await page.request.post("/api/local/character-assembly/preview?universe_id=Test", {
    data: { character: "Traveler", phase: "Adult", costume: "", front_only: true, front_count: 1, other_count: 1 },
  });
  expect(preview.ok(), await preview.text()).toBeTruthy();
  const plan = await preview.json();
  expect(plan.can_create, JSON.stringify(plan.blocking_reasons)).toBeTruthy();
  const runResponse = await page.request.post("/api/local/character-assembly/runs?universe_id=Test", { data: {
    character: "Traveler", phase: "Adult", costume: "", front_only: true,
    front_count: 1, other_count: 1, seeds: [11],
  }});
  expect(runResponse.ok(), await runResponse.text()).toBeTruthy();
  const run = await runResponse.json();
  expect(run.status).toBe("QUEUED");
  expect(run.candidates.filter(candidate => candidate.view === "FRONT")).toHaveLength(1);
  const assemblyCandidate = await processLocalFront(page, "character-assembly", run.run_id, "", image(1344, 768));
  const assemblyLock = await page.request.post(`/api/local/character-assembly/runs/${run.run_id}/views/FRONT/lock?universe_id=Test`);
  expect(assemblyLock.ok(), await assemblyLock.text()).toBeTruthy();
  expect((await assemblyLock.json()).locked).toBeTruthy();
  const dressingPreview = await page.request.post("/api/local/costume-dressing/preview?universe_id=Test", { data: {
    character: "Traveler", phase: "Adult", costume: "Test Travel Outfit", front_only: true,
    front_count: 1, other_count: 1,
  }});
  expect(dressingPreview.ok(), await dressingPreview.text()).toBeTruthy();
  const dressingPlan = await dressingPreview.json();
  expect(dressingPlan.can_create, JSON.stringify(dressingPlan.blocking_reasons)).toBeTruthy();
  const dressingResponse = await page.request.post("/api/local/costume-dressing/runs?universe_id=Test", { data: {
    character: "Traveler", phase: "Adult", costume: "Test Travel Outfit", front_only: true,
    front_count: 1, other_count: 1, seeds: [21],
  }});
  expect(dressingResponse.ok(), await dressingResponse.text()).toBeTruthy();
  const dressing = await dressingResponse.json();
  await processLocalFront(page, "costume-dressing", dressing.run_id, "Test Travel Outfit", image(1344, 768));
  const dressingLock = await page.request.post(`/api/local/costume-dressing/runs/${dressing.run_id}/views/FRONT/lock?costume=Test%20Travel%20Outfit&universe_id=Test`);
  expect(dressingLock.ok(), await dressingLock.text()).toBeTruthy();
  expect((await dressingLock.json()).locked).toBeTruthy();
  expect(assemblyCandidate.image_available).toBeTruthy();
  const costume = await page.request.get("/api/costumes?character=Traveler&phase=Adult&universe_id=Test");
  expect(costume.ok()).toBeTruthy();
  expect((await costume.json()).costumes.map(item => item.name)).toContain("Test Travel Outfit");
  await expect(page.locator("body")).toContainText("Narrative Scenes");
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

async function processLocalFront(page, pipeline, runId, costume, pngPath) {
  const base = `/api/local/${pipeline}/runs/${runId}`;
  const query = `?universe_id=Test${costume ? `&costume=${encodeURIComponent(costume)}` : ""}`;
  const reviewResponse = await page.request.post(`${base}/template-revisions${query}`, { data: { model: "codex:gpt-6-luna" } });
  expect(reviewResponse.ok(), await reviewResponse.text()).toBeTruthy();
  const reviewId = (await reviewResponse.json()).revision.revision_id;
  const reviewAnswered = new Set();
  await expect.poll(async () => {
    const review = (await (await page.request.get(`${base}/template-revisions${query}&revision_id=${reviewId}`)).json()).revision;
    if (review.status === "FAILED") throw new Error(review.error);
    const queue = await (await page.request.get("/api/ai/jobs")).json();
    for (const job of queue.items || []) {
      if (job.task_type === "character_prompt_review" && job.status === "QUEUED" && !reviewAnswered.has(job.ask_id)) {
        await deliverEnvelope(page, job.ask_id, { summary: "Prepared prompt review: no corrections needed.", findings: [] });
        reviewAnswered.add(job.ask_id);
      }
    }
    return review.status;
  }, { timeout: 20000 }).toBe("REVIEW_READY");
  const accepted = await page.request.post(`${base}/template-revisions/${reviewId}/accept${query}`, { data: { selected_ids: [] } });
  expect(accepted.ok(), await accepted.text()).toBeTruthy();
  const started = await page.request.post(`${base}/views/FRONT/proceed${query}`, { data: { expected_stage: -1 } });
  expect(started.ok(), await started.text()).toBeTruthy();
  const context = await (await page.request.get("/__test/context")).json();
  const answered = new Set();
  let candidate;
  await expect.poll(async () => {
    const response = await page.request.get(`${base}${query}`);
    const run = await response.json();
    if (["ERROR", "CANCELLED"].includes(run.status)) throw new Error(run.error || run.status);
    candidate = run.candidates.find(item => item.view === "FRONT");
    if (candidate?.ask_id && !answered.has(candidate.ask_id)) {
      await answerLocalEnvelope(context.queue, candidate.ask_id, await readFile(pngPath));
      answered.add(candidate.ask_id);
    }
    if (run.rankings?.FRONT?.status === "FAILED") {
      throw new Error(`Luna ranking failed: ${run.rankings.FRONT.error || "unknown error"}`);
    }
    return candidate?.image_available && run.rankings?.FRONT?.status === "COMPLETE" ? "READY" : candidate?.status;
  }, { timeout: 70_000 }).toBe("READY");
  const selected = await page.request.post(`${base}/views/FRONT/select${query}`, { data: { candidate_id: candidate.candidate_id } });
  expect(selected.ok(), await selected.text()).toBeTruthy();
  const imageResponse = await page.request.get(`${base}/images/${candidate.candidate_id}${query}`);
  expect(imageResponse.ok()).toBeTruthy();
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
