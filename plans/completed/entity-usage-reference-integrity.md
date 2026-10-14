# Entity image usage reference integrity
Status: complete
Related audit: [Costume deletion and reference integrity](../completed/costume-reference-integrity.md).

## Goal
Prevent frozen Narrative job references from following a later logical-key reassignment,
and let usage refresh report an invalid endpoint without dropping a valid direct consumer
or aborting its transaction.

## Current behavior
`EntityLibraryService.refresh_usages` records each observed `(asset_id, reference_key)`
pair as one usage and validates only the direct ID when both are present. A missing key
then violates SQLite's foreign key and rolls back all refreshes. `usage_for_asset`,
asset metadata updates, and `LibraryDeletionService._protect_narrative_assets` follow
the current logical binding even when the usage has a direct asset ID. Narrative
generation freezes both resolved IDs and bytes in job reference records; authored
elements instead use either a direct ID or a logical key.

## Desired behavior
- A usage with `asset_id` is anchored to that exact image. Follow a logical key only
  when the usage has no direct ID.
- Validate direct IDs and logical keys independently. Record each invalid endpoint in
  the refresh report, retain every valid endpoint as a usable protection, and commit
  other observations normally.
- Keep the existing storage schema and current-key behavior for key-only usages.

## Impact and constraints
Files: `zet/services/entity_library_service.py`,
`zet/services/library_deletion_service.py`, `Docs/COMPONENTS/LIBRARY.md`,
`Docs/DATA_MODEL.md`, `Docs/INVARIANTS.md`, `Docs/CODE_MAP.md`, and this plan. Storage schema, serialized Narrative records,
queue payloads, and service ownership do not change. Preserve universe isolation,
frozen job inputs, direct provenance, and exact live logical consumers. No permanent
tests or new coverage are authorized by this task; the existing E2E baseline is not
run unless Joe requests tests.

## Work packets
### WP1 — Validate and retain usage endpoints independently
- Dependencies: none.
- Files/interfaces: `EntityLibraryService.refresh_usages`.
- Work: check direct asset and logical-key existence separately, collect a missing
  report row for each invalid endpoint, insert a usage with only its valid endpoint(s),
  and avoid inserting a row when neither endpoint is valid.
- Acceptance: valid observations survive alongside an invalid key; missing keys do
  not abort refresh; invalid direct IDs do not discard an independently valid key.
- Validation: source review and `git diff --check`; no test execution in this task.
- Status: complete.

### WP2 — Anchor paired consumers to their resolved image
- Dependencies: WP1.
- Files/interfaces: `EntityLibraryService.usage_for_asset`, current-usage guards in
  `update_asset`, and `LibraryDeletionService._protect_narrative_assets`.
- Work: follow `logical_references.asset_id` only for key-only usage rows. Keep direct
  IDs authoritative for paired historical/frozen references.
- Acceptance: reassigning a key does not make the new image inherit a paired usage;
  the saved direct image remains protected; key-only live consumers follow the key.
- Validation: inspect all usage joins and `git diff --check`; no test execution.
- Status: complete.

### WP3 — Document and close
- Dependencies: WP1/WP2.
- Files: Library component, invariants, this plan.
- Work: document endpoint validity and paired/key-only consumer semantics; record
  validation and limitations; archive the plan.
- Acceptance: docs match source; final diff contains only this behavior and docs.
- Validation: final `git diff --check` and diff review.
- Status: complete.

## Risks and open points
A usage can carry both a direct ID and a key whose current binding differs after
reassignment. The direct ID remains its frozen identity; a separate key-only live
element represents the current binding where applicable. The legacy paired record
does not independently protect the reassigned target. Callers must continue to refresh
usages after authoring or reference changes.

## Progress
Reviewed the completed audit, library/Narrative component docs, data model,
invariants, usage scanner, Narrative job freezing, and all catalog usage joins.
WP1/WP2 independently validate direct IDs and keys, store whichever endpoint is
valid, and make direct IDs authoritative when querying paired usage records.
`git diff --check` passed. No automated test suite or disposable test was run.

## Final results
Changed `entity_library_service.py` and `library_deletion_service.py`; documented
the usage contract in DATA_MODEL, LIBRARY, INVARIANTS and CODE_MAP. No storage schema,
serialized formats, public interfaces, tests, or dependencies changed. `git diff
--check` passed. Automated behavior remains unverified in this task; the source
guards and query paths were reviewed, including all `asset_usages` joins.
