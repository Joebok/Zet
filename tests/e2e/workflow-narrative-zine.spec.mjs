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

test("Narrative zine assigns a finished source and regenerates a printable layout", async ({ page }) => {
  expect((await page.request.post("/__test/reset")).ok()).toBeTruthy();
  const context = await (await page.request.get("/__test/context")).json();
  const { story, scene, backdrop, assembly } = context.ids;
  const sceneUrl = `/api/narrative/stories/${story}/scenes/${scene}`;
  const targetUrl = id => `${sceneUrl}/targets/${id}?universe_id=Test`;
  const image = await readFile(path.join(resultsRoot, "narrative-e2e", "fast", "render-1344x768.png"));
  const assemblyImage = await readFile(path.join(resultsRoot, "narrative-e2e", "fast", "render-1184x896.png"));
  let completed = false;
  page.on("pageerror", error => {
    page.__zetPageErrors ??= [];
    page.__zetPageErrors.push(error.message);
  });
  try {
    const backdropPrompt = await page.request.patch(targetUrl(backdrop), { data: {
      prompt: "A forest gate in soft daylight.", visual_overrides: { style: "Simple graphic illustration" },
    } });
    expect(backdropPrompt.ok(), await backdropPrompt.text()).toBeTruthy();
    const sourceRender = await startRender(page, sceneUrl, backdrop);
    await deliver(context.queue, sourceRender.image_job_id, image);
    await expect.poll(async () => (await target(page, targetUrl, backdrop)).candidates[sourceRender.candidate_id]?.status).toBe("COMPLETE");

    const patched = await page.request.patch(targetUrl(assembly), { data: {
      assembly_mode: "finish_composite", layers: [{ target_id: backdrop, candidate_id: sourceRender.candidate_id,
        role: "base", fit: "cover", cutout: "opaque", x: 0.5, y: 0.5, scale: 1, z: 0, opacity: 1, visible: true, strokes: [] }],
      prompt: "A traveler arrives at a forest gate.", visual_overrides: { style: "Simple graphic illustration" },
    } });
    expect(patched.ok(), await patched.text()).toBeTruthy();
    const assemblyRender = await startRender(page, sceneUrl, assembly);
    await deliver(context.queue, assemblyRender.image_job_id, assemblyImage);
    await expect.poll(async () => (await target(page, targetUrl, assembly)).candidates[assemblyRender.candidate_id]?.status).toBe("COMPLETE");
    const locked = await page.request.post(`${sceneUrl}/targets/${assembly}/candidates/${assemblyRender.candidate_id}?universe_id=Test`, {
      data: { action: "lock" },
    });
    expect(locked.ok(), await locked.text()).toBeTruthy();
    const sourcesResponse = await page.request.get(`/api/zines/story-scenes/${story}`);
    expect(sourcesResponse.ok()).toBeTruthy();
    const sources = (await sourcesResponse.json()).scenes;
    expect(sources).toHaveLength(1);
    const [source] = sources;
    expect(source.tag).toContain(assemblyRender.candidate_id);
    const inputHash = createHash("sha256").update(await readFile(source.image_path)).digest("hex");

    await page.goto(`/?page=zine&workspace=story&story_slug=${story}&scene_slug=${scene}&universe_id=Test`);
    await expect(page.locator("#zine-page")).toBeVisible();
    await page.locator("#zine-story-select").selectOption(story);
    await page.locator("#zine-fill-story").click();
    await expect(page.locator("#zine-front")).toHaveValue(source.tag);
    await page.locator("#zine-name").fill("E2E Forest Zine");
    for (const slot of ["front", "page-1", "page-3", "page-5", "back"]) {
      await page.locator(`#zine-${slot}`).fill(source.tag);
    }
    await page.locator("#zine-save").click();
    await expect(page.locator("#zine-message")).toContainText("Created zine");
    const slug = "E2E-Forest-Zine";
    let document = await getZine(page, slug);
    expect(document.metadata.slots).toMatchObject({ front: source.tag, page_1: source.tag, page_3: source.tag, page_5: source.tag, back: source.tag });
    expect(document.zine.image_exists).toBe(true);
    const zinePath = document.zine.image_path;
    const firstLayout = await readFile(zinePath);
    const firstHash = createHash("sha256").update(firstLayout).digest("hex");
    const dimensions = await imageDimensions(firstLayout);
    expect(dimensions.width).toBeGreaterThan(1000);
    expect(dimensions.height).toBeGreaterThan(700);
    await expect(page.locator("#zine-preview")).toHaveAttribute("src", /.+/);

    await page.reload();
    await expect(page.locator("#zine-name")).toHaveValue("E2E Forest Zine");
    await expect(page.locator("#zine-page-1")).toHaveValue(source.tag);
    document = await getZine(page, slug);
    expect(document.metadata.slots.page_1).toBe(source.tag);
    await page.locator("#zine-regenerate").click();
    await expect(page.locator("#zine-message")).toContainText("Regenerated zine");
    const regenerated = await readFile(zinePath);
    expect(createHash("sha256").update(regenerated).digest("hex")).toBe(firstHash);
    expect(await imageDimensions(regenerated)).toEqual(dimensions);
    expect(createHash("sha256").update(await readFile(source.image_path)).digest("hex")).toBe(inputHash);
    completed = true;
  } finally {
    if (completed) expect((await page.request.post("/__test/reset")).ok()).toBeTruthy();
  }
});

async function target(page, url, id) {
  const response = await page.request.get(url(id));
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

async function startRender(page, sceneUrl, targetId) {
  const response = await page.request.post(`${sceneUrl}/targets/${targetId}/jobs?universe_id=Test`, {
    data: { action: "render", count: 1, render_mode: "draft" },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  let job, candidate;
  await expect.poll(async () => {
    const detailResponse = await page.request.get(`${sceneUrl}/targets/${targetId}?universe_id=Test`);
    const detail = await detailResponse.json();
    job = Object.values(detail.jobs).filter(item => item.kind === "render").at(-1);
    candidate = detail.candidates[job?.candidate_ids?.[0]];
    return candidate?.status;
  }).toBe("QUEUED");
  return { candidate_id: candidate.id, image_job_id: candidate.job_id };
}

async function deliver(queue, id, output) {
  const ask = path.join(queue, "File_Proxy", "Ask", "zet", id);
  const answer = path.join(queue, "File_Proxy", "Answer", "zet", id);
  const manifestBytes = await readFile(path.join(ask, "ask_manifest.json"));
  const manifest = JSON.parse(manifestBytes.toString("utf8"));
  await mkdir(answer, { recursive: true });
  await writeFile(path.join(answer, "ask_manifest.json"), manifestBytes);
  await writeFile(path.join(answer, "job.json"), await readFile(path.join(ask, "job.json")));
  await writeFile(path.join(answer, manifest.expected_output), output);
  await writeFile(path.join(answer, "answer_manifest.json"), JSON.stringify({ ask_id: id, status: "SUCCESS",
    expected_output: manifest.expected_output, worker_id: "prepared-narrative-zine-test", ollama_attempt_id: id }));
  await writeFile(path.join(answer, "proxy_result.json"), JSON.stringify({ status: "SUCCEEDED", output_files: [
    { path: manifest.expected_output, size: output.length, sha256: createHash("sha256").update(output).digest("hex") },
  ] }));
}

async function getZine(page, slug) {
  const response = await page.request.get(`/api/zines/${slug}`);
  expect(response.ok(), await response.text()).toBeTruthy();
  return (await response.json()).document;
}

async function imageDimensions(bytes) {
  expect(bytes.toString("ascii", 1, 4)).toBe("PNG");
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
}
