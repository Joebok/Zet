# Costume deletion and reference integrity
Status: complete (requested deletion fix and broader inspection; follow-up defects remain)
Related issue/specification: Joe's attached Adult Valindia / Relaxed deletion report.

## Goal
Delete only the requested costume's assets and block only for consumers of those
assets. Inspect related inventory reference protections without changing the live
library, deleting Joe's costume, or expanding the maintained test suite.

## Current behavior and impact
`LibraryDeletionService.delete_costume` selects every local Costume-Dressing asset
for the character/phase through an unqualified origin prefix. This set feeds both
Narrative protection and catalog purge. The reported IDs belong to School Outfit;
read-only Moonsea inspection found no classified Relaxed assets. Modern origin
keys include costume/view; older checksum-only keys need exact classification.
Affected implementation: `zet/services/library_deletion_service.py`.
Knowledge owners: Docs/COMPONENTS/LIBRARY.md, Docs/INVARIANTS.md and Docs/CODE_MAP.md.
Storage formats and architectural responsibilities remain unchanged.

## Constraints
Preserve logical keys, direct image bindings, frozen job inputs, universe isolation,
and unrelated costumes. No live model/queue work, external writes, or permanent tests.

## Work packets
### WP1 — Scope costume assets precisely
- Dependencies: none.
- Files/interfaces: library_deletion_service.py / delete_costume.
- Work: qualify the origin prefix by costume, compare literal prefixes rather than
  SQL wildcard patterns, retain exact character/phase/costume classification for
  old origin keys.
- Acceptance: Relaxed excludes School Outfit; genuine direct/logical consumers
  still block; an isolated delete preserves unrelated catalog images and keys.
- Validation: disposable Python checks with temporary/copied records and SQLite.
- Status: complete.

### WP2 — Inspect related reference integrity
- Dependencies: WP1 analysis.
- Files/interfaces: entity library usage discovery/status/replacement, Narrative
  resolution/snapshots, record catalog protection; read-only Moonsea catalog.
- Acceptance: identify concrete defects and limitations, distinguish database
  integrity from consumer semantics, report scope without speculative repairs.
- Validation: read-only integrity/foreign-key/usage queries and disposable checks.
- Status: complete.

### WP3 — Verify and document
- Dependencies: WP1/WP2.
- Files: affected library/invariant/code-map documentation and this plan.
- Acceptance: record observed results and unresolved audit findings; complete plan.
- Validation: approved `npm.cmd run test:e2e`, `git diff --check`, final diff review.
- Status: complete.

## Validation and risks
S1/S2 cover authoring/publication compatibility; their assertions do not cover
deletion precision. Use disposable checks for that gap. Old unclassified
checksum-only assets cannot be safely attributed from character/phase alone.
The usage scanner recursively includes historical jobs; inspect before changing
that policy because those jobs also retain direct provenance and frozen bytes.

## Progress
Read-only Moonsea `PRAGMA integrity_check` returned ok; foreign_key_check found
zero violations. Current dual direct/logical usages: 20; mismatched bindings: zero.

## Audit results and follow-up work
All three asset IDs in the attached error are classified School Outfit, not Relaxed.
The old origin selector included 16 Valindia/Adult images; exact Relaxed
classification found zero. The fix limits both guard and purge, including literal
underscore matching and both publisher qualifier forms. Unclassified old images
remain unattributed rather than being deleted on a character/phase guess.

Inspected shared usage queries, archive/status guards, replacement/key reassignment,
entity/variant deletion guards and merge links, Narrative resolution and frozen
job references, migration bindings, and the record-catalog reference scanner.
Inventory consumer queries join exact asset IDs/keys; the broad costume-origin
predicate is confined to costume deletion. These paths are source inspection,
not exhaustive execution coverage. Record-catalog tag scans retain their legacy
Stories/Characters/Assets/Pipelines roots; migrated Narrative image dependencies
use the entity catalog's direct IDs/logical keys.

### Finding 1 — Historical metadata becomes a replacement's consumer
`EntityLibraryService.refresh_usages` recursively visits jobs, baseline/detail
snapshots and source snapshots. `usage_for_asset` and archive/deletion queries
resolve every stored reference_key against its current binding, even if the
observation also contains a frozen asset ID. A disposable record containing only
`jobs.old.references[0]` with image A/key K falsely appeared in image B's usages
after K was reassigned to B. Narrative render/generate jobs copy the bytes into
job-local snapshots; this historical metadata is not a new live binding to B.
This is reproducible, but no current live dual observation had divergent IDs.
- Follow-up packet: entity_library_service.py usage traversal/query semantics,
  Narrative job-reference producers/consumers, and owning library/invariant docs.
- Dependencies: decide which authored fields and unresolved jobs are live
  dependencies versus frozen provenance; preserve replay and direct provenance.
- Acceptance: rebinding K protects live K consumers of B without attributing
  A's frozen metadata to B; genuine direct and logical guards still work.
- Validation: disposable rebind/archive/deletion checks and approved E2E baseline.
- Status: not implemented; broader inspection did not authorize redesigning usage policy.

### Finding 2 — Invalid dual observation aborts refresh
`refresh_usages` validates only asset_id when both fields exist. A valid asset ID
with a missing reference_key then fails the foreign key on insertion and rolls
back the entire refresh. Normal element authoring rejects dual bindings, but
job references deliberately contain both and the scanner accepts arbitrary
nested source records. This can leave usages stale after an already-written record.
- Follow-up packet: entity_library_service.py / refresh_usages.
- Dependencies: none for validating both endpoints; coordinate normalization with
  Finding 1 if changing observation format.
- Acceptance: invalid endpoints appear in the missing-reference report without
  aborting valid observations or silently dropping a real direct consumer.
- Validation: disposable mixed valid/missing observations and E2E baseline.
- Status: not implemented.

### Live catalog observations
288 assets, no missing image blobs, no foreign-key violations, no variant-owner
mismatches, and no assets with multiple costume classifications. One active key,
`tsaeytte.adult.costume-dressing.romulan-dress.back`, points at archived image
`6d3c2c0f-83d0-4cc4-af59-52d77b22f604`. Narrative resolution correctly rejects it;
the audit did not establish the historical operation that caused this state.
Two obsolete Paladin Armor images retain preferred keys now bound to their
replacements. Their detail selector hides preferred keys for non-approved images;
this is residual metadata, not evidence of a live-reference mismatch. No data
repair, reconciliation, or production app construction was performed.

## Final results
- Changed library_deletion_service.py and the owning library/invariant docs.
  Responsibilities/entry points did not move, so CODE_MAP requires no change;
  this bug repair introduces no durable architectural decision requiring an ADR.
- Disposable `python3 -B test-results/costume-reference-check.py`: passed copied
  Moonsea deletion and preservation, genuine direct/logical blocking, precise
  modern/classified-legacy purging, literal wildcard-like names and both qualifier
  forms. Reproduced Findings 1 and 2. No permanent tests were added.
- Hash comparison: all 185 inspected live catalog/Narrative/Valindia source files
  were byte-identical before and after the checks.
- `npm.cmd run test:e2e`: 3 passed in 26.1 seconds with verified Python 3.
- `git diff --check`: passed; final diff reviewed for unintended changes.
- No live render check or actual Relaxed deletion; this is a local source fix.
