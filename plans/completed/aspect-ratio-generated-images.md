# Aspect ratio sizing for generated images
Status: complete
Related specification: approved chat plan, 2026-11-03

## Goal
New generated image dimensions come from canvas aspect ratio and Draft/Final mode. Existing images and frozen retries retain their dimensions.

## Work packets
1. Narrative target sizing: scene ratio for backdrop/assembly, editable subscene ratio, legacy reads. Validate with disposable service checks.
2. Assembly geometry/transport: freeze mode-resolved dimensions through snapshots, composition and proxy. Validate both modes and retry.
3. Narrative dashboard: replace target dimensions with ratio display and mode preview. Validate in browser.
4. Other generation: remove hidden dimensions and raw-size request fallback; update callers. Validate focused APIs.
5. Repair existing S3 fixture if needed, run approved fast E2E and diff checks, update affected knowledge, archive this plan.

## Constraints
Print/export width and crop geometry stay. Do not add permanent scenarios. Do not run live AI checks.

## Progress
- Inspected current Narrative, ad hoc generation, dashboard and approved S3 paths before implementation.
- Packets 1–4 complete. Target records retain legacy pixel fields, while new jobs freeze mode-resolved dimensions. Old raw-size ad hoc retries use an internal compatibility path.
- Packet 5 complete. The existing S3 fixture now uses the derived Draft image size; no scenario was added.

## Final results
- Changed Narrative authoring, assembly composition/preview, and ad hoc generation inputs to ratio plus Draft/Final sizing. Print/export and crop controls were left intact.
- `npm run test:e2e`: 4/4 passed (43.1s) after final edits. Disposable isolated API checks verified a scene change to 16:9 yields a 2720 × 1536 Final backdrop request and assembly composite/snapshot, with an existing selection retained.
- Python compilation, JavaScript syntax checks, and `git diff --check` passed. No live model/render check ran.
