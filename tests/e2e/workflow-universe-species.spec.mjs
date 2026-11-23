import { expect, test } from "@playwright/test";

test("universe style and species settings persist with revision fencing", async ({ page }) => {
  const reset = await page.request.post("/__test/reset");
  expect(reset.ok()).toBeTruthy();
  const created = await page.request.post("/api/universes", { data: {
    name: "E2E Settings Universe", canonical_art_style: "Ink and wash", environmental_art_style: "Soft painted backgrounds",
  } });
  expect(created.ok(), await created.text()).toBeTruthy();
  const universe = (await created.json()).universe;
  expect(universe.universe_id).toBeTruthy();

  const changed = await page.request.patch(`/api/universes/${universe.universe_id}`, { data: {
    canonical_art_style: "Graphic ink with muted watercolor",
    environmental_art_style: "Layered forest watercolor",
  } });
  expect(changed.ok(), await changed.text()).toBeTruthy();
  expect((await (await page.request.get(`/api/universes/${universe.universe_id}`)).json()).universe.canonical_art_style)
    .toBe("Graphic ink with muted watercolor");

  const catalogResponse = await page.request.get(`/api/species?universe_id=${universe.universe_id}`);
  expect(catalogResponse.ok()).toBeTruthy();
  const catalog = await catalogResponse.json();
  const entry = { label: "E2E Marsh Folk", aliases: ["Marshkin"], body_reference: {
    positive: ["Webbed hands and broad feet"], negative: ["Human ears"], view_instructions: {},
  } };
  const saved = await page.request.put(`/api/species?universe_id=${universe.universe_id}`, { data: {
    revision: catalog.revision, id: "e2e-marsh-folk", entry, create: true,
  } });
  expect(saved.ok(), await saved.text()).toBeTruthy();
  expect((await saved.json()).species["e2e-marsh-folk"].label).toBe(entry.label);
  const stale = await page.request.put(`/api/species?universe_id=${universe.universe_id}`, { data: {
    revision: catalog.revision, id: "e2e-marsh-folk", entry, create: false,
  } });
  expect(stale.status()).toBe(409);

  await page.goto("/?page=universes");
  await expect(page.locator("#universes-page")).toContainText("E2E Settings Universe");
});
