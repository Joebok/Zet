import { expect, test } from "@playwright/test";
import { createHash } from "node:crypto";
import { spawn } from "node:child_process";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import net from "node:net";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { resultsRoot } from "./results-path.mjs";

test.afterEach(async ({ page }, testInfo) => {
  if (testInfo.status !== testInfo.expectedStatus) {
    await page.request.post("/__test/retain-failure", { data: { title: testInfo.title } }).catch(() => {});
  } else {
    expect(page.__zetPageErrors ?? [], "uncaught browser exceptions").toEqual([]);
  }
});

test("Character recovery resumes queued work and fences an old retry answer", async ({ page }) => {
  const fixtureRoot = await mkdtemp(path.join(resultsRoot, "recovery-fixture-"));
  const port = await availablePort();
  const baseUrl = `http://127.0.0.1:${port}`;
  let server;
  let passed = false;
  try {
    server = await startServer(fixtureRoot, port, false);
    await waitForServer(baseUrl, server);
    const context = await jsonGet(baseUrl, "/__test/context");
    const query = "character=Traveler&phase=Adult&universe_id=Test";
    const containerUrl = `/api/character-containers/body-reference?${query}`;
    const viewUrl = `/api/character-containers/body-reference/views/FRONT`;
    let detail = await jsonGet(baseUrl, containerUrl);
    const queued = await postJson(baseUrl, `${viewUrl}/generate?${query}`, {
      count: 1, render_mode: "draft", expected_revision: detail.revision,
    });
    const candidateId = queued.boards.FRONT.slots.find(id => id && !detail.boards.FRONT.slots.includes(id));
    let candidate = queued.boards.FRONT.candidates[candidateId];
    expect(candidate.status).toBe("QUEUED");
    expect(candidate.attempt_id).toBeTruthy();
    const originalAsk = candidate.ask_id;
    const originalAttempt = candidate.attempt_id;
    expect(await readFile(path.join(context.queue, "File_Proxy", "Ask", "zet", originalAsk, "ask_manifest.json"))).toBeTruthy();

    await stopServer(server);
    server = await startServer(fixtureRoot, port, true);
    await waitForServer(baseUrl, server);
    detail = await jsonGet(baseUrl, containerUrl);
    candidate = detail.boards.FRONT.candidates[candidateId];
    expect(candidate.status).toBe("QUEUED");
    expect(candidate.attempt_id).toBe(originalAttempt);
    expect(candidate.ask_id).toBe(originalAsk);
    const preparedImage = await imageForRequest(candidate.render_request.settings, context.library);
    await deliver(context.queue, originalAsk, preparedImage);
    await expect.poll(async () => (await jsonGet(baseUrl, containerUrl)).boards.FRONT.candidates[candidateId]?.status).toBe("COMPLETE");
    detail = await jsonGet(baseUrl, containerUrl);
    candidate = detail.boards.FRONT.candidates[candidateId];
    expect(candidate.attempt_id).toBe(originalAttempt);
    expect(candidate.attempt_number).toBe(1);
    const recoveredHash = await imageHash(baseUrl, viewUrl, query, candidateId);
    expect(await imageHash(baseUrl, viewUrl, query, candidateId)).toBe(recoveredHash);

    const secondQueued = await postJson(baseUrl, `${viewUrl}/generate?${query}`, {
      count: 1, render_mode: "draft", expected_revision: detail.revision,
    });
    const retryCandidateId = secondQueued.boards.FRONT.slots.find(id => id && !detail.boards.FRONT.slots.includes(id));
    candidate = secondQueued.boards.FRONT.candidates[retryCandidateId];
    const failedAttempt = candidate.attempt_id;
    const failedAsk = candidate.ask_id;
    await deliver(context.queue, failedAsk, null, true);
    await expect.poll(async () => (await jsonGet(baseUrl, containerUrl)).boards.FRONT.candidates[retryCandidateId]?.status).toBe("FAILED");
    detail = await jsonGet(baseUrl, containerUrl);
    const retried = await postJson(baseUrl,
      `/api/character-containers/body-reference/views/FRONT/candidates/${retryCandidateId}/retry?${query}`,
      { expected_revision: detail.revision });
    candidate = retried.boards.FRONT.candidates[retryCandidateId];
    const currentAttempt = candidate.attempt_id;
    const currentAsk = candidate.ask_id;
    expect(currentAttempt).not.toBe(failedAttempt);
    expect(currentAsk).not.toBe(failedAsk);
    expect(candidate.status).toBe("QUEUED");

    await deliver(context.queue, failedAsk, preparedImage);
    await delay(300);
    detail = await jsonGet(baseUrl, containerUrl);
    candidate = detail.boards.FRONT.candidates[retryCandidateId];
    expect(candidate.status).toBe("QUEUED");
    expect(candidate.attempt_id).toBe(currentAttempt);
    expect(candidate.ask_id).toBe(currentAsk);
    expect(candidate.image_path).toBeFalsy();

    const retryImage = await imageForRequest(candidate.render_request.settings, context.library);
    await deliver(context.queue, currentAsk, retryImage);
    await expect.poll(async () => (await jsonGet(baseUrl, containerUrl)).boards.FRONT.candidates[retryCandidateId]?.status).toBe("COMPLETE");
    detail = await jsonGet(baseUrl, containerUrl);
    candidate = detail.boards.FRONT.candidates[retryCandidateId];
    expect(candidate.attempt_id).toBe(currentAttempt);
    expect(candidate.attempt_number).toBe(2);
    expect(await imageHash(baseUrl, viewUrl, query, retryCandidateId)).toBe(createHash("sha256").update(retryImage).digest("hex"));
    passed = true;
  } finally {
    if (server) await stopServer(server);
    if (passed) await rm(fixtureRoot, { recursive: true, force: true });
  }
});

async function startServer(fixtureRoot, port, resume) {
  const args = ["-B", "tests/e2e/server.py", "--mode", "fast", "--port", String(port),
    "--fixture-root", fixtureRoot];
  if (resume) args.push("--resume-fixtures");
  const child = spawn(process.env.ZET_TEST_PYTHON || "python3", args, {
    cwd: process.cwd(), env: process.env, stdio: ["ignore", "pipe", "pipe"], windowsHide: true,
  });
  child.startupOutput = "";
  child.stdout.on("data", chunk => { child.startupOutput += chunk.toString(); });
  child.stderr.on("data", chunk => { child.startupOutput += chunk.toString(); });
  child.once("error", error => { child.startupError = error; });
  return child;
}

async function stopServer(child) {
  if (child.exitCode !== null || child.signalCode !== null) return;
  child.kill();
  await Promise.race([
    new Promise(resolve => child.once("exit", resolve)),
    delay(8000).then(() => { throw new Error("Recovery fixture server did not stop."); }),
  ]);
}

async function waitForServer(baseUrl, child) {
  const deadline = Date.now() + 20_000;
  let lastError;
  while (Date.now() < deadline) {
    if (child.exitCode !== null || child.startupError) {
      throw new Error(`Recovery fixture server exited during startup (${child.exitCode}): ${child.startupError || child.startupOutput}`);
    }
    try {
      const response = await fetch(`${baseUrl}/api/context`);
      if (response.ok) return;
    } catch (error) {
      lastError = error;
    }
    await delay(150);
  }
  throw new Error(`Recovery fixture server did not become ready: ${lastError || "startup timeout"}\n${child.startupOutput}`);
}

async function availablePort() {
  const socket = net.createServer();
  await new Promise((resolve, reject) => socket.once("error", reject).listen(0, "127.0.0.1", resolve));
  const { port } = socket.address();
  await new Promise(resolve => socket.close(resolve));
  return port;
}

async function jsonGet(baseUrl, url) {
  const response = await fetch(`${baseUrl}${url}`);
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}

async function postJson(baseUrl, url, data) {
  const response = await fetch(`${baseUrl}${url}`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}

async function imageForRequest(settings, library) {
  const files = ["render-1344x768.png", "render-1216x832.png", "render-1184x896.png", "render-2720x1536.png", "render-832x1248.png"];
  for (const filename of files) {
    const bytes = await readFile(path.join(resultsRoot, "narrative-e2e", "fast", filename));
    if (bytes.readUInt32BE(16) === settings.width && bytes.readUInt32BE(20) === settings.height) return bytes;
  }
  const responseImage = path.join(library, "Test", "images", "traveler-reference.png");
  const fallback = await readFile(responseImage);
  if (fallback.readUInt32BE(16) === settings.width && fallback.readUInt32BE(20) === settings.height) return fallback;
  throw new Error(`No prepared response matches frozen sizing ${settings.width}x${settings.height}.`);
}

async function deliver(queue, id, output, failed = false) {
  const ask = path.join(queue, "File_Proxy", "Ask", "zet", id);
  const answer = path.join(queue, "File_Proxy", "Answer", "zet", id);
  const manifestBytes = await readFile(path.join(ask, "ask_manifest.json"));
  const manifest = JSON.parse(manifestBytes.toString("utf8"));
  await mkdir(answer, { recursive: true });
  await writeFile(path.join(answer, "ask_manifest.json"), manifestBytes);
  await writeFile(path.join(answer, "job.json"), await readFile(path.join(ask, "job.json")));
  const outputFiles = [];
  if (output) {
    await writeFile(path.join(answer, manifest.expected_output), output);
    outputFiles.push({ path: manifest.expected_output, size: output.length,
      sha256: createHash("sha256").update(output).digest("hex") });
  }
  await writeFile(path.join(answer, "answer_manifest.json"), JSON.stringify({ ask_id: id,
    status: failed ? "ERROR" : "SUCCESS", expected_output: manifest.expected_output,
    error_message: failed ? "Prepared recovery failure" : "", worker_id: "prepared-recovery-test", ollama_attempt_id: id }));
  await writeFile(path.join(answer, "proxy_result.json"), JSON.stringify({
    status: failed ? "FAILED" : "SUCCEEDED", output_files: outputFiles,
  }));
}

async function imageHash(baseUrl, viewUrl, query, candidateId) {
  const response = await fetch(`${baseUrl}${viewUrl}/candidates/${candidateId}/image?${query}`);
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return createHash("sha256").update(Buffer.from(await response.arrayBuffer())).digest("hex");
}
