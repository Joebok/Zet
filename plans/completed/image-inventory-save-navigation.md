# Reliable image inventory saving and navigation
Status: active
Related issue/specification: user report in the current task

## Goal
Make image detail edits stable during loading, saving, navigation, and background image jobs. Persist editor fields in one atomic request, refresh search after edits, and preserve old logical reference aliases when changing the preferred key.

## Current behavior
`EntityLibraryService.get_asset` obtains one asset by building the full `list_assets` result, which synchronizes pipeline images. The browser saves metadata, two descriptors, and a logical reference through separate sequential requests, then fetches the image detail again. Editor fields remain active during requests; detail loads can finish out of order. Rebuilding metadata selectors clears selected entity/set options. Search cards are not refreshed when the preferred key changes. `catalog.sqlite3` is schema version 2 and has a backup-on-upgrade initialization path.

## Desired behavior
Image detail reads are targeted; editor changes commit atomically; latest selection wins; fields are disabled with status during load/save; navigation shares any in-flight save; errors preserve drafts; search refreshes when returning from details. A stored preferred reference controls the displayed tag while previous keys remain active aliases.

## Invariants and constraints
- `catalog.sqlite3` is authoritative; preserve universe binding and existing archive/usage protections.
- Use the existing schema backup workflow and reject newer unsupported schema versions.
- No new maintained tests or coverage expansion without separate approval. Use disposable diagnostic checks and the approved E2E baseline.
- Keep existing working-tree changes and exclude unrelated cleanup.

## Implementation steps
### WP1 — Targeted image detail reads
- Dependencies: none.
- Files/interfaces: `zet/services/entity_library_service.py`.
- Work: query and assemble one asset's existing detail payload without calling `list_assets` or pipeline discovery; share row-building helpers where useful.
- Acceptance: detail and missing-image responses retain current shapes/meaning without scanning unrelated images.
- Validation: disposable catalog diagnostic and source/caller inspection.
- Status: complete. Direct detail queries assemble the prior payload; no pipeline synchronization or unrelated inventory listing occurs on detail reads.

### WP2 — Persist preferred reference
- Dependencies: WP1.
- Files/interfaces: `zet/repositories/entity_library_repository.py`, `zet/services/entity_library_service.py`.
- Work: migrate catalog schema 2 to 3 with backup, explicit migration commit, and integrity check; backfill approved assets with their currently displayed first active reference. Store the selected active reference per asset; update it on editor preference changes, preserve aliases, transfer it during replacement, and fall back alphabetically when a preferred reference is reassigned or deactivated.
- Acceptance: migration preserves current display behavior and is safely repeatable; changing/clearing preference updates selection without breaking old keys; cross-asset key collisions are rejected by editor saves.
- Validation: disposable migration, reference-selection, replacement, and reassignment diagnostics.
- Status: complete. Schema 3 migration/backfill and explicit preference behavior were verified with disposable catalogs; reference aliases remain active and replacement transfers the preferred key.

### WP3 — Atomic editor update and one reconciliation
- Dependencies: WP1–WP2.
- Files/interfaces: `zet/services/entity_library_service.py`, `zet/app.py`, `zet/web/app.py`.
- Work: extend the existing asset PATCH with optional descriptor and preferred-key fields; update metadata, links, descriptors, and reference preference in one transaction. Preserve omitted values and existing API response shape. Refresh usages once before protection checks; invalidate summaries and reconcile the derived index once after commit. Surface post-commit index errors as refresh warnings while returning the saved canonical asset.
- Acceptance: invalid fields roll back the entire edit; successful saves use one request, transaction, and reconciliation; existing PATCH consumers remain compatible.
- Validation: disposable rollback, success, and post-commit reconciliation failure diagnostics.
- Status: complete. Editor fields are accepted in one catalog transaction; invalid changes roll back, while post-commit index failures are returned as refresh warnings.

### WP4 — Race-safe editor state and navigation
- Dependencies: WP3.
- Files/interfaces: `zet/web/static/zet.js`, `zet/web/templates/index.html`.
- Work: add visible editor status and disable mutating controls during load/save; generation-guard detail loads and asynchronous prompt drafts. Capture one immutable save payload and share the pending save promise with navigation guards. Apply the canonical PATCH response directly and update the saved baseline without another GET. Preserve selected entity/set values when rebuilding options. Keep drafts and block navigation on errors.
- Acceptance: latest image selection wins; saved text does not revert; navigation waits for one save; errors retain recoverable drafts; metadata refresh does not create dirty state.
- Validation: disposable delayed-response/failure diagnostics and browser inspection.
- Status: complete. Editor requests are generation-guarded, controls are disabled during load/save, and navigation waits for the shared save promise.

### WP5 — Refresh search after editing
- Dependencies: WP4.
- Files/interfaces: `zet/web/static/zet.js`.
- Work: mark search results stale on successful saves and refresh them when returning to Search, preserving filters/page offset and guarding against stale response ordering. Show a loading status while results refresh. Do not poll or reload editor fields for image job status.
- Acceptance: updated preferred tags and metadata display on return without browser refresh; search refresh cannot overwrite editor fields.
- Validation: disposable search/navigation diagnostic and polling-call inspection.
- Status: complete. Successful saves mark search stale; returning to Search refreshes results with request-generation protection. Editor refresh is user initiated.

### WP6 — Documentation and completion
- Dependencies: WP1–WP5.
- Files/interfaces: `Docs/COMPONENTS/LIBRARY.md`, `Docs/DATA_MODEL.md`, `Docs/CODE_MAP.md`, `Docs/INVARIANTS.md`, `Docs/DECISIONS/README.md`, new ADR.
- Work: document targeted reads, preference storage, migration, and consolidated save; add an ADR for explicit preference storage and atomic editor updates. Record observed validation, complete this plan, and move it to `plans/completed/` only after acceptance checks pass.
- Acceptance: owning knowledge docs accurately match implementation and checks; no unrelated documentation changes.
- Validation: review changed documentation and final diff.
- Status: complete. Component/data/code-map/invariant documentation and ADR 0006 are synchronized with the implementation.

## Validation
- Verified Python 3.14.6 and Node 24.18.1.
- Disposable diagnostics passed for targeted detail reads/search synchronization, migration/backfill/idempotence, preferred aliases/collision/clear, and transaction rollback. Source/browser inspection covered navigation/save sharing, stale response guards, selector preservation, and no polling writes.
- `npm.cmd run test:e2e`: 3 passed. One initial run had a transient failure-retention lock error; the affected scenario passed alone and the full rerun passed.
- `python -m py_compile` on changed Python modules, `node --check zet/web/static/zet.js`, and `git diff --check` passed.
- Inspect the final diff and preserve all pre-existing user changes.

## Assumptions and decisions
- Changing the preferred key keeps previous keys active for existing templates and scenes.
- Empty preference clears the preferred key and displays the asset tag.
- Existing reference-management endpoints retain their current reassignment behavior; collision rejection applies to the editor save operation.
- No new dependencies, live rendering, or normal-library diagnostics.

## Progress and results
- 2026-10-12: implemented WP1–WP6. Disposable diagnostics and the approved E2E baseline passed. A fast-fixture browser smoke check loaded the app and confirmed the inventory view exists; a full UI save-flow was not exercised in that smoke check.
