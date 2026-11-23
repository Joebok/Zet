import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import path from "node:path";

test("Inventory image edit preserves bytes and retains logical reference aliases", async ({ page }) => {
  const reset = await page.request.post("/__test/reset");
  expect(reset.ok()).toBeTruthy();
  const context = await (await page.request.get("/__test/context")).json();
  const imagePath = path.join(context.library, "Test", "images", "traveler-reference.png");
  const bytes = await readFile(imagePath);
  const entityResponse = await page.request.post("/api/entity-library/entities", { data: {
    name: "E2E Reference Subject", entity_type: "character", description: "Fixture for Inventory editing",
  } });
  expect(entityResponse.ok(), await entityResponse.text()).toBeTruthy();
  const entity = (await entityResponse.json()).entity;
  const importedResponse = await page.request.post("/api/entity-library/assets?label=E2E%20Reference&entity_ids=" + entity.entity_id, {
    headers: { "Content-Type": "image/png" }, data: bytes,
  });
  expect(importedResponse.ok(), await importedResponse.text()).toBeTruthy();
  const imported = (await importedResponse.json()).asset;
  const assetId = imported.asset_id;
  const baseline = await page.request.get(`/api/entity-library/assets/${assetId}`);
  expect(baseline.ok()).toBeTruthy();
  const original = (await baseline.json()).asset;
  const aliasResponse = await page.request.post("/api/entity-library/logical-references", { data: {
    asset_id: assetId, reference_key: "e2e-reference-legacy", label: "Prior reference name",
  } });
  expect(aliasResponse.ok(), await aliasResponse.text()).toBeTruthy();

  const update = await page.request.patch(`/api/entity-library/assets/${assetId}`, { data: {
    label: "E2E Reference Revised", notes: "Verified E2E catalog note", status: "approved",
    preferred_reference_key: "e2e-reference-current", entity_links: [{ entity_id: entity.entity_id, role: "primary_subject" }],
    set_ids: [], facets: [], tags: ["e2e", "reference"], descriptors: {},
  } });
  expect(update.ok(), await update.text()).toBeTruthy();
  const revised = (await update.json()).asset;
  expect(revised.label).toBe("E2E Reference Revised");
  expect(revised.checksum).toBe(original.checksum);
  expect(revised.logical_reference.reference_key).toBe("e2e-reference-current");

  const invalid = await page.request.patch(`/api/entity-library/assets/${assetId}`, { data: {
    label: "Must Not Commit", preferred_reference_key: "INVALID KEY!",
  } });
  expect(invalid.status()).toBe(400);
  const afterInvalid = (await (await page.request.get(`/api/entity-library/assets/${assetId}`)).json()).asset;
  expect(afterInvalid.label).toBe("E2E Reference Revised");
  expect(afterInvalid.checksum).toBe(original.checksum);
  const references = (await (await page.request.get("/api/entity-library/logical-references")).json()).references;
  expect(references.find(item => item.reference_key === "e2e-reference-current").asset_id).toBe(assetId);
  expect(references.find(item => item.reference_key === "e2e-reference-legacy").asset_id).toBe(assetId);
  await page.goto("/?page=auxiliary-resources");
  await expect(page.locator("#auxiliary-resources-page")).toHaveClass(/active/);
});
