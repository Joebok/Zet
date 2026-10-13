import { cp, mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const source = path.join(root, "node_modules", "three");
const target = path.join(root, "zet", "web", "static", "vendor", "three");
await mkdir(path.join(target, "build"), { recursive: true });
await mkdir(path.join(target, "examples", "jsm", "controls"), { recursive: true });
for (const name of ["three.module.js", "three.core.js"]) {
  await cp(path.join(source, "build", name), path.join(target, "build", name));
}
for (const name of ["OrbitControls.js", "TransformControls.js"]) {
  await cp(path.join(source, "examples", "jsm", "controls", name), path.join(target, "examples", "jsm", "controls", name));
}
