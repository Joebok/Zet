import { expect, test } from "@playwright/test";

const PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aS8kAAAAASUVORK5CYII=", "base64");

async function openInventory(page) {
  await page.goto("/");
  await page.waitForFunction(() => typeof window.activatePage === "function");
  await page.waitForFunction(() => document.body.dataset.dashboardReady === "true");
  await page.evaluate(() => window.activatePage("auxiliary-resources", { skipAutosave: true }));
  await expect(page.locator("#entity-library-search-view")).toBeVisible();
}

test("Image Inventory searches, copies a tag, keeps search state in details, and separates entity management", async ({ page }) => {
  await openInventory(page);
  const imported = await page.request.post("/api/entity-library/assets?label=Inventory+Card+Test", {
    data: PNG,
    headers: { "content-type": "image/png" },
  });
  expect(imported.ok()).toBeTruthy();
  const asset = (await imported.json()).asset;

  await page.locator("#entity-library-search").fill("Inventory Card Test");
  await page.locator("#entity-library-refresh").click();
  const card = page.locator("#entity-library-results .image-catalog-card").filter({ hasText: "Inventory Card Test" });
  await expect(card).toBeVisible();
  await expect(card.locator(".inventory-card-tag")).toHaveText(`{{LIB:ASSET:${asset.asset_id}}}`);
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await card.getByRole("button", { name: "Copy tag" }).click();
  await expect(card.getByRole("button", { name: "Copied" })).toBeVisible();
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe(`{{LIB:ASSET:${asset.asset_id}}}`);

  const preferredReference = await page.request.post("/api/entity-library/logical-references", {
    data: { reference_key: "inventory.preferred", label: "Inventory preferred", asset_id: asset.asset_id },
  });
  expect(preferredReference.ok()).toBeTruthy();
  await page.locator("#entity-library-search").fill("inventory.preferred");
  await page.locator("#entity-library-refresh").click();
  await expect(card.locator(".inventory-card-tag")).toHaveText("{{LIB:REF:inventory.preferred}}");
  await card.getByRole("button", { name: "Copy tag" }).click();
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe("{{LIB:REF:inventory.preferred}}");

  await card.getByRole("button", { name: "Details" }).click();
  await expect(page.locator("#entity-library-detail-view")).toBeVisible();
  await page.locator("#entity-library-edit-notes").fill("Unsaved note");
  await page.getByRole("button", { name: "Back to search" }).click();
  await expect(page.locator("#unsaved-changes-dialog")).toBeVisible();
  await page.locator("#unsaved-changes-dialog button[value=discard]").click();
  await expect(page.locator("#entity-library-search")).toHaveValue("inventory.preferred");

  await page.getByRole("button", { name: "Entities" }).click();
  await page.getByRole("button", { name: "Add entity" }).click();
  await page.locator("#inventory-record-form [name=name]").fill("Inventory Test Entity");
  await page.locator("#inventory-record-form [name=entity_type]").selectOption("creature");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page.locator(".inventory-organization-row").filter({ hasText: "Inventory Test Entity" })).toBeVisible();
  for (const width of [1440, 1024, 768]) {
    await page.setViewportSize({ width, height: 900 });
    await expect.poll(() => page.locator("#auxiliary-resources-page").evaluate((node) => node.scrollWidth <= node.clientWidth + 1)).toBe(true);
  }
});
