import { expect, test } from "@playwright/test";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
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

test("Narrative animation pins a lettered assembly and persists timed edits", async ({ page }) => {
  const reset = await page.request.post("/__test/reset");
  expect(reset.ok()).toBeTruthy();
  const context = await (await page.request.get("/__test/context")).json();
  const { story, scene, backdrop, assembly } = context.ids;
  const sceneUrl = `/api/narrative/stories/${story}/scenes/${scene}`;
  const targetUrl = id => `${sceneUrl}/targets/${id}`;
  const image = await readFile(path.join(resultsRoot, "narrative-e2e", "fast", "render-1184x896.png"));
  let completed = false;
  page.on("pageerror", error => {
    page.__zetPageErrors ??= [];
    page.__zetPageErrors.push(error.message);
  });
  try {
    const backdropPrompt = await page.request.patch(`${targetUrl(backdrop)}?universe_id=Test`, {
      data: { prompt: "A forest gate in soft daylight.", visual_overrides: { style: "Simple graphic illustration" } },
    });
    expect(backdropPrompt.ok(), await backdropPrompt.text()).toBeTruthy();
    const backdropRender = await startRender(page, sceneUrl, backdrop, "draft");
    await deliver(context.queue, backdropRender.image_job_id, image);
    await expect.poll(async () => (await target(page, targetUrl(backdrop))).candidates[backdropRender.candidate_id]?.status).toBe("COMPLETE");

    const assemblyPatch = await page.request.patch(`${targetUrl(assembly)}?universe_id=Test`, { data: {
      assembly_mode: "finish_composite", layers: [{ target_id: backdrop, candidate_id: backdropRender.candidate_id,
        role: "base", fit: "cover", cutout: "opaque", x: 0.5, y: 0.5, scale: 1, z: 0, opacity: 1, visible: true, strokes: [] }],
      prompt: "A traveler pauses at the forest gate.", visual_overrides: { style: "Simple graphic illustration" },
    } });
    expect(assemblyPatch.ok(), await assemblyPatch.text()).toBeTruthy();
    const assemblyRender = await startRender(page, sceneUrl, assembly, "draft");
    await deliver(context.queue, assemblyRender.image_job_id, image);
    await expect.poll(async () => (await target(page, targetUrl(assembly))).candidates[assemblyRender.candidate_id]?.status).toBe("COMPLETE");

    const textUrl = `${targetUrl(assembly)}/scene-text?candidate=${assemblyRender.candidate_id}&universe_id=Test`;
    let textState = await jsonGet(page, textUrl);
    const entries = [{ id: "animation-caption", text: "A new path opens", tail: "none" }];
    const placements = { "animation-caption": { box: [0.15, 0.8, 0.7, 0.15] } };
    const textSaved = await page.request.post(`${targetUrl(assembly)}/scene-text/save?candidate=${assemblyRender.candidate_id}&universe_id=Test`, {
      data: { revision: textState.revision, entries, placements },
    });
    expect(textSaved.ok(), await textSaved.text()).toBeTruthy();
    textState = await textSaved.json();
    const textPreview = await page.request.post(`${targetUrl(assembly)}/scene-text/preview?candidate=${assemblyRender.candidate_id}&universe_id=Test`, {
      data: { entries: textState.entries, placements: textState.placements },
    });
    expect(textPreview.ok(), await textPreview.text()).toBeTruthy();
    const textConfirm = await page.request.post(`${targetUrl(assembly)}/scene-text/confirm?candidate=${assemblyRender.candidate_id}&universe_id=Test`, {
      data: { token: (await textPreview.json()).token },
    });
    expect(textConfirm.ok(), await textConfirm.text()).toBeTruthy();
    const locked = await page.request.post(`${targetUrl(assembly)}/candidates/${assemblyRender.candidate_id}?universe_id=Test`, {
      data: { action: "lock" },
    });
    expect(locked.ok(), await locked.text()).toBeTruthy();
    const finishedImageResponse = await page.request.get(`${targetUrl(assembly)}/candidates/${assemblyRender.candidate_id}/finished-image?universe_id=Test`);
    expect(finishedImageResponse.ok()).toBeTruthy();
    const finishedImage = Buffer.from(await finishedImageResponse.body());
    expect(createHash("sha256").update(finishedImage).digest("hex"))
      .not.toBe(createHash("sha256").update(image).digest("hex"));

    const created = await page.request.post(`/api/narrative/stories/${story}/animations?universe_id=Test`, {
      data: { name: "E2E Forest Arrival", aspect_ratio: "16:9" },
    });
    expect(created.ok(), await created.text()).toBeTruthy();
    let animation = await created.json();
    const bound = await page.request.post(`/api/narrative/stories/${story}/animations/${animation.id}/sources?universe_id=Test`, {
      data: { source_id: `${scene}:${assembly}:${assemblyRender.candidate_id}` },
    });
    expect(bound.ok(), await bound.text()).toBeTruthy();
    animation = await bound.json();
    const assetId = animation.bound_asset_id;
    expect(animation.assets[assetId].lettering_separable).toBe(true);
    const sourceSnapshot = animation.assets[assetId];
    const pinnedArtwork = Buffer.from(sourceSnapshot.artwork_data_url.split(",")[1], "base64");
    expect(createHash("sha256").update(pinnedArtwork).digest("hex")).toBe(sourceSnapshot.sha256);

    const spec = { ...animation.spec, shots: [{ id: "arrival", source_id: assetId, duration_ms: 2400,
      camera_mode: "center", camera: [{ time_ms: 0, x: 0.5, y: 0.5, zoom: 1 },
        { time_ms: 2400, x: 0.55, y: 0.48, zoom: 1.2 }],
      text: { "animation-caption": [{ time_ms: 0, opacity: 0 }, { time_ms: 500, opacity: 1 }, { time_ms: 2200, opacity: 1 }] },
    }], transitions: [{ type: "cut", duration_ms: 0 }, { type: "cut", duration_ms: 0 }] };
    const save = await page.request.put(`/api/narrative/stories/${story}/animations/${animation.id}?universe_id=Test`, {
      data: { revision: animation.revision, spec },
    });
    expect(save.ok(), await save.text()).toBeTruthy();
    const saved = await save.json();
    const stale = await page.request.put(`/api/narrative/stories/${story}/animations/${animation.id}?universe_id=Test`, {
      data: { revision: animation.revision, spec: { ...spec, name: "Stale overwrite" } },
    });
    expect([409, 400]).toContain(stale.status());
    animation = await (await page.request.get(`/api/narrative/stories/${story}/animations/${animation.id}?universe_id=Test`)).json();
    expect(animation.spec.name).toBe("E2E Forest Arrival");
    expect(animation.spec.shots[0].camera).toEqual(spec.shots[0].camera);
    expect(animation.spec.shots[0].text["animation-caption"]).toHaveLength(3);
    expect(animation.assets[assetId].text_data_urls["animation-caption"]).toBeTruthy();
    const html = await page.request.get(`/api/narrative/stories/${story}/animations/${animation.id}/html?universe_id=Test`);
    expect(html.ok()).toBeTruthy();
    const htmlText = await html.text();
    expect(htmlText).toContain("E2E Forest Arrival");
    expect(htmlText).toContain(sourceSnapshot.text_data_urls["animation-caption"].split(",")[1]);
    expect(saved.assets[assetId].sha256).toBe(sourceSnapshot.sha256);
    completed = true;
  } finally {
    if (completed) {
      const cleaned = await page.request.post("/__test/reset");
      expect(cleaned.ok()).toBeTruthy();
    }
  }
});

async function target(page, targetUrl) {
  return jsonGet(page, `${targetUrl}?universe_id=Test`);
}

async function jsonGet(page, url) {
  const response = await page.request.get(url);
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
    const detail = await jsonGet(page, `${sceneUrl}/targets/${target}?universe_id=Test`);
    job = Object.values(detail.jobs).filter(item => item.kind === "render").at(-1);
    candidate = detail.candidates[job?.candidate_ids?.[0]];
    return candidate?.status;
  }).toBe("QUEUED");
  return { ...job, candidate_id: candidate.id, image_job_id: candidate.job_id };
}

async function deliver(queue, id, output) {
  const ask = path.join(queue, "File_Proxy", "Ask", "zet", id);
  const answer = path.join(queue, "File_Proxy", "Answer", "zet", id);
  const manifest = JSON.parse(await readFile(path.join(ask, "ask_manifest.json"), "utf8"));
  await mkdir(answer, { recursive: true });
  await writeFile(path.join(answer, "ask_manifest.json"), await readFile(path.join(ask, "ask_manifest.json")));
  await writeFile(path.join(answer, "job.json"), await readFile(path.join(ask, "job.json")));
  await writeFile(path.join(answer, manifest.expected_output), output);
  await writeFile(path.join(answer, "answer_manifest.json"), JSON.stringify({ ask_id: id, status: "SUCCESS",
    expected_output: manifest.expected_output, worker_id: "prepared-narrative-animation-test", ollama_attempt_id: id }));
  await writeFile(path.join(answer, "proxy_result.json"), JSON.stringify({ status: "SUCCEEDED", output_files: [
    { path: manifest.expected_output, size: output.length,
      sha256: createHash("sha256").update(output).digest("hex") },
  ] }));
}
