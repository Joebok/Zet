import { expect, test } from "@playwright/test";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";

test.afterEach(async ({ page }, testInfo) => {
  if (testInfo.status !== testInfo.expectedStatus) {
    await page.request.post("/__test/retain-failure", { data: { title: testInfo.title } });
  } else {
    expect(page.__zetPageErrors ?? [], "uncaught browser exceptions").toEqual([]);
  }
});

test("Character Wizard resumes a prepared interview and publishes only after acceptance", async ({ page }) => {
  const reset = await page.request.post("/__test/reset");
  expect(reset.ok()).toBeTruthy();
  const context = await (await page.request.get("/__test/context")).json();
  const privateLibrary = path.resolve(context.library, "Test");
  const characterName = "E2E Wizard Traveler";
  const phase = "Adult";
  const sessionRoot = path.join(privateLibrary, "_state", "CharacterWizard");
  let sessionId = "";
  let completed = false;
  page.on("pageerror", error => {
    page.__zetPageErrors ??= [];
    page.__zetPageErrors.push(error.message);
  });

  try {
    await page.goto("/");
    await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
    await page.getByRole("button", { name: "Character Development" }).click();
    await page.locator("#new-menu-button").click();
    await page.locator("#new-character").click();
    const dialog = page.locator("#character-wizard");
    await expect(dialog).toBeVisible();
    await dialog.locator('[data-intake] input[name="character"]').fill(characterName);
    await dialog.locator('[data-intake] input[name="phase"]').fill(phase);
    const species = dialog.locator('[data-intake] select[name="species_id"]');
    await expect(species.locator("option").nth(1)).toBeAttached();
    await species.selectOption({ index: 1 });
    await dialog.locator('[data-intake] select[name="gender"]').selectOption("Undecided");
    await dialog.locator('[data-intake] input[name="image1"]').setInputFiles(
      path.join(context.library, "Test", "images", "traveler-reference.png"));
    await dialog.locator('[data-intake] input[name="caption1"]').fill("Full body portrait reference");
    const createdResponse = page.waitForResponse(response => response.request().method() === "POST" &&
      response.url().endsWith("/api/character-wizard"));
    await dialog.locator('[data-intake] button[type="submit"]').click();
    const created = await (await createdResponse).json();
    sessionId = created.id;
    expect(created.status).toBe("RUNNING");
    const characterPath = path.join(privateLibrary, "Characters", characterName, phase, "Character.md");
    await expect.poll(async () => {
      try { await readFile(characterPath); return true; } catch { return false; }
    }).toBe(false);

    await dialog.locator('[data-command="close"]').click();
    await page.reload();
    await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
    await page.getByRole("button", { name: "Character Development" }).click();
    await page.locator("#new-menu-button").click();
    await page.locator("#new-character").click();
    const resumed = page.locator("#character-wizard [data-resume]");
    await expect(resumed.locator(`option[value="${sessionId}"]`)).toBeAttached();
    await resumed.selectOption(sessionId);
    await expect(dialog.locator("[data-session]")).toBeVisible();

    const bodyAttempt = await waitForWizardAttempt(page, sessionId, "BODY_DESCRIPTION_FACTS");
    await deliverWizardText(context.queue, bodyAttempt.id,
      "* Adult traveler has a balanced build and a relaxed, upright silhouette.\n* The visible arms and legs are proportionate.");
    await expect.poll(async () => {
      const detail = await (await page.request.get(`/api/character-wizard/${sessionId}`)).json();
      return detail.sections?.BODY_DESCRIPTION_FACTS.status;
    }).toBe("READY");

    const headAttempt = await waitForWizardAttempt(page, sessionId, "HEAD_EDIT_FRONT_DESCRIPTION");
    await deliverWizardText(context.queue, headAttempt.id,
      "* Adult traveler has an oval face, clear eyes, and dark wavy hair ending at the shoulders.\n* The brows are gently arched.");
    await expect.poll(async () => (await (await page.request.get(`/api/character-wizard/${sessionId}`)).json()).status)
      .toBe("DRAFT");
    let draft = await (await page.request.get(`/api/character-wizard/${sessionId}`)).json();
    expect(draft.sections.BODY_DESCRIPTION_FACTS.text).toContain("balanced build");
    expect(draft.sections.HEAD_EDIT_FRONT_DESCRIPTION.text).toContain("dark wavy hair");
    expect(draft.errors).toEqual([]);
    await expect.poll(async () => {
      try { await readFile(characterPath); return true; } catch { return false; }
    }).toBe(false);

    await dialog.locator('[data-command="preview"]').click();
    await expect(dialog.locator('[data-command="accept"]')).toBeEnabled();
    const preview = await (await page.request.get(`/api/character-wizard/${sessionId}`)).json();
    expect(preview.preview_ready).toBe(true);
    expect(preview.markdown).toContain("balanced build");
    expect(preview.markdown).toContain("dark wavy hair");
    const acceptResponse = page.waitForResponse(response => response.request().method() === "POST" &&
      response.url().endsWith(`/api/character-wizard/${sessionId}/accept`));
    await dialog.locator('[data-command="accept"]').click();
    const accepted = await (await acceptResponse).json();
    expect(accepted.status).toBe("ACCEPTED");
    await expect.poll(async () => (await readFile(characterPath, "utf8")).includes("balanced build"))
      .toBe(true);
    expect(await readFile(characterPath, "utf8")).toContain("dark wavy hair");
    await expect(page.locator("#onboarding-character")).toHaveValue(characterName);
    expect(page.__zetPageErrors ?? []).toEqual([]);
    completed = true;
  } finally {
    if (completed) {
      const session = sessionId && path.resolve(sessionRoot, sessionId);
      if (session && session.startsWith(path.resolve(sessionRoot) + path.sep)) await rm(session, { recursive: true, force: true });
      const ownedCharacter = path.resolve(privateLibrary, "Characters", characterName);
      if (ownedCharacter.startsWith(privateLibrary + path.sep)) await rm(ownedCharacter, { recursive: true, force: true });
    }
  }
});

async function waitForWizardAttempt(page, id, section) {
  let attemptId;
  await expect.poll(async () => {
    const detail = await (await page.request.get(`/api/character-wizard/${id}`)).json();
    if (detail.sections?.[section]?.status !== "QUEUED") return detail.sections?.[section]?.status;
    const context = await (await page.request.get("/__test/context")).json();
    const session = JSON.parse(await readFile(path.join(context.library, "Test", "_state", "CharacterWizard", id, "session.json"), "utf8"));
    if (session.attempt?.section === section) attemptId = session.attempt.id;
    return attemptId ? section : detail.sections?.[section]?.status;
  }).toBe(section);
  await expect.poll(async () => {
    const root = path.join((await (await page.request.get("/__test/context")).json()).queue,
      "File_Proxy", "Ask", "zet", attemptId);
    try { await readFile(path.join(root, "ask_manifest.json")); return true; } catch { return false; }
  }).toBe(true);
  return { id: attemptId, section };
}

async function deliverWizardText(queue, id, text) {
  const ask = path.join(queue, "File_Proxy", "Ask", "zet", id);
  const answer = path.join(queue, "File_Proxy", "Answer", "zet", id);
  const manifest = JSON.parse(await readFile(path.join(ask, "ask_manifest.json"), "utf8"));
  const output = Buffer.from(text, "utf8");
  await mkdir(answer, { recursive: true });
  await writeFile(path.join(answer, "ask_manifest.json"), await readFile(path.join(ask, "ask_manifest.json")));
  await writeFile(path.join(answer, "job.json"), await readFile(path.join(ask, "job.json")));
  await writeFile(path.join(answer, manifest.expected_output), output);
  await writeFile(path.join(answer, "answer_manifest.json"), JSON.stringify({
    ask_id: id, status: "SUCCESS", expected_output: manifest.expected_output,
    worker_id: "prepared-character-wizard-test", ollama_attempt_id: id,
  }));
  await writeFile(path.join(answer, "proxy_result.json"), JSON.stringify({ status: "SUCCEEDED", output_files: [
    { path: manifest.expected_output, size: output.length, sha256: createHash("sha256").update(output).digest("hex") },
  ] }));
}
