# Narrative canvas sizing
Status: complete

## Goal and current behavior
New targets ignore scene canvas: subscenes use 1216x832 and backdrops/assemblies
use 1344x768. Default new scenes to 4:3 and derive new target dimensions from
the scene ratio near Qwen Image 2.1's 2048-squared pixel budget.

## Impact and constraints
Models own new-scene defaults; a shared service owns sizing; scene/reference
services own target creation. Preserve saved dimensions, explicit creation
overrides, imported subscene inputs, frozen jobs and existing compositions.
Keep legacy missing-canvas reads at 16:9. No schema migration, dependencies,
permanent tests, live AI calls or normal-library writes.
Documentation owners: Narrative component and data model. Existing code-map
ownership and architecture/invariants remain unchanged.

## Luna sized work packets
### WP1 — Canvas policy and creation
- Dependencies: none.
- Files: models/narrative.py, services/narrative_canvas_service.py,
  services/narrative_scene_service.py, services/narrative_reference_service.py,
  repositories/narrative_repository.py.
- Use official presets for standard ratios; calculate other ratios near the
  same area, round to multiples of 32 and respect 256–4096 bounds. Validate
  supplied scene ratios. Apply to new targets and linked backdrops only.
- Acceptance: 1:1 -> 2048x2048; new default 4:3 -> 2400x1792;
  portrait/custom ratios valid; saved dimensions and imported inputs preserved.
- Validation: disposable private service checks; approved fast E2E baseline.
- Status: complete.

### WP2 — Documentation and verification
- Dependencies: WP1.
- Files: Docs/COMPONENTS/NARRATIVE.md, Docs/DATA_MODEL.md, this plan.
- Repair tests/e2e/server.py fixture dimensions to match its existing prepared
  response images; preserve scenario purpose and coverage.
- Document policy, compatibility and actual validation; inspect final diff.
- Acceptance: observed results recorded, unrelated working changes preserved.
- Validation: npm.cmd run test:e2e; git diff --check.
- Status: complete.

## Risks and alternatives
4.2MP increases render cost relative to former defaults. Extreme ratios need a
smaller pixel budget to fit the existing dimension limits. Malformed ratios
must produce a useful validation error instead of silently selecting landscape.
Official presets: https://github.com/QwenLM/Qwen-Image-2.1#supported-aspect-ratios

## Validation results
Disposable temporary-library service checks passed: standard/equivalent ratios,
custom/portrait/extreme ratios, invalid ratio rejection, all three target kinds,
saved-dimension preservation after changing canvas, explicit creation overrides,
legacy missing-canvas reads and linked backdrops. Changed Python AST parsing passed.
S1/S3 are maintained workflow regressions; the new sizing checks do not expand
the approved scenarios. Initial fast E2E run: three passed, Narrative assembly
failed because its prepared 1344x768 response no longer matched the initial
canvas. Repaired fixture creation to specify its prepared image dimensions
explicitly for all three kinds, retaining existing fast/live scenario purpose.
Full approved fast baseline rerun passed: `npm.cmd run test:e2e`, four scenarios,
40.8 seconds. Additional disposable checks passed imported-subscene source-size
preservation and invalid scene-save rejection without overwriting the old canvas.
`git diff --check` passed; final diff reviewed with pre-existing opacity changes
preserved. No permanent tests, dependencies, live AI calls or production data
writes were added. Live render performance/quality at 4.2MP remains unverified.

## Final results
New scenes default to 4:3. Shared canvas sizing initializes new subscenes,
backdrops, linked backdrops and assemblies near 4.2MP. Existing records and copied
subscene dimensions remain unchanged. Narrative/data-model knowledge updated;
the test fixture explicitly retains its prepared response sizes. No unresolved
implementation blockers.
