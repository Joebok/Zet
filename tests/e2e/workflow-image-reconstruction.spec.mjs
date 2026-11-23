import { expect, test } from "@playwright/test";
import { createHash } from "node:crypto";
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";

test.afterEach(async ({ page }, testInfo) => {
  if (testInfo.status !== testInfo.expectedStatus) {
    await page.request.post("/__test/retain-failure", { data: { title: testInfo.title } });
  } else {
    expect(page.__zetPageErrors ?? [], "uncaught browser exceptions").toEqual([]);
  }
});

test("Image Generation reconstructs, compares, and corrects a selected result", async ({ page }) => {
  const reset = await page.request.post("/__test/reset");
  expect(reset.ok()).toBeTruthy();
  const context = await (await page.request.get("/__test/context")).json();
  const queue = context.queue;
  const image = await readFile(path.join(context.library, "Test", "responses", "render-1344x768.png"));
  const input = { mode: "txt2img", prompt: "A red lighthouse beside a pine forest", negative_prompt: "text",
    aspect_ratio: "16:9", reference_images: [] };
  let assetId = "";
  let completed = false;
  page.on("pageerror", error => {
    page.__zetPageErrors ??= [];
    page.__zetPageErrors.push(error.message);
  });

  try {
    const created = await (await page.request.post("/api/image-generation/assets", {
      data: { name: "E2E Reconstruction Lighthouse", inputs: input },
    })).json();
    assetId = created.asset_id;
    let detail = await imageAsset(page, assetId);
    const initial = await page.request.post(`/api/image-generation/assets/${assetId}/generate`, {
      data: { expected_revision: detail.revision, slot: 1, expected_assignment: null, render_mode: "draft" },
    });
    expect(initial.ok(), await initial.text()).toBeTruthy();
    detail = await initial.json();
    const firstAssignment = detail.slots[0];
    const firstAsk = await findAsk(queue, { ad_hoc_request_id: firstAssignment.requestId });
    await deliver(queue, firstAsk, image);
    await expect.poll(async () => {
      const current = await imageAsset(page, assetId);
      return current.jobs.find(job => job.request_id === firstAssignment.requestId)?.status;
    }).toBe("COMPLETE");

    detail = await imageAsset(page, assetId);
    const selected = await page.request.post(`/api/image-generation/assets/${assetId}/select`, {
      data: { expected_revision: detail.revision, slot: 1, expected_assignment: firstAssignment, render_mode: "draft" },
    });
    expect(selected.ok(), await selected.text()).toBeTruthy();
    detail = await selected.json();

    await page.goto(`/?page=image-generation&universe_id=Test&generation_asset=${assetId}&generation_view=reconstruction`);
    await expect(page.locator("#image-generation-page")).toHaveClass(/active/);
    const started = await page.request.post(`/api/image-generation/assets/${assetId}/analyze`, {
      data: { expected_revision: detail.revision, selected_result: firstAssignment,
        notes: "Keep the simple graphic style.", preserve: "Red lighthouse and surrounding pine forest.",
        changes: "Remove the small boat from the water." },
    });
    expect(started.ok(), await started.text()).toBeTruthy();
    detail = await started.json();
    const reconstructionId = detail.authoring.job_id;
    const analysisAsk = await findAsk(queue, { task_type: "image_reconstruction", llm_role: "reconstruction_prompt" });
    const preparedAnalysis = {
      content_prompt: "A red lighthouse rises above a pine forest beside calm water, with no boat.",
      identity: "Red lighthouse with tall white windows, evergreen shoreline.",
      observations: ["A small boat is visible in the source."], proposals: [], questions: [], uncertainties: [],
    };
    await deliver(queue, analysisAsk, JSON.stringify(preparedAnalysis));
    await expect.poll(async () => (await reconstruction(page, reconstructionId)).status).toBe("READY");
    const analysis = await reconstruction(page, reconstructionId);
    expect(analysis.target.observations).toContain("A small boat is visible in the source.");
    const preservedSource = await page.request.get(`/api/image-generation/reconstructions/${reconstructionId}/sources/0`);
    expect(preservedSource.ok()).toBeTruthy();
    expect(createHash("sha256").update(await preservedSource.body()).digest("hex"))
      .toBe(createHash("sha256").update(image).digest("hex"));

    const editedPrompt = analysis.prompt + " Keep the shoreline clear and the lighthouse centered.";
    await page.reload();
    const authoring = page.locator("[data-ig-authoring]");
    await authoring.locator("summary").click();
    const draftField = page.locator("[data-ig-draft]");
    await expect(draftField).toHaveValue(analysis.prompt);
    await draftField.fill(editedPrompt);
    const applyPrompt = page.locator("[data-ig-use]");
    await expect(applyPrompt).toBeEnabled();
    await applyPrompt.click();
    await expect.poll(async () => (await imageAsset(page, assetId)).authoring.edited_prompt)
      .toBe(editedPrompt);
    detail = await imageAsset(page, assetId);
    expect(detail.authoring.edited_prompt).toContain("Keep the shoreline clear");
    expect(detail.inputs.reconstruction.prompt).toBe(editedPrompt);

    const second = await page.request.post(`/api/image-generation/assets/${assetId}/generate`, {
      data: { expected_revision: detail.revision, slot: 2, expected_assignment: null, render_mode: "draft" },
    });
    expect(second.ok(), await second.text()).toBeTruthy();
    detail = await second.json();
    const secondAssignment = detail.slots[1];
    const secondAsk = await findAsk(queue, { ad_hoc_request_id: secondAssignment.requestId });
    await deliver(queue, secondAsk, image);
    await expect.poll(async () => {
      const current = await imageAsset(page, assetId);
      return current.jobs.find(job => job.request_id === secondAssignment.requestId)?.status;
    }).toBe("COMPLETE");
    detail = await imageAsset(page, assetId);
    const candidateJob = detail.jobs.find(job => job.request_id === secondAssignment.requestId);
    expect(candidateJob.prompt).toContain("Keep the shoreline clear");
    expect(candidateJob.reconstruction.target_hash).toBe(analysis.target_hash);
    expect(candidateJob.reference_labels || []).not.toContain("Original reconstruction source");
    const selectedSecond = await page.request.post(`/api/image-generation/assets/${assetId}/select`, {
      data: { expected_revision: detail.revision, slot: 2, expected_assignment: secondAssignment, render_mode: "draft" },
    });
    expect(selectedSecond.ok(), await selectedSecond.text()).toBeTruthy();
    detail = await selectedSecond.json();

    const compared = await page.request.post(`/api/image-generation/assets/${assetId}/compare`, {
      data: { selected_result: secondAssignment },
    });
    expect(compared.ok(), await compared.text()).toBeTruthy();
    const reportStarted = await compared.json();
    const compareAsk = await findAsk(queue, { task_type: "image_reconstruction", llm_role: "reconstruction_review" });
    await deliver(queue, compareAsk, JSON.stringify({ summary: "The lighthouse reads clearly.", items: [
      { category: "drift", visibility: "visible", feature: "A boat remains in the water.",
        evidence: "The candidate shows a boat on the water.", expected: "Water without a boat.",
        observed: "A small boat remains.", correction: "Remove the boat from the water.", severity: "minor" },
    ] }));
    await expect.poll(async () => (await report(page, reconstructionId, reportStarted.id)).status).toBe("COMPLETE");
    const reportDetail = await report(page, reconstructionId, reportStarted.id);
    expect(reportDetail.items[0].correction).toBe("Remove the boat from the water.");

    const correction = await page.request.post(`/api/image-generation/assets/${assetId}/correct`, {
      data: { task_id: reconstructionId, report_id: reportStarted.id, item_ids: [reportDetail.items[0].id],
        instructions: "Keep the shoreline clear.", selected_result: secondAssignment, render_mode: "draft", aspect_ratio: "16:9" },
    });
    expect(correction.ok(), await correction.text()).toBeTruthy();
    const correctionJob = await correction.json();
    expect(correctionJob.parent_task_id).toBe(reconstructionId);
    await expect.poll(async () => (await reconstruction(page, correctionJob.id)).status).toBe("SUBMITTED");
    const corrected = await reconstruction(page, correctionJob.id);
    expect(corrected.target.change_text).toContain("Remove the small boat from the water.");
    expect(corrected.target.change_text).toContain("Keep the shoreline clear.");
    expect(corrected.source.sha256).toBe(analysis.source.sha256);
    const correctionAsk = await findAsk(queue, { ad_hoc_request_id: correctionJob.id });
    expect(correctionAsk.ask_manifest.task_type).toBe("local_test_render");
    await deliver(queue, correctionAsk, image);
    await expect.poll(async () => {
      const current = await imageAsset(page, assetId);
      return current.jobs.find(job => job.request_id === correctionJob.id)?.status;
    }).toBe("COMPLETE");
    const finishedAsset = await imageAsset(page, assetId);
    const correctionOutput = finishedAsset.jobs.find(job => job.request_id === correctionJob.id);
    expect(correctionOutput.reconstruction.parent_task_id).toBe(reconstructionId);
    expect(correctionOutput.images[0].index).toBe(0);

    const fresh = await page.context().browser().newPage();
    try {
      const persisted = await imageAsset(fresh, assetId);
      expect(persisted.inputs.reconstruction.id).toBe(reconstructionId);
      expect(persisted.authoring.edited_prompt).toBe(editedPrompt);
      const savedCorrection = await reconstruction(fresh, correctionJob.id);
      expect(savedCorrection.parent_task_id).toBe(reconstructionId);
    } finally { await fresh.close(); }
    completed = true;
  } finally {
    if (completed) {
      const cleaned = await page.request.post("/__test/reset");
      expect(cleaned.ok()).toBeTruthy();
    }
  }
});

async function imageAsset(page, id) {
  const response = await page.request.get(`/api/image-generation/assets/${id}`);
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

async function reconstruction(page, id) {
  const response = await page.request.get(`/api/image-generation/reconstructions/${id}`);
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

async function report(page, taskId, id) {
  const response = await page.request.get(`/api/image-generation/reconstructions/${taskId}/reports/${id}`);
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

async function findAsk(queue, matches) {
  let found;
  await expect.poll(async () => {
    for (const state of ["Ask", "Running"]) {
      const root = path.join(queue, "File_Proxy", state, "zet");
      let folders = [];
      try { folders = await readdir(root, { withFileTypes: true }); } catch {}
      for (const folder of folders.filter(item => item.isDirectory() && !item.name.startsWith("."))) {
        try {
          const location = path.join(root, folder.name);
          const ask_manifest = JSON.parse(await readFile(path.join(location, "ask_manifest.json"), "utf8"));
          if (Object.entries(matches).every(([key, value]) => ask_manifest[key] === value)) {
            found = { id: ask_manifest.ask_id, location, ask_manifest };
            return true;
          }
        } catch {}
      }
    }
    return false;
  }).toBe(true);
  return found;
}

async function deliver(queue, ask, output) {
  const answer = path.join(queue, "File_Proxy", "Answer", "zet", ask.id);
  await mkdir(answer, { recursive: true });
  await writeFile(path.join(answer, "ask_manifest.json"), await readFile(path.join(ask.location, "ask_manifest.json")));
  await writeFile(path.join(answer, "job.json"), await readFile(path.join(ask.location, "job.json")));
  if (!Buffer.isBuffer(output)) output = Buffer.from(output, "utf8");
  await writeFile(path.join(answer, ask.ask_manifest.expected_output), output);
  await writeFile(path.join(answer, "answer_manifest.json"), JSON.stringify({ ask_id: ask.id, status: "SUCCESS",
    expected_output: ask.ask_manifest.expected_output, worker_id: "prepared-image-reconstruction-test", ollama_attempt_id: ask.id }));
  await writeFile(path.join(answer, "proxy_result.json"), JSON.stringify({ status: "SUCCEEDED", output_files: [
    { path: ask.ask_manifest.expected_output, size: output.length,
      sha256: createHash("sha256").update(output).digest("hex") },
  ] }));
}
