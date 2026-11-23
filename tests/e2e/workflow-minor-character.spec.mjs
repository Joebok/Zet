import { expect, test } from "@playwright/test";

test("Minor Character workspace can be created, renamed, and safely removed", async ({ page }) => {
  const reset = await page.request.post("/__test/reset");
  expect(reset.ok()).toBeTruthy();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));

  await page.goto("/?page=minor-characters");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.locator("#mc-new-name").fill("E2E Scout");
  await page.getByRole("button", { name: "New Minor Character", exact: true }).click();
  const character = page.locator("#minor-characters-page");
  await expect(character).toContainText("E2E Scout");

  const collection = await (await page.request.get("/api/minor-characters")).json();
  const created = collection.characters.find(item => item.name === "E2E Scout");
  expect(created).toBeTruthy();
  const detail = await (await page.request.get(`/api/minor-characters/${created.character_id}`)).json();
  expect(detail.character.name).toBe("E2E Scout");
  expect(Object.keys(detail.character.boards)).toContain("STYLE");
  expect(Object.keys(detail.character.boards)).toContain("FRONT");
  const rename = await page.request.patch(`/api/minor-characters/${created.character_id}`, {
    data: { name: "E2E Scout Renamed", revision: detail.character.revision,
      template_hash: detail.character.template_hash },
  });
  expect(rename.ok(), await rename.text()).toBeTruthy();
  expect((await rename.json()).character.name).toBe("E2E Scout Renamed");
  await page.reload();
  await expect(page.locator("#minor-characters-page")).toContainText("E2E Scout Renamed");

  const beforeDelete = await (await page.request.post(`/api/minor-characters/${created.character_id}/delete-preview`)).json();
  expect(beforeDelete.protected_effects).toEqual([]);
  const removed = await page.request.delete(`/api/minor-characters/${created.character_id}`, {
    data: { revision: beforeDelete.revision, template_hash: beforeDelete.template_hash,
      confirmation_token: beforeDelete.confirmation_token, approved_effects: [] },
  });
  expect(removed.ok(), await removed.text()).toBeTruthy();
  await page.reload();
  await expect(page.locator("#minor-characters-page")).toContainText("No Minor Characters yet");
  expect((await page.request.get(`/api/minor-characters/${created.character_id}`)).status()).toBe(404);
  expect(errors).toEqual([]);
});
