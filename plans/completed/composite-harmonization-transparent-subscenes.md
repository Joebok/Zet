# Composite harmonization and transparent subscenes
Status: complete
Related specification: Joe's approved implementation plan, 2026-10-14.

## Goal and desired behavior
Add `harmonize_composite` alongside the two existing assembly modes: freeze the
placed composite, ask Qwen to integrate its appearance while preserving layout,
and retain the full generated result. Keep `finish_composite` as the default.
Add `use_transparent_background=true` to subscene authoring, interview and Write
Prompt. Render continues to send the prompt exactly as entered. Unchecked follows
saved visual context; checked suppresses visible scenery without deleting inputs.

## Current behavior and impact
NarrativeAssemblyService freezes composites and restores protected subject pixels
for finishing; reference assembly sends original sources with text coordinates.
Narrative prompt synthesis and final packaging currently impose a neutral
background even when authored prose asks for transparency. Model/repository,
scene/reference/generation services and narrative.js own the affected contracts.
Documentation owners: Narrative, Prompts, Data Model, Invariants and a new ADR.

## Invariants and constraints
Preserve frozen reference order/bytes, mode provenance, retry ownership, image
selection/locks, existing modes, historical snapshots and user config.toml edits.
No production-library changes, deployment, dependencies, live rendering,
supporting pair references or permanent test additions. Transparency and artistic
improvement remain model-dependent; packaging correctness is locally verifiable.

## Luna-sized work packets
### WP1 — Preference storage
- Dependencies: none. Files: models/narrative.py; narrative_scene_service.py;
  narrative_reference_service.py (services under zet/services).
- Add strict boolean persistence/defaults and source input copying/snapshots.
- Acceptance: absent defaults true; false survives round trip/import; invalid
  types fail; non-subscene behavior unchanged.
- Validation: disposable Python checks against temporary storage.
- Status: complete. Disposable temporary-storage checks passed.

### WP2 — Background-aware interview and prompts
- Dependencies: WP1. Files: narrative_prompt_service.py,
  narrative_generation_service.py and interview contract as needed.
- Give checked transparency priority over visible environment prose while keeping
  authored context; preserve subjects, supports, lighting and camera. Remove the
  unconditional neutral-background rule; append clear RGBA/zero-alpha guidance.
- Freeze preference; fence stale interview/prompt results and distinguish legacy
  snapshots without the field. Do not change manual render text.
- Acceptance/validation: disposable request, prompt and stale-result checks.
- Status: complete. Checked/unchecked request/prompt and stale-result checks passed.

### WP3 — Harmonization backend
- Dependencies: none; implement after WP2. Files: narrative assembly/prompt/scene
  services; generation lifecycle integration as needed.
- Freeze one composite reference, retain comparison composite, omit unnecessary
  finishing masks, provide layout-preserving harmonization guidance, validate
  dimensions and retain the full result.
- Acceptance/validation: disposable temporary-image snapshot, freeze, output and
  legacy finishing checks; keep existing provenance and retry guards.
- Status: complete. Frozen-image, full-output, dimension and finishing checks passed.

### WP4 — Dashboard
- Dependencies: WP1–WP3. File: zet/web/static/narrative.js.
- Accessible subscene-only checkbox after Physical Context, boolean save/poll/
  dirty handling, Setting suppression explanation and Write Prompt guidance.
  Add mode selector/help/history/candidate labels and comparison support.
- Acceptance/validation: disposable isolated browser checks for persistence,
  polling, visibility, labels and composite comparison.
- Status: complete. Isolated Chromium checks passed, including rapid toggles
  while a PATCH was held in flight, explicit false reload and polling updates.

### WP5 — Validation and knowledge
- Dependencies: WP1–WP4. Update affected docs and ADR; run approved
  `npm.cmd run test:e2e`, disposable focused checks and `git diff --check`.
- Review final diff. Record actual results here, then archive to plans/completed.
- Status: complete. Approved baseline, focused checks, syntax and diff checks passed;
  affected knowledge and ADR 0010 updated.

## Progress, decisions and final results
- Initial inspection confirms the relevant runtime paths and the pre-existing
  config.toml modification. No live-model quality claims will be made.
- WP1–WP4 implemented sequentially with no delegation. The new preference lives in
  model defaults; absent flags in historical jobs deliberately do not match new
  target policy when applying text results. Historical prompts/candidates are not
  rewritten, and manual render dispatch remains unchanged.
- `npm.cmd run test:e2e` with verified Python 3.14: all 3 approved scenarios passed
  (29.8 seconds), using the isolated fixture library and prepared responses.
- Disposable Python checks passed: default/read/save/import/strict boolean contracts;
  checked/unchecked interview and synthesis context without source mutation;
  deterministic transparency wording and removal of neutral-background suffix;
  legacy/different-flag interview fencing and stale synthesis non-application;
  composite/source freezing, single binding, output dimensions/full-byte retention,
  comparison lookup and legacy finishing subject protection.
- Disposable Chromium check passed: default/subscene-only checkbox, actual boolean
  PATCH payloads, toggles during a held save, false persistence, polling updates,
  unchanged manual prompt bytes, all mode labels/help, prepared harmonization
  synthesis/render lifecycle, full returned image bytes, prompt history, comparison
  link and reload. No browser page errors. The driver was removed after validation;
  no permanent tests/scenarios were added. Its initial URL-interception/textarea
  assertions were corrected before the passing run; no product fix was needed.
- `node --check zet/web/static/narrative.js`, AST parsing of all six changed Python
  modules, and `git diff --check` passed. Final source/documentation diff reviewed.
- Updated Narrative, Prompts, Data Model and Invariants; added ADR 0010. Existing
  entry-point responsibilities did not move, so no code-map rewrite was necessary.
- Temporary fixture server stopped. No production-library edits, live model calls,
  deployment, dependencies or changes to config.toml were performed. Actual alpha
  fidelity, appearance integration and placement drift still require live review.
