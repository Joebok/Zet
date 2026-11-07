# Unified head-container phase-change source
Status: active

## Goal
Use one phase-change source for Head Image Construct and Head Image Edit across
Draft and Final requests. A phase/pipeline setting follows the current locked,
published FRONT; a managed upload remains an alternative. Preserve frozen inputs
and migrate older per-quality choices with Final precedence.

## Current behavior
`CharacterAssetContainerService.resolve_references` selected a separate saved
choice by candidate quality and pinned locked references to candidate IDs.
The container settings exposed quality and candidate selectors. Migration stored
both mode choices. Relevant owners are the container service, migration service,
container router/controller/template, and this plan's linked component and
invariant documentation.

## Implementation packets
### WP1 — Shared source resolution and storage
- Dependencies: none.
- Files/interfaces: `character_asset_container_service.py`.
- Work: Resolve unified `sources.phase_change`; use legacy Final if present,
  otherwise Draft. Follow the current lock without candidate ID pinning. Save
  phase/pipeline or verified upload; reject legacy mode-scoped writes. Preserve
  frozen candidate request inputs.
- Acceptance: Both qualities resolve the same current locked FRONT. A saved
  phase/pipeline is allowed before a lock exists; preparation then reports the
  missing or unavailable source. Existing managed upload paths still resolve.
- Validation: Disposable isolated service check for both pipelines, lock change,
  missing lock, upload, legacy precedence, and frozen requests.
- Status: in progress.

### WP2 — Migration and dashboard source controls
- Dependencies: WP1.
- Files/interfaces: `character_container_migration_service.py`, container router,
  `character_asset_container.js`, and `index.html`.
- Work: Store one effective migrated choice while retaining old per-quality
  provenance. Remove Source quality and candidate selection. Show the current
  locked FRONT for selected phase/pipeline; keep upload and clear actions. Remove
  quality from new save/upload requests and reject obsolete quality-specific UI
  writes with a refresh message.
- Acceptance: Save, clear, upload, and reload work for both head containers;
  locked source status tracks the current upstream lock.
- Validation: Disposable browser/API check against an isolated library.
- Status: in progress.

### WP3 — Documentation and regression verification
- Dependencies: WP1 and WP2.
- Files/interfaces: `DATA_MODEL.md`, `INVARIANTS.md`, `LOCAL_CHARACTERS.md`,
  ADR 0048, and this plan.
- Work: Describe shared source resolution and migration behavior. Preserve the
  prior migration/production configuration notes below as historical progress.
- Acceptance: Documentation agrees with implementation and records validation.
- Validation: Approved `npm run test:e2e`, focused Python/JavaScript syntax
  checks, `git diff --check`, and final diff review. No permanent tests or live
  rendering/library actions.
- Status: in progress.

## Constraints
Preserve universe ownership and publication checks. New requests must use the
current locked/published image and freeze its bytes; later lock changes affect
only new requests. Do not add permanent test scenarios or run live renders.

## Historical progress
The prior mode-specific implementation included isolated checks and configuration
of Youth batch `20261023_070525_864928` from the corresponding Adult locks. That
work preserved Draft state and submitted no render. This plan supersedes its
quality-specific source behavior while retaining the configured source phase and
pipeline intent where the current lock remains available.

## Progress and validation
Implementation is in progress. The disposable service check confirmed that Draft
and Final requests resolve the same locked source and that newly prepared requests
follow a changed upstream lock. `npm run test:e2e` passed all four approved
scenarios. Python compilation for the changed services/router, `node --check` for
the container controller, and `git diff --check` passed. The disposable check did
not exercise upload validation, unavailable legacy Final migration, or the browser
source controls/API journey; those remain unverified. No live library or renderer
was used. Keep this plan active until those focused checks are completed.
