import { expect, test } from "@playwright/test";
import { createHash } from "node:crypto";
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { resultsRoot } from "./results-path.mjs";

test.afterEach(async ({ page }, testInfo) => {
  const errors = page.__zetPageErrors ?? [];
  if (testInfo.status !== testInfo.expectedStatus || errors.length) {
    await page.request.post("/__test/retain-failure", { data: { title: testInfo.title } });
  }
  if (testInfo.status === testInfo.expectedStatus) {
    expect(errors, "uncaught browser exceptions").toEqual([]);
  }
});

test("Narrative finishes a cropped Final assembly with confirmed lettering", async ({ page }) => {
  const reset = await page.request.post("/__test/reset");
  expect(reset.ok()).toBeTruthy();
  const context = await (await page.request.get("/__test/context")).json();
  const { story, scene, backdrop, assembly } = context.ids;
  const sceneUrl = `/api/narrative/stories/${story}/scenes/${scene}`;
  const targetUrl = target => `${sceneUrl}/targets/${target}?universe_id=Test`;
  const sceneTextUrl = (target, candidate) => `${targetUrl(target).split("?")[0]}/scene-text?candidate=${candidate}&universe_id=Test`;
  const draftImage = await readFile(path.join(resultsRoot, "narrative-e2e", "fast", "render-1344x768.png"));
  const finalImage = await readFile(path.join(resultsRoot, "narrative-e2e", "fast", "render-2720x1536.png"));
  let completed = false;
  page.on("pageerror", error => {
    page.__zetPageErrors ??= [];
    page.__zetPageErrors.push(error.message);
  });

  try {
    const changedScene = await page.request.patch(`${sceneUrl}?universe_id=Test`, { data: { canvas: "16:9" } });
    expect(changedScene.ok(), await changedScene.text()).toBeTruthy();
    let source = await target(page, targetUrl, backdrop);
    const sourcePrompt = await page.request.patch(targetUrl(backdrop), {
      data: { prompt: "A quiet forest path beneath a clear sky.", visual_overrides: { style: "Simple graphic illustration" } },
    });
    expect(sourcePrompt.ok(), await sourcePrompt.text()).toBeTruthy();
    const sourceJob = await startRender(page, sceneUrl, backdrop, "draft");
    const sourceCandidate = sourceJob.candidate_ids[0];
    await answerRender(context.queue, sourceJob.image_job_id, draftImage);
    await expect.poll(async () => (await target(page, targetUrl, backdrop)).candidates[sourceCandidate]?.status).toBe("COMPLETE");
    source = await target(page, targetUrl, backdrop);
    const originalBytes = Buffer.from(await (await page.request.get(`${sceneUrl}/targets/${backdrop}/candidates/${sourceCandidate}/image?universe_id=Test`)).body());
    const sourceHash = createHash("sha256").update(originalBytes).digest("hex");

    const createdBackdrop = await page.request.post(`${sceneUrl}/references?universe_id=Test`, { data: {
      title: "E2E Cropped Forest", source: { story_id: story, scene_id: scene, target_id: backdrop,
        candidate_id: sourceCandidate, render_mode: "draft" },
    } });
    expect(createdBackdrop.ok(), await createdBackdrop.text()).toBeTruthy();
    const cropTarget = await createdBackdrop.json();
    const adapted = await page.request.patch(targetUrl(cropTarget.id), { data: {
      backdrop_adaptation: { crop_enabled: true, crop: { x: 80, y: 64, width: 1184, height: 640 } },
    } });
    expect(adapted.ok(), await adapted.text()).toBeTruthy();
    const cropApply = await page.request.post(`${sceneUrl}/targets/${cropTarget.id}/backdrop-source?universe_id=Test`, {
      data: { action: "crop", render_mode: "draft" },
    });
    expect(cropApply.ok(), await cropApply.text()).toBeTruthy();
    let cropped = await cropApply.json();
    const cropId = cropped.selected_id;
    expect(cropped.candidates[cropId].backdrop_adaptation.operation).toBe("crop");
    const croppedImage = await page.request.get(`${sceneUrl}/targets/${cropTarget.id}/candidates/${cropId}/image?universe_id=Test`);
    expect(croppedImage.ok()).toBeTruthy();
    expect(createHash("sha256").update(await croppedImage.body()).digest("hex")).not.toBe(sourceHash);

    const layers = [{ target_id: cropTarget.id, candidate_id: cropId,
      role: "base", fit: "cover", cutout: "opaque", x: 0.5, y: 0.5, scale: 1, z: 0, opacity: 1,
      visible: true, strokes: [] }];
    const assemblyUpdated = await page.request.patch(targetUrl(assembly), { data: {
      assembly_mode: "finish_composite", layers, prompt: "A finished forest scene with a traveler approaching the gate.",
      visual_overrides: { style: "Simple graphic illustration" },
    } });
    expect(assemblyUpdated.ok(), await assemblyUpdated.text()).toBeTruthy();
    const assemblyJob = await startRender(page, sceneUrl, assembly, "final");
    expect(assemblyJob.render_sizing.render_mode).toBe("final");
    expect(assemblyJob.render_sizing.aspect_ratio).toBe("16:9");
    const finishedCandidate = assemblyJob.candidate_ids[0];
    await answerRender(context.queue, assemblyJob.image_job_id, finalImage);
    await expect.poll(async () => (await target(page, targetUrl, assembly)).candidates[finishedCandidate]?.status).toBe("COMPLETE");
    let currentAssembly = await target(page, targetUrl, assembly);
    expect(currentAssembly.candidates[finishedCandidate].render_mode).toBe("final");

    let textState = await getSceneText(page, sceneTextUrl, assembly, finishedCandidate);
    const entries = [{ id: "e2e-caption", text: "The journey begins", tail: "none", placement: { box: [0.1, 0.8, 0.8, 0.15] } }];
    const placements = { "e2e-caption": { box: [0.1, 0.8, 0.8, 0.15] } };
    const savedText = await page.request.post(`${sceneUrl}/targets/${assembly}/scene-text/save?candidate=${finishedCandidate}&universe_id=Test`, {
      data: { revision: textState.revision, entries, placements },
    });
    expect(savedText.ok(), await savedText.text()).toBeTruthy();
    textState = await savedText.json();
    expect(textState.entries[0].text).toBe("The journey begins");
    const previewPayload = { entries: textState.entries, placements: textState.placements };
    const preview = await page.request.post(`${sceneUrl}/targets/${assembly}/scene-text/preview?candidate=${finishedCandidate}&universe_id=Test`, { data: previewPayload });
    expect(preview.ok(), await preview.text()).toBeTruthy();
    const staleToken = (await preview.json()).token;

    const changed = await page.request.post(`${sceneUrl}/targets/${assembly}/scene-text/save?candidate=${finishedCandidate}&universe_id=Test`, {
      data: { revision: textState.revision, entries: [{ ...entries[0], text: "The journey starts" }], placements },
    });
    expect(changed.ok(), await changed.text()).toBeTruthy();
    const staleConfirm = await page.request.post(`${sceneUrl}/targets/${assembly}/scene-text/confirm?candidate=${finishedCandidate}&universe_id=Test`, {
      data: { token: staleToken },
    });
    expect(staleConfirm.status()).toBe(400);
    expect((await staleConfirm.json()).detail).toContain("Preview again");

    textState = await getSceneText(page, sceneTextUrl, assembly, finishedCandidate);
    const freshPreview = await page.request.post(`${sceneUrl}/targets/${assembly}/scene-text/preview?candidate=${finishedCandidate}&universe_id=Test`, {
      data: { entries: textState.entries, placements: textState.placements },
    });
    expect(freshPreview.ok(), await freshPreview.text()).toBeTruthy();
    const confirmed = await page.request.post(`${sceneUrl}/targets/${assembly}/scene-text/confirm?candidate=${finishedCandidate}&universe_id=Test`, {
      data: { token: (await freshPreview.json()).token },
    });
    expect(confirmed.ok(), await confirmed.text()).toBeTruthy();
    currentAssembly = await confirmed.json();
    expect(currentAssembly.candidates[finishedCandidate].scene_text_final.image).toContain("lettering/");

    const artwork = await page.request.get(`${sceneUrl}/targets/${assembly}/candidates/${finishedCandidate}/image?universe_id=Test`);
    const lettered = await page.request.get(`${sceneUrl}/targets/${assembly}/candidates/${finishedCandidate}/finished-image?universe_id=Test`);
    expect(artwork.ok() && lettered.ok()).toBeTruthy();
    const artworkBytes = Buffer.from(await artwork.body());
    const letteredBytes = Buffer.from(await lettered.body());
    expect(createHash("sha256").update(letteredBytes).digest("hex"))
      .not.toBe(createHash("sha256").update(artworkBytes).digest("hex"));
    const lock = await page.request.post(`${sceneUrl}/targets/${assembly}/candidates/${finishedCandidate}?universe_id=Test`, {
      data: { action: "lock" },
    });
    expect(lock.ok(), await lock.text()).toBeTruthy();
    await page.goto(`/narrative?story=${story}&scene=${scene}&target=${assembly}`);
    await page.reload();
    const persisted = await target(page, targetUrl, assembly);
    expect(persisted.candidates[finishedCandidate].locked).toBe(true);
    expect(persisted.candidates[finishedCandidate].scene_text_final.token).toBeTruthy();
    const persistedImage = await page.request.get(`${sceneUrl}/targets/${assembly}/candidates/${finishedCandidate}/finished-image?universe_id=Test`);
    expect(createHash("sha256").update(await persistedImage.body()).digest("hex"))
      .toBe(createHash("sha256").update(letteredBytes).digest("hex"));
    completed = true;
  } finally {
    if (completed) {
      const cleaned = await page.request.post("/__test/reset");
      expect(cleaned.ok()).toBeTruthy();
    }
  }
});

async function target(page, targetUrl, id) {
  const response = await page.request.get(targetUrl(id));
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

async function startRender(page, sceneUrl, target, render_mode) {
  const response = await page.request.post(`${sceneUrl}/targets/${target}/jobs?universe_id=Test`, {
    data: { action: "render", count: 1, render_mode },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  let job, candidate;
  await expect.poll(async () => {
    const detail = await targetDetail(page, sceneUrl, target);
    job = Object.values(detail.jobs).filter(item => item.kind === "render").at(-1);
    candidate = detail.candidates[job?.candidate_ids?.[0]];
    return candidate?.status;
  }).toBe("QUEUED");
  return { ...job, candidate_id: candidate.id, image_job_id: candidate.job_id };
}

async function targetDetail(page, sceneUrl, targetId) {
  const response = await page.request.get(`${sceneUrl}/targets/${targetId}?universe_id=Test`);
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

async function getSceneText(page, sceneTextUrl, targetId, candidate) {
  const response = await page.request.get(sceneTextUrl(targetId, candidate));
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

async function answerRender(queue, id, output) {
  const ask = path.join(queue, "File_Proxy", "Ask", "zet", id);
  const answer = path.join(queue, "File_Proxy", "Answer", "zet", id);
  const manifest = JSON.parse(await readFile(path.join(ask, "ask_manifest.json"), "utf8"));
  await mkdir(answer, { recursive: true });
  await writeFile(path.join(answer, "ask_manifest.json"), await readFile(path.join(ask, "ask_manifest.json")));
  await writeFile(path.join(answer, "job.json"), await readFile(path.join(ask, "job.json")));
  await writeFile(path.join(answer, manifest.expected_output), output);
  await writeFile(path.join(answer, "answer_manifest.json"), JSON.stringify({ ask_id: id, status: "SUCCESS",
    expected_output: manifest.expected_output, worker_id: "prepared-narrative-finishing-test", ollama_attempt_id: id }));
  await writeFile(path.join(answer, "proxy_result.json"), JSON.stringify({ status: "SUCCEEDED", output_files: [
    { path: manifest.expected_output, size: output.length,
      sha256: createHash("sha256").update(output).digest("hex") },
  ] }));
}
