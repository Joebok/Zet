import { expect, test } from "@playwright/test";
import { createHash } from "node:crypto";
import { access, mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";

test("Image Generation renders, publishes, and cancels its owned queued work", async ({ page, browser }) => {
  const reset = await page.request.post("/__test/reset");
  expect(reset.ok()).toBeTruthy();
  const context = await (await page.request.get("/__test/context")).json();
  const input = { mode: "txt2img", prompt: "A lighthouse among pine trees", negative_prompt: "text",
    aspect_ratio: "16:9", reference_images: [] };
  const createdResponse = await page.request.post("/api/image-generation/assets", {
    data: { name: "E2E Lighthouse", inputs: input },
  });
  expect(createdResponse.ok(), await createdResponse.text()).toBeTruthy();
  const created = await createdResponse.json();
  expect(created.asset_id).toMatch(/^[a-f0-9]{32}$/);

  const saved = await page.request.post(`/api/image-generation/assets/${created.asset_id}/save`, {
    data: { expected_revision: created.revision, name: "E2E Lighthouse Saved",
      inputs: { ...input, prompt: "A red lighthouse beside a pine forest" } },
  });
  expect(saved.ok(), await saved.text()).toBeTruthy();
  const detail = await saved.json();
  expect(detail.name).toBe("E2E Lighthouse Saved");
  expect(detail.inputs.prompt).toBe("A red lighthouse beside a pine forest");

  const secondPage = await browser.newPage();
  try {
    const reloaded = await secondPage.request.get(`/api/image-generation/assets/${created.asset_id}`);
    expect(reloaded.ok()).toBeTruthy();
    expect((await reloaded.json()).inputs).toMatchObject({
      prompt: "A red lighthouse beside a pine forest", aspect_ratio: "16:9", mode: "txt2img",
    });
    await secondPage.goto("/?page=image-generation");
    await expect(secondPage.locator("#image-generation-page")).toHaveClass(/active/);
    await expect(secondPage.locator("#image-generation-page")).toContainText("E2E Lighthouse Saved");

    let current = await (await secondPage.request.get(`/api/image-generation/assets/${created.asset_id}`)).json();
    const generated = await secondPage.request.post(`/api/image-generation/assets/${created.asset_id}/generate`, {
      data: { expected_revision: current.revision, slot: 1, expected_assignment: null, render_mode: "draft" },
    });
    expect(generated.ok(), await generated.text()).toBeTruthy();
    current = await generated.json();
    const assignment = current.slots[0];
    expect(assignment.requestId).toBeTruthy();
    const transportId = await findImageGenerationAsk(context.queue, assignment.requestId);
    await deliverPreparedImage(context.queue, transportId,
      await readFile(path.join(context.library, "Test", "responses", "render-1344x768.png")));
    await expect.poll(async () => {
      const detail = await (await secondPage.request.get(`/api/image-generation/assets/${created.asset_id}`)).json();
      return detail.jobs.find(job => job.request_id === assignment.requestId)?.status;
    }).toBe("COMPLETE");
    current = await (await secondPage.request.get(`/api/image-generation/assets/${created.asset_id}`)).json();
    expect(current.jobs.find(job => job.request_id === assignment.requestId).images[0].index).toBe(0);
    const selected = await secondPage.request.post(`/api/image-generation/assets/${created.asset_id}/select`, {
      data: { expected_revision: current.revision, slot: 1, expected_assignment: assignment, render_mode: "draft" },
    });
    expect(selected.ok(), await selected.text()).toBeTruthy();
    current = await selected.json();
    const published = await secondPage.request.post(`/api/image-generation/assets/${created.asset_id}/inventory-add`, {
      data: { expected_revision: current.revision, slot: 1, expected_assignment: assignment,
        label: "E2E Lighthouse Result" },
    });
    expect(published.ok(), await published.text()).toBeTruthy();
    const inventoryAsset = (await published.json()).asset;
    expect(inventoryAsset.status).toBe("approved");
    expect((await secondPage.request.get(`/api/entity-library/assets/${inventoryAsset.asset_id}`)).ok()).toBeTruthy();

    current = await (await secondPage.request.get(`/api/image-generation/assets/${created.asset_id}`)).json();
    const secondRender = await secondPage.request.post(`/api/image-generation/assets/${created.asset_id}/generate`, {
      data: { expected_revision: current.revision, slot: 2, expected_assignment: null, render_mode: "draft" },
    });
    expect(secondRender.ok(), await secondRender.text()).toBeTruthy();
    current = await secondRender.json();
    const queuedAssignment = current.slots[1];
    const queuedTransportId = await findImageGenerationAsk(context.queue, queuedAssignment.requestId);
    const cancelled = await secondPage.request.post(`/api/image-generation/assets/${created.asset_id}/cancel`, {
      data: { expected_revision: current.revision, slot: 2, expected_assignment: queuedAssignment,
        expected_upscale_id: null, render_mode: "draft" },
    });
    expect(cancelled.ok(), await cancelled.text()).toBeTruthy();
    expect((await cancelled.json()).slots[1]).toBeNull();
    await expect(access(path.join(context.queue, "File_Proxy", "Ask", "zet", queuedTransportId)))
      .rejects.toThrow();
  } finally {
    await secondPage.close();
  }
});

async function deliverPreparedImage(queue, id, output) {
  const ask = path.join(queue, "File_Proxy", "Ask", "zet", id);
  const answer = path.join(queue, "File_Proxy", "Answer", "zet", id);
  const manifest = JSON.parse(await readFile(path.join(ask, "ask_manifest.json"), "utf8"));
  await mkdir(answer, { recursive: true });
  await writeFile(path.join(answer, "ask_manifest.json"), await readFile(path.join(ask, "ask_manifest.json")));
  await writeFile(path.join(answer, "job.json"), await readFile(path.join(ask, "job.json")));
  await writeFile(path.join(answer, manifest.expected_output), output);
  await writeFile(path.join(answer, "answer_manifest.json"), JSON.stringify({
    ask_id: id, status: "SUCCESS", expected_output: manifest.expected_output,
    worker_id: "prepared-image-generation-test", ollama_attempt_id: id,
  }));
  await writeFile(path.join(answer, "proxy_result.json"), JSON.stringify({ status: "SUCCEEDED", output_files: [
    { path: manifest.expected_output, size: output.length,
      sha256: createHash("sha256").update(output).digest("hex") },
  ] }));
}

async function findImageGenerationAsk(queue, requestId) {
  for (const state of ["Ask", "Running"]) {
    const root = path.join(queue, "File_Proxy", state, "zet");
    let folders = [];
    try { folders = await readdir(root, { withFileTypes: true }); } catch {}
    for (const folder of folders.filter(item => item.isDirectory())) {
      try {
        const manifest = JSON.parse(await readFile(path.join(root, folder.name, "ask_manifest.json"), "utf8"));
        if (manifest.ad_hoc_request_id === requestId) return manifest.ask_id;
      } catch {}
    }
  }
  throw new Error(`No prepared Image Generation ask found for ${requestId}`);
}
