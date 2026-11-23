import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { resultsRoot } from "./results-path.mjs";

test.afterEach(async ({ page }, testInfo) => {
  if (testInfo.status !== testInfo.expectedStatus) {
    await page.request.post("/__test/retain-failure", { data: { title: testInfo.title } });
  } else {
    expect(page.__zetPageErrors ?? [], "uncaught browser exceptions").toEqual([]);
  }
});

test("Character Body and Head candidates capture their published upstream sources", async ({ page }) => {
  expect((await page.request.post("/__test/reset")).ok()).toBeTruthy();
  const context = await (await page.request.get("/__test/context")).json();
  const base = "/api/character-containers";
  const character = "Traveler";
  const phase = "Adult";
  const query = (selectedPhase, costume = "") => new URLSearchParams({
    character, phase: selectedPhase, ...(costume ? { costume } : {}), universe_id: "Test",
  }).toString();
  let completed = false;
  page.on("pageerror", error => {
    page.__zetPageErrors ??= [];
    page.__zetPageErrors.push(error.message);
  });
  try {
    const bodyFront = await getJson(page, `${base}/body-reference?${query(phase)}`);
    const bodyFrontId = bodyFront.boards.FRONT.selected_id;
    const bodyFrontAsset = bodyFront.boards.FRONT.candidates[bodyFrontId];
    expect(bodyFrontAsset.locked).toBe(true);
    const bodySave = await page.request.put(`${base}/body-reference/sources/views?${query(phase)}`, {
      data: { expected_revision: bodyFront.revision, source: { BACK: "FRONT" } },
    });
    expect(bodySave.ok(), await bodySave.text()).toBeTruthy();
    let body = await bodySave.json();
    const bodyUrl = `${base}/body-reference/views/BACK`;
    const bodyGenerate = await page.request.post(`${bodyUrl}/generate?${query(phase)}`, {
      data: { count: 1, render_mode: "draft", expected_revision: body.revision },
    });
    expect(bodyGenerate.ok(), await bodyGenerate.text()).toBeTruthy();
    body = await bodyGenerate.json();
    const bodyId = body.boards.BACK.slots.find(Boolean);
    let bodyCandidate = body.boards.BACK.candidates[bodyId];
    expect(bodyCandidate.render_request.inputs).toHaveLength(1);
    expect(bodyCandidate.render_request.inputs[0]).toMatchObject({ role: "body_reference_front_anchor", view: "FRONT", candidate_id: bodyFrontId });
    const bodyImage = await responseFor(context, bodyCandidate.render_request.settings);
    const bodyAsk = bodyCandidate.ask_id;
    await answerEnvelope(context.queue, bodyAsk, bodyImage);
    await expect.poll(async () => (await getJson(page, `${base}/body-reference?${query(phase)}`)).boards.BACK.candidates[bodyId]?.status).toBe("COMPLETE");
    body = await getJson(page, `${base}/body-reference?${query(phase)}`);
    body = await action(page, "body-reference", phase, "BACK", bodyId, "select", body.revision);
    body = await action(page, "body-reference", phase, "BACK", bodyId, "lock", body.revision);
    bodyCandidate = body.boards.BACK.candidates[bodyId];
    expect(bodyCandidate.locked).toBe(true);
    expect(bodyCandidate.inventory_asset_id).toBeTruthy();
    expect(bodyCandidate.render_request.inputs[0].candidate_id).toBe(bodyFrontId);

    const seededYoung = await page.request.post("/__test/seed-cross-phase-head-source");
    expect(seededYoung.ok(), await seededYoung.text()).toBeTruthy();
    let youngHead = (await seededYoung.json()).container;
    const adultHead = await getJson(page, `${base}/head-image-edit?${query(phase)}`);
    const adultHeadId = adultHead.boards.FRONT.selected_id;
    const adultHeadCandidate = adultHead.boards.FRONT.candidates[adultHeadId];
    expect(adultHeadCandidate.locked).toBe(true);
    const savedPhaseSource = await page.request.put(`${base}/head-image-edit/sources/phase_change?${query("E2E_Young")}`, {
      data: { expected_revision: youngHead.revision, source: { phase } },
    });
    expect(savedPhaseSource.ok(), await savedPhaseSource.text()).toBeTruthy();
    youngHead = await savedPhaseSource.json();
    expect(youngHead.sources.phase_change).toEqual({ phase });

    const headUrl = `${base}/head-image-edit/views/FRONT`;
    const headGenerate = await page.request.post(`${headUrl}/generate?${query("E2E_Young")}`, {
      data: { count: 1, render_mode: "draft", expected_revision: youngHead.revision, apply_phase_change: true },
    });
    expect(headGenerate.ok(), await headGenerate.text()).toBeTruthy();
    youngHead = await headGenerate.json();
    const headId = youngHead.boards.FRONT.slots.find(Boolean);
    let headCandidate = youngHead.boards.FRONT.candidates[headId];
    expect(headCandidate.render_request.inputs).toHaveLength(1);
    expect(headCandidate.render_request.inputs[0]).toMatchObject({
      role: "head_image_source", view: "FRONT", candidate_id: adultHeadId, sha256: adultHeadCandidate.image_sha256,
    });
    expect(headCandidate.render_request.provenance.apply_phase_change).toBe(true);
    expect(headCandidate.render_request.prompt).toContain("younger adult");
    const headImage = await responseFor(context, headCandidate.render_request.settings);
    await answerEnvelope(context.queue, headCandidate.ask_id, headImage);
    await expect.poll(async () => (await getJson(page, `${base}/head-image-edit?${query("E2E_Young")}`)).boards.FRONT.candidates[headId]?.status).toBe("COMPLETE");
    youngHead = await getJson(page, `${base}/head-image-edit?${query("E2E_Young")}`);
    youngHead = await action(page, "head-image-edit", "E2E_Young", "FRONT", headId, "select", youngHead.revision);
    youngHead = await action(page, "head-image-edit", "E2E_Young", "FRONT", headId, "lock", youngHead.revision);
    headCandidate = youngHead.boards.FRONT.candidates[headId];
    expect(headCandidate.locked).toBe(true);
    expect(headCandidate.inventory_asset_id).toBeTruthy();
    expect(headCandidate.render_request.inputs[0].candidate_id).toBe(adultHeadId);
    expect(createHash("sha256").update(headImage).digest("hex")).toBe(headCandidate.image_sha256);
    completed = true;
  } finally {
    if (completed) expect((await page.request.post("/__test/reset")).ok()).toBeTruthy();
  }
});

async function getJson(page, url) {
  const response = await page.request.get(url);
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

async function action(page, pipeline, phase, view, candidateId, name, revision) {
  const params = new URLSearchParams({ character: "Traveler", phase, universe_id: "Test" });
  const response = await page.request.post(`/api/character-containers/${pipeline}/views/${view}/candidates/${candidateId}/${name}?${params}`, {
    data: { expected_revision: revision, expected_candidate_id: candidateId },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

async function responseFor(context, settings) {
  const files = ["render-1344x768.png", "render-1216x832.png", "render-1184x896.png", "render-2720x1536.png", "render-832x1248.png", "render-1024x1024.png"];
  for (const filename of files) {
    const bytes = await readFile(path.join(resultsRoot, "narrative-e2e", "fast", filename));
    if (bytes.readUInt32BE(16) === settings.width && bytes.readUInt32BE(20) === settings.height) return bytes;
  }
  throw new Error(`No prepared response matches frozen sizing ${settings.width}x${settings.height}.`);
}

async function answerEnvelope(queue, id, output) {
  const ask = path.join(queue, "File_Proxy", "Ask", "zet", id);
  const answer = path.join(queue, "File_Proxy", "Answer", "zet", id);
  const manifestBytes = await readFile(path.join(ask, "ask_manifest.json"));
  const manifest = JSON.parse(manifestBytes.toString("utf8"));
  await mkdir(answer, { recursive: true });
  await writeFile(path.join(answer, "ask_manifest.json"), manifestBytes);
  await writeFile(path.join(answer, "job.json"), await readFile(path.join(ask, "job.json")));
  await writeFile(path.join(answer, manifest.expected_output), output);
  await writeFile(path.join(answer, "answer_manifest.json"), JSON.stringify({ ask_id: id, status: "SUCCESS",
    expected_output: manifest.expected_output, worker_id: "prepared-character-upstream-test", ollama_attempt_id: id }));
  await writeFile(path.join(answer, "proxy_result.json"), JSON.stringify({ status: "SUCCEEDED", output_files: [
    { path: manifest.expected_output, size: output.length, sha256: createHash("sha256").update(output).digest("hex") },
  ] }));
}
