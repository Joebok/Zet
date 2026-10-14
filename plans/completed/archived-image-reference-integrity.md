# Repair active references bound to archived images
Status: complete
Related audit: [Costume deletion and reference integrity](../completed/costume-reference-integrity.md).

## Goal
Deactivate the identified stale Romulan Dress back-view key while preserving its
archived image and binding, and prevent active logical references from pointing to
archived images.

## Current behavior
`EntityLibraryService._sync_pipeline_assets` archives pipeline assets whose origins
are no longer supplied but leaves their active logical references unchanged.
`_save_logical_reference` can activate a key on any asset status. Explicit archive
operations deactivate references, but pipeline reconciliation does not. The
Narrative resolver rejects archived targets. Read-only Moonsea inspection found one
active key bound to an archived asset, no usages or current local lock for that
slot, and passing SQLite integrity and foreign-key checks. The historical cause
is unknown.

## Desired behavior
Pipeline archival and key deactivation commit together. Active key writes cannot
target archived images. The existing record is repaired by an explicit, preview-first
operation that checks its expected binding and backs up the catalog before writing.

## Constraints and impact
Keep the existing asset selection policy, schema, image bytes, key binding, usage
semantics, and universe isolation. No permanent tests, dependencies, API routes,
live model/render checks, or automatic replacement selection. Relevant owners:
Library component, data model, invariants and capability code map.

## Work packets
### WP1 — Keep pipeline archival and reference status consistent
- Dependencies: none.
- Files/interfaces: `zet/services/entity_library_service.py`, `_sync_pipeline_assets`.
- Work: select the exact rows being archived and deactivate their active keys in
  the same transaction, for both populated and empty provider results.
- Acceptance: newly archived pipeline assets have no active keys; retained images
  and unrelated keys remain unchanged.
- Validation: disposable temporary-catalog checks with a fake provider, including
  transaction rollback and repeated synchronization.
- Status: complete. Disposable fake-provider checks covered retained and empty
  provider results, repeated sync, and rollback after an injected post-update failure.

### WP2 — Reject active keys on archived images
- Dependencies: WP1.
- Files/interfaces: `EntityLibraryService._save_logical_reference`,
  `save_logical_reference`, `update_asset`, and replacement key transfer.
- Work: validate target status in the key-write transaction. Editor saves that
  archive an image keep submitted preferred keys inactive. Check replacement
  transfers before moving bindings.
- Acceptance: rejected assignments leave existing rows unchanged; approved targets
  and set-only references retain current behavior.
- Validation: disposable create/reassign/reactivate, archive/editor-save, approved
  assignment, replacement, and rollback checks.
- Status: complete. Disposable checks covered archived-target activation,
  approved-target assignment, editor archival with a preferred key, and key
  transfer during replacement.

### WP3 — Add a targeted preview/apply repair
- Dependencies: WP1/WP2.
- Files/interfaces: `EntityLibraryService.deactivate_archived_reference` and
  `zet/scripts/repair_archived_reference.py`.
- Work: require explicit universe root, key and expected asset ID; preview by
  default; require `--apply`; verify the binding/status; treat matching inactive
  rows as a no-op. Do not initialize the app or migrate/synchronize the catalog.
  Back up and verify SQLite before apply; recheck and update only key status/time
  transactionally.
- Acceptance: the repair preserves binding, labels, sets, assets, usages and blobs;
  conflicts abort safely.
- Validation: disposable copied-catalog preview, apply, repeat, conflict and backup
  restore checks.
- Status: complete. Disposable service/CLI checks covered preview, apply,
  idempotency, conflicting expected IDs, and a verified catalog backup. A rehearsal
  copied the live 290-asset/43-reference catalog before apply; only the target
  reference status and timestamp changed in the copy. Its integrity and foreign-key
  checks passed, and no active key remained bound to an archived image.

### WP4 — Verify, apply with authorization, and document
- Dependencies: WP1–WP3.
- Files: Library component, data model, invariants, code map, this plan.
- Work: run the approved E2E baseline and diff checks; present exact preview and
  copied-catalog results before live repair. After authorization, stop catalog
  writers, preview again, back up and apply; verify integrity, binding status,
  image checksum, unrelated rows, and Narrative inactive-key resolution. Record
  results and archive this plan when complete.
- Acceptance: no active key targets an archived image and docs describe the verified
  behavior and validation. The later back-view publication can explicitly rebind.
- Validation: `npm.cmd run test:e2e`, `git diff --check`, targeted read-only SQL,
  and final diff review. Live repair is separately gated by Joe's authorization.
- Status: complete. The approved E2E baseline passed (3 scenarios); targeted source,
  rollback, and Narrative resolution checks passed. `git diff --check` passed. The
  initial rehearsal detected six unrelated catalog records added while writers were
  running, so the deployed dashboard and harvester were stopped before the fresh
  preview and live apply. Both were restarted; production health returned on the
  same revision.

## Progress and decisions
Selected policy: retain the image archived and deactivate its logical key. No
replacement is selected. The guarded live repair is complete.

The live apply changed only the target logical reference's status and timestamp
relative to its verified pre-repair backup. The catalog now has 296 assets and 49
logical references; SQLite integrity is `ok`, foreign-key check has zero violations,
and no active reference targets an archived image. The archived image checksum
still matches its stored blob. Narrative resolution rejects the now-inactive key.
The first copied-catalog rehearsal used the earlier 290-asset/43-reference snapshot;
the live catalog had gained six unrelated Valindia records by the time writers were
stopped. The fresh live backup was taken after those records appeared, and all rows
except the requested reference status/timestamp matched it after apply.

## Final results
Changed `entity_library_service.py`, added `repair_archived_reference.py`, and
updated Library, data-model, invariant, and code-map documentation. Disposable
checks covered pipeline archival/deactivation, rollback, archived-target rejection,
editor archival, replacement, CLI preview/apply/idempotency/conflicts, and backup
restoration. The approved `npm.cmd run test:e2e` baseline passed all three scenarios
(23.4 seconds). The live repair was applied with a verified backup; post-apply
integrity, foreign-key, binding-diff, image-checksum, active-to-archived, and
Narrative-resolution checks passed. Production restarted healthy on the same release.
No schema, permanent tests, dependencies, or live render checks were added.
