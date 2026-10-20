# Stage character views in Image Generator
Status: complete
Related specification: user-approved plan in this chat.

## Goal and current behavior
Stage the current Body/Head/Assembly/Dressing view job in Image Generator without
submitting inference or adopting results. CharacterRenderSlots.prepare_input owns
current prompts/reference recipes. AdHocImageGenerationService currently chooses
its own preset, appends reference labels, and disables prompt globals. Its board
requires unselection before ordinary Clear All.

## Desired behavior and constraints
One Stage in Image Generator button per view honors Recompile and prerequisites,
replaces generator content only after preparation succeeds, and preserves ordered
reference bytes, render profile, dimensions, checkpoint and prompt-global behavior.
Fresh generation seeds; no pipeline candidate/selection/lock changes. Four active
batch pipelines only; Minor Characters/refinement are excluded. Preserve existing
work; no new dependencies, maintained scenarios or live inference.

## Impact and knowledge owners
Focused staging service, character slot preparation/presentation, local HTTP router
and app wiring, ad hoc render payloads/dispatch, generator workspace reset, shared
character and generator JavaScript. Documentation owners: LOCAL_CHARACTERS,
DASHBOARD_UI, PROMPTS and CODE_MAP. Universe isolation, ordered bindings, immutable
locks and queue ownership remain required. Existing saved jobs keep old defaults.

## Luna-sized work packets
### WP1 — Prepare current view inputs
- Dependencies: none. Files: render_slot_service.py; image_generator_staging_service.py.
- Reuse current input preparation under the run lock; validate complete temporary
  snapshots and export prompt, dimensions, configuration and ordered image bytes.
- Acceptance: same inputs as Generate; no candidate allocation or inference.
- Validation: disposable isolated service/input comparisons.
- Status: complete.

### WP2 — Preserve render behavior
- Dependencies: WP1. File: ad_hoc_image_generation_service.py.
- Validate optional render_config; preserve reference metadata, preset/checkpoint,
  globals policy and label-appending policy through saved jobs and Retry.
- Acceptance: ordinary ad hoc defaults unchanged; staged compilation matches.
- Validation: disposable prepared-request/graph comparisons at matched seeds.
- Status: complete.

### WP3 — Replace workspace through service/API
- Dependencies: WP1/WP2. Files: image_generation_workspace_service.py;
  local_character_asset_pipeline_router.py; web/app.py.
- Add POST view /image-generation-stage and atomic deselect/clear after validation.
- Acceptance: invalid preparation preserves board; detached answers cannot refill.
- Validation: disposable API and workspace checks, including universe ownership.
- Status: complete.

### WP4 — Browser handoff
- Dependencies: WP3. Files: local_asset_pipeline.js; zet.js.
- Add per-view action and shared handoff; clear old generator/reconstruction/true-up
  content and browser persistence; populate mode/inputs; persist and navigate.
- Acceptance: repeated staging/reload works; no inference; async context fenced.
- Validation: disposable isolated Playwright browser checks and node --check.
- Status: complete.

### WP5 — Validate/document
- Dependencies: WP1–WP4. Update affected knowledge, record outcomes and archive.
- Validation: npm.cmd run test:e2e; Python 3 AST checks; node --check; git diff --check;
  final diff review. No permanent tests or new scenarios.
- Status: complete.

## Progress and decisions
- Python 3 verified with python3; workspace clean at implementation start.
- Reused current-view preparation under the run lock; temporary copies are exported
  as ordered data URLs. Invalid preparation never clears the generator board.
- Optional render_config is additive in browser/job payloads. Source preset,
  checkpoint, prompt-document formatting, globals policy and binding metadata are
  retained; ordinary ad hoc defaults and historical retry defaults remain intact.
- Staging clears selection and board bindings atomically, preserving job history.
  Browser reset includes inventory association, reconstruction/true-up drafts and
  legacy reference persistence. Generator count is retained, and rendering stays
  explicit. Mode changes/other entry workflows clear source render settings.
- An asynchronous browser check exposed a disabled button after returning to its
  source view. Restoring its eligibility in finally fixed the issue; the same
  test now also verifies late navigation responses and upload reads cannot apply.
- DATA_MODEL also required an additive-field note; no migration or ADR was needed.

## Final results
- All five work packets complete. No pipeline candidate allocation, selection/lock
  changes, automatic result adoption, new dependencies or maintained tests.
- npm.cmd run test:e2e: 4 approved scenarios passed (final run 45.9s).
- Disposable backend checks: all 32 view prompt/reference inputs match Generate;
  8 matched-seed FRONT/BACK graphs match after normalizing output/input filenames.
  Uploaded Head FRONT, run spec/state immutability, invalid views/references/limits,
  foreign-universe rejection, selected/running slot detachment, no submission on
  staging and Retry configuration/seed retention passed.
- Disposable Chromium checks: all four pipeline buttons, both modes, replacement,
  reference metadata/byte persistence on reload, explicit Generate, source return,
  navigation cancellation and delayed upload fences passed without page errors.
- node --check: both changed JS files passed. Python 3 AST: all six changed/new
  Python files passed. git diff --check and final diff review passed.
- Screenshots and disposable scripts are under ignored test-results/. No live AI
  execution or production-library changes; rendered artistic quality is unverified.
