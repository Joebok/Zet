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

test("Character candidate board reviews work and protects Draft cleanup", async ({ page }) => {
  expect((await page.request.post("/__test/reset")).ok()).toBeTruthy();
  const context = await (await page.request.get("/__test/context")).json();
  const queue = context.queue;
  const image = await readFile(path.join(resultsRoot, "narrative-e2e", "fast", "render-1344x768.png"));
  const query = "character=Traveler&phase=Adult&universe_id=Test";
  const containerUrl = `/api/character-containers/character-assembly?${query}`;
  const viewUrl = `/api/character-containers/character-assembly/views/FRONT`;
  const endpoint = `${viewUrl}?${query}`;
  let completed = false;
  page.on("pageerror", error => {
    page.__zetPageErrors ??= [];
    page.__zetPageErrors.push(error.message);
  });
  try {
    let detail = await getJson(page, containerUrl);
    const generated = await page.request.post(`${viewUrl}/generate?${query}`, { data: {
      count: 1, render_mode: "draft", expected_revision: detail.revision,
    } });
    expect(generated.ok(), await generated.text()).toBeTruthy();
    detail = await generated.json();
    const firstId = detail.boards.FRONT.slots.find(Boolean);
    await answerEnvelope(queue, detail.boards.FRONT.candidates[firstId].ask_id, image);
    await expect.poll(async () => (await getJson(page, containerUrl)).boards.FRONT.candidates[firstId]?.status).toBe("COMPLETE");
    detail = await getJson(page, containerUrl);
    detail = await boardAction(page, query, firstId, "select", detail.revision);
    detail = await boardAction(page, query, firstId, "lock", detail.revision);
    expect(detail.boards.FRONT.candidates[firstId].locked).toBe(true);
    detail = await boardAction(page, query, firstId, "unlock", detail.revision);
    expect(detail.boards.FRONT.candidates[firstId].locked).toBe(false);

    const upscale = await page.request.post(`${viewUrl}/candidates/${firstId}/upscale?${query}`, { data: { expected_revision: detail.revision } });
    expect(upscale.ok(), await upscale.text()).toBeTruthy();
    detail = await upscale.json();
    let first = detail.boards.FRONT.candidates[firstId];
    expect(first.status).toBe("QUEUED");
    expect(first.upscale_request).toBeTruthy();
    const upscaleAttempt = first.attempt_id;
    const upscaleAsk = first.ask_id;
    detail = await boardAction(page, query, firstId, "cancel", detail.revision, {
      expected_candidate_id: firstId, expected_attempt_id: upscaleAttempt,
    });
    first = detail.boards.FRONT.candidates[firstId];
    expect(first.status).toBe("COMPLETE");
    expect(first.upscale_request).toBeUndefined();
    expect(upscaleAsk).toBeTruthy();

    const secondResponse = await page.request.post(`${viewUrl}/generate?${query}`, { data: {
      count: 1, render_mode: "draft", expected_revision: detail.revision,
    } });
    expect(secondResponse.ok(), await secondResponse.text()).toBeTruthy();
    detail = await secondResponse.json();
    const secondId = detail.boards.FRONT.slots.find(id => id && id !== firstId);
    await answerEnvelope(queue, detail.boards.FRONT.candidates[secondId].ask_id, image);
    await expect.poll(async () => (await getJson(page, containerUrl)).boards.FRONT.candidates[secondId]?.status).toBe("COMPLETE");

    await page.goto(`/?page=character-asset-container&pipeline=character-assembly&view=FRONT&character=Traveler&phase=Adult&universe_id=Test`);
    await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
    const cards = page.locator(".zet-candidate-board article");
    await expect(cards).toHaveCount(8);
    await expect(cards.nth(0)).toContainText("Draft");
    await expect(cards.nth(1)).toContainText("Draft");
    await page.getByRole("button", { name: "Review candidate (Slot 1)" }).click();
    const review = page.getByRole("dialog", { name: "Review candidate" });
    await expect(review).toBeVisible();
    await expect(review).toContainText("1 of 2");
    await review.getByRole("button", { name: "Next candidate" }).click();
    await expect(review).toContainText("2 of 2");
    await review.getByRole("button", { name: "Close review" }).click();

    detail = await getJson(page, containerUrl);
    detail = await boardAction(page, query, firstId, "select", detail.revision);
    const previewUrl = `${viewUrl}/delete-drafts/preview?${query}`;
    const previewResponse = await page.request.post(previewUrl);
    expect(previewResponse.ok(), await previewResponse.text()).toBeTruthy();
    const stalePreview = await previewResponse.json();
    expect(stalePreview.candidates.map(item => item.candidate_id).sort()).toEqual([firstId, secondId].sort());
    expect(stalePreview.protected_effects).toContainEqual(expect.objectContaining({ id: `select:${firstId}` }));

    detail = await boardAction(page, query, secondId, "select", detail.revision);
    const cleanupUrl = `${viewUrl}/delete-drafts?${query}`;
    const stale = await page.request.post(cleanupUrl, { data: {
      confirmation_token: stalePreview.confirmation_token, expected_revision: stalePreview.revision,
      approved_effects: stalePreview.protected_effects.map(item => item.id),
    } });
    expect(stale.status()).toBe(409);

    const freshResponse = await page.request.post(previewUrl);
    expect(freshResponse.ok()).toBeTruthy();
    const freshPreview = await freshResponse.json();
    expect(freshPreview.protected_effects).toEqual([{ id: `select:${secondId}`, candidate_id: secondId,
      label: "Clear selected candidate in slot 2" }]);
    const incompleteApproval = await page.request.post(cleanupUrl, { data: {
      confirmation_token: freshPreview.confirmation_token, expected_revision: freshPreview.revision, approved_effects: [],
    } });
    expect(incompleteApproval.status()).toBe(409);
    expect((await incompleteApproval.json()).detail).toContain("Approve each selected or locked candidate");

    const committed = await page.request.post(cleanupUrl, { data: {
      confirmation_token: freshPreview.confirmation_token, expected_revision: freshPreview.revision,
      approved_effects: freshPreview.protected_effects.map(item => item.id),
    } });
    expect(committed.ok(), await committed.text()).toBeTruthy();
    detail = await committed.json();
    expect(detail.boards.FRONT.slots.filter(Boolean)).toEqual([]);
    expect(detail.boards.FRONT.selected_id).toBeFalsy();
    for (const candidateId of [firstId, secondId]) expect(detail.boards.FRONT.candidates[candidateId]).toBeUndefined();
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

async function boardAction(page, query, candidateId, action, revision, extra = {}) {
  const response = await page.request.post(`/api/character-containers/character-assembly/views/FRONT/candidates/${candidateId}/${action}?${query}`, {
    data: { expected_revision: revision, expected_candidate_id: candidateId, ...extra },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
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
    expected_output: manifest.expected_output, worker_id: "prepared-character-board-test", ollama_attempt_id: id }));
  await writeFile(path.join(answer, "proxy_result.json"), JSON.stringify({ status: "SUCCEEDED", output_files: [
    { path: manifest.expected_output, size: output.length, sha256: createHash("sha256").update(output).digest("hex") },
  ] }));
}
