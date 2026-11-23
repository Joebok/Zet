import { expect, test } from "@playwright/test";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";

test("Character template editor saves changes and preserves edits on a master conflict", async ({ page }) => {
  const reset = await page.request.post("/__test/reset");
  expect(reset.ok()).toBeTruthy();
  const context = await (await page.request.get("/__test/context")).json();
  const masterPath = path.join(context.library, "Test", "Characters", "Traveler", "Adult", "Character.md");
  const originalBytes = await readFile(masterPath);
  const original = originalBytes.toString("utf8");
  const load = await page.request.post("/api/edit-source/load", { data: {
    source_kind: "character_template", source_path: masterPath,
  } });
  expect(load.ok(), await load.text()).toBeTruthy();
  const editor = await load.json();
  const revised = editor.text.replace("Simple graphic illustration", "Prepared E2E ink and wash");
  try {
    const save = await page.request.post("/api/edit-source/save", { data: {
      editor_type: editor.editor_type, path: editor.path, text: revised, master_revision: editor.master_revision,
    } });
    expect(save.ok(), await save.text()).toBeTruthy();
    expect((await save.json()).status).toBe("SAVED");
    expect((await readFile(masterPath, "utf8"))).toContain("Prepared E2E ink and wash");

    const newerMaster = revised.replace("Prepared E2E ink and wash", "Concurrent master edit");
    await writeFile(masterPath, newerMaster, "utf8");
    const staleSave = await page.request.post("/api/edit-source/save", { data: {
      editor_type: editor.editor_type, path: editor.path,
      text: revised.replace("Traveler", "Retained draft Traveler"), master_revision: editor.master_revision,
    } });
    expect(staleSave.ok()).toBeTruthy();
    expect((await staleSave.json()).status).toBe("CONFLICT");
    expect(await readFile(masterPath, "utf8")).toContain("Concurrent master edit");

    const refreshed = await page.request.post("/api/edit-source/load", { data: {
      source_kind: "character_template", source_path: masterPath,
    } });
    expect((await refreshed.json()).text).toContain("Concurrent master edit");
  } finally {
    await writeFile(masterPath, originalBytes);
  }
});
