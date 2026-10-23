# Phase-sourced Head-Image Edit
Status: complete
Related specification: approved chat plan

## Goal
Create a target-phase Head-Image Edit FRONT from another phase's locked FRONT, then use only the selected target FRONT for remaining views. Compile direct prompt instructions for generation, same-phase editing, and phase change.

## Current behavior
`LocalHeadImageEditService` inherits upload-only FRONT sourcing. `Run_Head_Image_Edit_Jobs.py` includes preservation text in all modes and conditionally includes phase rules. The dashboard has upload/paste and an Apply Phase Change checkbox. `LocalAssetStoreService.locked_assets` already resolves available same-universe publications.

## Implementation packets
### WP1 — Source contract
- Files/interfaces: `local_head_image_edit_service.py`, existing batch preview/create/source update boundary; `front_source_phase` request field and source provenance.
- Work: validate exclusive source choice, resolve same-pipeline locked FRONT, snapshot it, reject missing locks and stale choices.
- Acceptance: phase source is used only for FRONT; creation rechecks lock; uploaded and generation paths continue.
- Validation: disposable service checks.
- Status: complete

### WP2 — Dashboard source choice
- Files/interfaces: `local_asset_pipeline.js`, `index.html`, scoped CSS only if required.
- Work: alternate upload/paste and locked-phase selection under checkbox; preview lock and provide lock-first navigation.
- Acceptance: missing lock blocks creation; context changes clear choice; selected lock is visible.
- Validation: disposable browser checks.
- Status: complete

### WP3 — Direct prompt modes
- Files/interfaces: `Run_Head_Image_Edit_Jobs.py`, operation template, Youth Tsaeytte `Character.md`.
- Work: choose one FRONT mode deterministically and remove conditional prose; leave phase guidance out of other views.
- Acceptance: phase change uses one target-phase rule block; all other views use selected target FRONT.
- Validation: disposable all-view prompt compiles and text checks.
- Status: complete

### WP4 — Knowledge and regression
- Files/interfaces: affected local-character, prompt, and data-model docs.
- Work: record new source/provenance contract and results; archive plan.
- Acceptance: `npm run test:e2e` and `git diff --check`; no permanent scenario or live model run.
- Validation: commands above and final diff review.
- Status: complete

## Constraints
Preserve unrelated checkout edits, universe isolation, published lock integrity, frozen source bytes, and accepted prompt revisions. No new dependency or permanent test.

## Final results
The new batch selector resolves an available same-pipeline locked FRONT, previews it, snapshots its bytes, and saves source phase/key/ID and snapshot hash. Missing locks block creation. Uploaded replacement clears the origin. FRONT prompt compilation now selects generation, same-phase edit, or phase-change authoring; other views use selected target FRONT and exclude phase rules. Youth Tsaeytte's HEAD_EDIT text has direct instructions.

Validation: isolated service checks covered exclusivity, missing lock, snapshot, provenance, and actual source replacement. Disposable prompt compilation covered three FRONT modes and seven later views. An isolated Chromium pass covered missing-lock guidance and link, locked-image preview, batch creation, and no browser errors. `npm.cmd run test:e2e` passed all four approved scenarios (37.6s); Python and JavaScript syntax checks, template parsing, CRLF check, and `git diff --check` passed. No live image generation or permanent test was added. A first disposable compile was blocked by the development-fixture guard, then repeated successfully with isolated resource lookups. One E2E rerun found the disposable browser server still on its port; after stopping that owned server, the final run passed.
