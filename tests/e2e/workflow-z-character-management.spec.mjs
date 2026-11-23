import { expect, test } from "@playwright/test";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";

test("Character rename preserves assets and archive requires safe confirmation", async ({ page }) => {
  const reset = await page.request.post("/__test/reset");
  expect(reset.ok()).toBeTruthy();
  const context = await (await page.request.get("/__test/context")).json();
  const rename = async (character, phase, newName, scope) => page.request.post("/api/local/character-overview/rename", {
    data: { character, phase, new_name: newName, scope },
  });
  let currentCharacter = "Traveler";
  let currentPhase = "Adult";
  try {
    const initial = await page.request.get("/api/local/character-overview?character=Traveler&phase=Adult&universe_id=Test");
    expect(initial.ok()).toBeTruthy();

    const characterRename = await rename(currentCharacter, currentPhase, "Traveler E2E", "character");
    expect(characterRename.ok(), await characterRename.text()).toBeTruthy();
    currentCharacter = "Traveler E2E";
    const phaseRename = await rename(currentCharacter, currentPhase, "Adult E2E", "phase");
    expect(phaseRename.ok(), await phaseRename.text()).toBeTruthy();
    currentPhase = "Adult E2E";

    const overview = await page.request.get(`/api/local/character-overview?character=${encodeURIComponent(currentCharacter)}&phase=${encodeURIComponent(currentPhase)}&universe_id=Test`);
    expect(overview.ok(), await overview.text()).toBeTruthy();
    const body = await page.request.get(`/api/character-containers/body-reference?character=${encodeURIComponent(currentCharacter)}&phase=${encodeURIComponent(currentPhase)}&universe_id=Test`);
    expect(body.ok(), await body.text()).toBeTruthy();
    const bodyDetail = await body.json();
    expect(bodyDetail.scope.character).toBe(currentCharacter);
    expect(bodyDetail.scope.phase).toBe(currentPhase);
    await page.goto("/?page=onboarding&character=Traveler%20E2E&phase=Adult%20E2E&universe_id=Test");
    await expect(page.locator("#onboarding-page")).toHaveClass(/active/);
  } finally {
    if (currentPhase !== "Adult") {
      const restoredPhase = await rename(currentCharacter, currentPhase, "Adult", "phase");
      expect(restoredPhase.ok(), await restoredPhase.text()).toBeTruthy();
      currentPhase = "Adult";
    }
    if (currentCharacter !== "Traveler") {
      const restoredCharacter = await rename(currentCharacter, currentPhase, "Traveler", "character");
      expect(restoredCharacter.ok(), await restoredCharacter.text()).toBeTruthy();
    }
  }

  const characterRoot = path.join(context.library, "Test", "Characters", "Traveler");
  const containerPath = path.join(context.library, "Test", "_state", "CharacterAssetContainers",
    "Traveler", "Adult", "body-reference", "_", "container.json");
  const originalContainer = await readFile(containerPath);
  const active = JSON.parse(originalContainer.toString("utf8"));
  const candidate = Object.values(active.boards.FRONT.candidates)[0];
  expect(candidate.locked).toBe(true);
  candidate.status = "QUEUED";
  try {
    await writeFile(containerPath, JSON.stringify(active, null, 2), "utf8");
    const blocked = await page.request.delete("/api/character?character=Traveler", { data: {} });
    expect(blocked.status()).toBe(400);
    expect((await blocked.json()).detail).toContain("Wait for active image work");
  } finally {
    await writeFile(containerPath, originalContainer);
  }

  const previewRequired = await page.request.delete("/api/character?character=Traveler", { data: {} });
  expect(previewRequired.status()).toBe(409);
  const preview = (await previewRequired.json()).detail;
  expect(preview.code).toBe("IMAGE_CONFIRMATION_REQUIRED");
  expect(preview.images.length).toBeGreaterThan(0);
  expect(preview.images.every(image => image.id && image.version)).toBe(true);

  const archive = await page.request.delete("/api/character?character=Traveler", { data: {
    confirm_ids: preview.images.map(image => image.id),
    expected_versions: Object.fromEntries(preview.images.map(image => [image.id, image.version])),
    expected_phases: ["Adult"],
  } });
  expect(archive.ok(), await archive.text()).toBeTruthy();
  const result = await archive.json();
  expect(result.destination).toBeTruthy();
  await expect(readFile(path.join(characterRoot, "Adult", "Character.md"))).rejects.toThrow();
  await expect(readFile(path.join(result.destination, "Characters", "Traveler", "Adult", "Character.md")))
    .resolves.toBeTruthy();
});
