import { expect, test } from "@playwright/test";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";

const timeout = Number(process.env.ZET_LIVE_TEST_TIMEOUT_MS || 20 * 60 * 1000);

test("live Narrative final assembly synthesis and render", async ({ page }) => {
  test.skip(process.env.ZET_LIVE_TEST_ENABLED !== "1",
    "Blocked until Joe explicitly requests the live check and enables ZET_LIVE_TEST_ENABLED=1.");
  const preflight = await (await page.request.get("/__test/live-preflight")).json();
  test.skip(!preflight.ready, `Blocked by live prerequisites: ${preflight.blockers.join(" ")}`);
  await page.goto("/narrative");
  await page.waitForFunction(() => document.body.dataset.narrativeReady === "true");
  const context = await (await page.request.get("/__test/context")).json();
  const ids = context.ids;
  const root = path.dirname(context.queue);
  const scene = `/api/narrative/stories/${ids.story}/scenes/${ids.scene}`;

  for (const [target, prompt, imageName] of [
    [ids.backdrop, "A quiet pine forest path in soft daylight.", "render-1344x768.png"],
    [ids.subscene, "The traveler reaches the forest gate, full body visible.", "render-1216x832.png"],
  ]) {
    await page.goto(`/narrative?story=${ids.story}&scene=${ids.scene}&target=${target}`);
    await page.locator("#narrative-prompt").fill(prompt);
    await page.getByRole("button", { name: "Save inputs" }).click();
    await page.getByRole("button", { name: "Render 1" }).click();
    const job = await waitForJob(page, scene, target, "image", "QUEUED");
    await deliverPreparedImage(context.queue, job.id, await readFile(path.join(root, imageName)));
    await expect.poll(async () => (await getJob(page, scene, target, job.id))?.status,
      { timeout }).toBe("COMPLETE");
    await page.locator(".narrative-slot").first().getByRole("button", { name: "Select" }).click();
    await page.locator(".narrative-slot").first().getByRole("button", { name: "Lock" }).click();
  }

  await page.goto(`/narrative?story=${ids.story}&scene=${ids.scene}&target=${ids.assembly}`);
  await page.getByRole("button", { name: "Add selected image" }).click();
  await page.locator("#assembly-source").selectOption(ids.subscene);
  await page.getByRole("button", { name: "Add selected image" }).click();
  await page.getByRole("button", { name: "Write Prompt" }).click();
  const synthesis = await waitForJob(page, scene, ids.assembly, "synthesize", "QUEUED");
  await expect.poll(async () => (await getJob(page, scene, ids.assembly, synthesis.id))?.status,
    { timeout }).toBe("COMPLETE");

  await page.getByRole("button", { name: "Render 1" }).click();
  const render = await waitForJob(page, scene, ids.assembly, "image", "QUEUED");
  const ask = await waitForNarrativeAsk(context.queue, render.id, timeout);
  expect(ask.consumer).toBe("zet-narrative-scenes");
  expect(ask.render_preset).toBe("comfyui-qwen-narrative");
  await expect.poll(async () => (await getJob(page, scene, ids.assembly, render.id))?.status,
    { timeout }).toBe("COMPLETE");

  await page.locator(".narrative-slot").first().getByRole("button", { name: "Select" }).click();
  await page.locator(".narrative-slot").first().getByRole("button", { name: "Lock" }).click();
  await page.reload();
  await expect(page.locator(".narrative-slot").first()).toContainText("Locked");
  await expect(page.locator(".narrative-slot img").first()).toHaveJSProperty("naturalWidth", 1344);
  await page.goto("/narrative");
  await expect(page.locator(".narrative-story-scene img")).toHaveJSProperty("naturalWidth", 1344);
  const stories = await (await page.request.get("/api/narrative/stories?universe_id=Test")).json();
  expect(stories.find(item => item.id === ids.story)?.scenes[0].final_assembly?.target_id).toBe(ids.assembly);
});

async function targetDetail(page, scene, target) {
  return (await page.request.get(`${scene}/targets/${target}?universe_id=Test`)).json();
}

async function getJob(page, scene, target, id) {
  return (await targetDetail(page, scene, target)).jobs[id];
}

async function waitForJob(page, scene, target, kind, status) {
  let job;
  await expect.poll(async () => {
    const detail = await targetDetail(page, scene, target);
    job = Object.values(detail.jobs).filter(item => item.kind === kind).at(-1);
    return job?.status;
  }, { timeout }).toBe(status);
  return job;
}

async function waitForNarrativeAsk(queue, id, limit) {
  let manifest;
  await expect.poll(async () => {
    for (const state of ["Ask", "Running"]) {
      for (const worker of ["zet", ""]) {
        const folder = path.join(queue, "File_Proxy", state, worker, id);
        try {
          manifest = JSON.parse(await readFile(path.join(folder, "ask_manifest.json"), "utf8"));
          return manifest.ask_id;
        } catch {}
      }
    }
    return "";
  }, { timeout: Math.min(limit, 30_000) }).toBe(id);
  return manifest;
}

async function deliverPreparedImage(queue, id, output) {
  const ask = path.join(queue, "File_Proxy", "Ask", "zet", id);
  const answer = path.join(queue, "File_Proxy", "Answer", "zet", id);
  const askBytes = await readFile(path.join(ask, "ask_manifest.json"));
  const manifest = JSON.parse(askBytes.toString("utf8"));
  await mkdir(answer, { recursive: true });
  await writeFile(path.join(answer, "ask_manifest.json"), askBytes);
  await writeFile(path.join(answer, "job.json"), await readFile(path.join(ask, "job.json")));
  await writeFile(path.join(answer, manifest.expected_output), output);
  await writeFile(path.join(answer, "answer_manifest.json"), JSON.stringify({
    ask_id: id, status: "SUCCESS", expected_output: manifest.expected_output,
    worker_id: "prepared-prerequisite", ollama_attempt_id: id,
  }));
  const outputFiles = [{ path: manifest.expected_output, size: output.length,
    sha256: createHash("sha256").update(output).digest("hex") }];
  await writeFile(path.join(answer, "proxy_result.json"), JSON.stringify({ status: "SUCCESS", output_files: outputFiles }));
  await writeFile(path.join(answer, "harvest_manifest.json"), JSON.stringify({ status: "HARVESTED_FOR_EXTERNAL_CONSUMER" }));
}
