import { expect, test } from "@playwright/test";

test.afterEach(async ({ page }, testInfo) => {
  if (testInfo.status !== testInfo.expectedStatus) {
    await page.request.post("/__test/retain-failure", { data: { title: testInfo.title } });
  } else {
    expect(page.__zetPageErrors ?? [], "uncaught browser exceptions").toEqual([]);
  }
});

test("Character workflows consume published locks and retain saved Inventory references", async ({ page }) => {
  const reset = await page.request.post("/__test/reset");
  expect(reset.ok()).toBeTruthy();
  let completed = false;
  page.on("pageerror", error => {
    page.__zetPageErrors ??= [];
    page.__zetPageErrors.push(error.message);
  });
  const character = "Traveler", phase = "Adult", query = "character=Traveler&phase=Adult";
  try {
    const seededViews = await page.request.post("/__test/seed-published-body-views");
    expect(seededViews.ok(), await seededViews.text()).toBeTruthy();
    const sourcesResponse = await page.request.get(`/api/local-asset-sources?${query}`);
    expect(sourcesResponse.ok(), await sourcesResponse.text()).toBeTruthy();
    const sources = (await sourcesResponse.json()).sources;
    const source = sources.find(item => item.pipeline === "body-reference" && item.view === "FRONT");
    expect(source?.source_key).toBeTruthy();
    expect(source?.category_key).toBeTruthy();
    expect(source.inventory_asset_id).toBeTruthy();
    const originalAsset = await page.request.get(`/api/entity-library/assets/${source.inventory_asset_id}?universe_id=Test`);
    expect(originalAsset.ok(), await originalAsset.text()).toBeTruthy();
    const original = (await originalAsset.json()).asset;

    const identityRoute = `/api/identity-keys?character=${character}&phase=${phase}`;
    const savedKey = await page.request.post(`/api/identity-keys?character=${character}&phase=${phase}`, {
      data: { source_local_key: source.category_key, label: "E2E Face and Coat", crop_percent: 64 },
    });
    expect(savedKey.ok(), await savedKey.text()).toBeTruthy();
    const key = (await savedKey.json()).identity_key;
    expect(key.label).toBe("E2E Face and Coat");
    expect(key.source_local_key).toBe(source.source_key);
    const keyLock = await page.request.put(`/api/identity-keys/${key.identity_key_id}/lock?character=${character}&phase=${phase}`, { data: { locked: true } });
    expect(keyLock.ok(), await keyLock.text()).toBeTruthy();
    const lockedKey = (await keyLock.json()).identity_key;
    expect(lockedKey.inventory_asset_id).toBeTruthy();
    const keyAssetResponse = await page.request.get(`/api/entity-library/assets/${lockedKey.inventory_asset_id}?universe_id=Test`);
    expect(keyAssetResponse.ok()).toBeTruthy();
    const keyAsset = (await keyAssetResponse.json()).asset;

    const turnaroundRows = (await (await page.request.get(`/api/turnarounds?${query}`)).json()).rows;
    const row = turnaroundRows.find(item => item.source_local_keys?.includes(source.source_key));
    expect(row, "turnaround row from the current Body-Reference lock").toBeTruthy();
    const partial = await page.request.post(`/api/turnarounds/${row.turnaround_id}/partials?${query}`, {
      data: { label: "E2E Close Details", crop_percent: 62, detection_tolerance: 50 },
    });
    expect(partial.ok(), await partial.text()).toBeTruthy();
    const partialRow = (await partial.json()).row;
    const partialSheet = partialRow.auxiliary_sheets.find(item => item.label === "E2E Close Details");
    expect(partialSheet?.status).toBe("RENDER_REVIEW");
    expect(partialRow.source_local_keys).toContain(source.source_key);
    expect(partialSheet.candidate_image_exists).toBe(true);

    const containerResponse = await page.request.get(`/api/character-containers/body-reference?${query}&universe_id=Test`);
    expect(containerResponse.ok(), await containerResponse.text()).toBeTruthy();
    let container = await containerResponse.json();
    const candidateId = container.boards.FRONT.selected_id;
    const unlocked = await page.request.post(`/api/character-containers/body-reference/views/FRONT/candidates/${candidateId}/unlock?${query}&universe_id=Test`, {
      data: { expected_revision: container.revision, expected_candidate_id: candidateId },
    });
    expect(unlocked.ok(), await unlocked.text()).toBeTruthy();
    const remainingSources = (await (await page.request.get(`/api/local-asset-sources?${query}`)).json()).sources;
    expect(remainingSources.some(item => item.category_key === source.category_key)).toBe(false);

    const keyDetail = await page.request.get(`/api/identity-keys/${key.identity_key_id}?character=${character}&phase=${phase}`);
    expect(keyDetail.ok(), await keyDetail.text()).toBeTruthy();
    expect((await keyDetail.json()).identity_key.inventory_asset_id).toBe(lockedKey.inventory_asset_id);
    const keyAssetAgain = await page.request.get(`/api/entity-library/assets/${keyAsset.asset_id}?universe_id=Test`);
    expect(keyAssetAgain.ok()).toBeTruthy();
    expect((await keyAssetAgain.json()).asset.checksum).toBe(keyAsset.checksum);
    expect(lockedKey.source_inventory_asset_id).toBe(original.asset_id);
    expect((await page.request.get(identityRoute)).ok()).toBeTruthy();
    completed = true;
  } finally {
    if (completed) {
      const cleaned = await page.request.post("/__test/reset");
      expect(cleaned.ok()).toBeTruthy();
    }
  }
});
