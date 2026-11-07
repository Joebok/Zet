# Identity Key Inventory publication

Status: complete

## Goal

Publish a saved Identity Key under the character, phase and key label. Keep the Inventory item and its source linkage current across edits and explicit unlocks.

## Work packets

### WP1 — Persist and publish
- Files and interfaces: IdentityKey model, repository and service, local source service, EntityLibraryService.
- Dependencies: existing crop writer, file fence and catalog transaction.
- Acceptance: a saved crop publishes with a stable asset ID and logical reference, source provenance and character/phase association. Update commits a new crop and catalog revision together. Unlock archives the owned item. Existing keys remain readable.
- Validation: disposable lifecycle and failure checks against an isolated catalog.
- Status: complete.

### WP2 — Dashboard actions
- Files and interfaces: ZetApp, FastAPI Identity Key routes and Identity Key table in zet.js.
- Dependencies: WP1.
- Acceptance: Lock and Unlock reflect saved state and show feedback. A locked key must be unlocked before deletion.
- Validation: JavaScript syntax check and approved fast E2E suite.
- Status: complete.

### WP3 — Verify and document
- Files: library component, data model and code map.
- Dependencies: WP1 and WP2.
- Acceptance: document storage, ownership and lifecycle. Review final diff.
- Validation: git diff --check.
- Status: complete.

## Final results

- The catalog owns lock state. Updates keep the asset ID and logical reference and switch to a new crop revision using a publication receipt. Unlock archives the item. Relock restores it.
- The isolated FastAPI check passed save, lock, relock, locked update, unlock, deletion protection, source linkage for older records, and rollback after staging an interrupted update.
- `npm run test:e2e` passed all four approved fast scenarios (44.8 seconds). JavaScript syntax, Python AST parsing, and `git diff --check` passed.
- The fast scenarios do not exercise the Identity Keys row buttons directly. The lifecycle check used the same HTTP routes as the dashboard.
