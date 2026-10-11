import { cp, readdir, rm } from "node:fs/promises";
import { resolve } from "node:path";

const projectRoot = resolve("test-results", "dashboard-browser-project");
const pristineProjectRoot = resolve(projectRoot, ".pristine-project");

export async function restorePristineProjectState() {
  const pristineNames = await readdir(pristineProjectRoot);
  const preserve = new Set([".pristine-project", ".pristine-scenes"]);
  for (const name of await readdir(projectRoot)) {
    if (!preserve.has(name) && !pristineNames.includes(name)) {
      await rm(resolve(projectRoot, name), { recursive: true, force: true });
    }
  }
  for (const name of pristineNames) {
    const source = resolve(pristineProjectRoot, name);
    const destination = resolve(projectRoot, name);
    await rm(destination, { recursive: true, force: true });
    await cp(source, destination, { recursive: true, force: true });
  }
}

export async function restorePristineScene(page, storySlug, sceneSlug) {
  const fixturePath = resolve(
    "test-results",
    "dashboard-browser-project",
    ".pristine-scenes",
    storySlug,
    `${sceneSlug}.scene.json`,
  );
  const currentPath = resolve(
    "test-results",
    "dashboard-browser-project",
    "Stories",
    storySlug,
    `${sceneSlug}.scene.json`,
  );
  await cp(fixturePath, currentPath);
}
