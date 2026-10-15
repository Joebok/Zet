# Recover verified locks hidden by archived catalog entries
Status: complete â€” installed and live catalog repaired; FRONT left unlocked for Joe
Related issue: none

## Goal and evidence
Restore inventory discovery and relocking for verified local character images whose
catalog entries remain archived after source availability is restored. Read-only inspection
of the configured Moonsea library found all eight Tsaeytte Adult Canonical Adventure
Gear images intact with matching hashes and live batches; seven remain locked and
FRONT was explicitly unlocked by Joe. All eight catalog entries are archived and
their costume references inactive. Valindia School Outfit has the same older
archived entries; its recently republished FRONT uses an approved entry.

The configured portable paths resolve correctly. EntityLibraryService pipeline sync
only excludes current origin keys from further archival; it never restores entries.
register_locked_pipeline_image reuses archived origin keys, then classification
rejects activation of their references. Preserve the archived-reference guard.

## Impact and constraints
Owners: entity_library_service.py; LIBRARY component and CODE_MAP documentation.
No schema/path format change. Preserve image IDs, bytes, reference bindings, user
changes, obsolete entries and genuinely unavailable/stale/unlocked sources. No new
permanent scenarios or dependencies. No live library writes or production deployment
without Joe's approval. Architecture/data/invariants were consulted; no new durable
design decision or changed ownership requires an ADR.

## Work packets
### WP1 â€” Restore verified local publications
- Dependencies: none.
- Files: zet/services/entity_library_service.py.
- Work: restore archived entries identified by verified current local origins during
  synchronization, reactivating only references still bound to those restored entries;
  verified explicit publication restores the reused entry before classification.
- Acceptance: existing IDs survive discovery/relock; invalid locks remain archived;
  generic reference writes continue to reject archived targets.
- Validation: disposable catalog reproduction including portable relocated locks,
  legacy/current origins, repeat sync/relock and invalid sources; approved S2.
- Status: complete.

### WP2 â€” Document, validate and prepare the live recovery
- Dependencies: WP1.
- Files: Docs/COMPONENTS/LIBRARY.md, Docs/CODE_MAP.md, this plan.
- Work: record recovery contract; inspect live catalog read-only to enumerate exact
  changes and offer concrete recovery/deployment for approval after local verification.
- Acceptance: code and disposable checks pass; live changes are explicit and pending
  approval; no live file or selection is changed in this local implementation.
- Validation: npm.cmd run test:e2e; git diff --check; scoped diff review.
- Status: complete, including approved live installation, repair and verification.

## Validation and progress
Python 3.14 verified via python3. Existing unrelated working-tree changes are preserved.
Live inspection used SQLite mode=ro and LocalAssetStoreService read/hash checks only.
No app initialization or library sync was run against the live library.

Implemented exact origin/path/checksum recovery in the inventory synchronization
transaction, including references still bound to the recovered asset. Explicit
publication restores an existing verified archived entry before classification.
Historical duplicate publications sharing a checksum are excluded by exact locked
image path. Obsolete entries and reference keys rebound elsewhere are preserved.

Disposable `python3 -B test-results/inventory-recovery-check.py` passed on copied
Tsaeytte records and catalog after relocating the fixture: seven current locks
reappeared, FRONT relocked with its existing asset ID, repeated sync was unchanged,
portable path writes remained relative, and archived-reference guards still held.
Stale locks, modified bytes, invalid batches, historical duplicate blobs, rebound
keys and corrupted stored publications were checked. No permanent tests were added.

The read-only preview `test-results/inventory-recovery-preview.json` enumerates 133
current archived publications (94 Tsaeytte, 39 Valindia) and 37 inactive references.
It includes seven Canonical Adventure Gear and seven School Outfit locks. The
explicitly unlocked Tsaeytte FRONT is a separate proposed relock, preserving asset
81269748-46f2-4fa0-b11b-bdb625855e65. No image regeneration or new IDs are needed.

Initial `npm.cmd run test:e2e`: all 3 passed (28.6 seconds). A repeat after the exact
path guard passed S1/S3 but S2 received a transient 404 while reading Dressing
state.json: Windows PermissionError, followed by a locked runner.lock during failure
retention. Trace preserved at test-results/inventory-recovery-e2e-file-lock-trace.zip.
This occurred before Dressing publication, outside the changed catalog methods.
A final baseline rerun passed all 3 scenarios (27.3 seconds). `git diff --check` passed; scoped code/docs
diff reviewed. Existing unrelated path/process changes were preserved.

## Approved live rollout
Joe approved installing the fix and repairing the live catalog. He explicitly
reserved relocking Tsaeytte FRONT for his own verification; do not relock it or
activate its reference. Install the reviewed fix in running Zet, make an
integrity-checked SQLite backup, revalidate and restore the enumerated verified
publications/references, then verify inventory and image serving. Preserve unrelated working-tree changes
and exclude them from the rollout. Historical/unverified entries stay archived.

## Live results (2026-10-14)
- Installed only `zet/services/entity_library_service.py` into the existing active
  release `2e3ad3517bc46e61f6c57ced46163ef06a3ce97c`. The production module matched
  the original committed source before installation (ignoring BOM/newlines); no
  existing production edit was overwritten. The installed file matches the locally
  tested file byte-for-byte. This is a recorded runtime hotfix, not a new promoted
  Git release; checkout edits remain uncommitted.
- Stopped only dashboard/harvester processes matching the exact managed config.
  Their Windows venv launcher/core pairs were accounted for. Restarted the dashboard
  and harvester through the existing deployment helpers with hidden windows. Health
  reports ready on port 8081 with new boot `0c1b42d5205a4c2db7fcfe5f0065187b`.
- Re-ran the disposable recovery check with the active release interpreter and
  installed service before touching the live catalog: passed.
- Integrity-checked SQLite backup:
  `E:/Zet/Zet_Library_v5/Moonsea/backups/catalog-before-locked-inventory-recovery-20261015T002556154260Z.sqlite3`.
- Revalidated the approved preview and restored exactly 133 asset statuses and 37
  same-bound reference statuses in one transaction. Compared before/after rows:
  only their statuses/timestamps changed; all other catalog tables, image IDs,
  metadata and local selection/lock source files were unchanged by the repair.
  Integrity and foreign-key checks passed.
- HTTP inventory searches returned 200, including all seven currently locked
  Tsaeytte Canonical Adventure Gear views and all eight Valindia School Outfit
  views. Representative Tsaeytte and Valindia `/api/file` requests returned 200 and
  matching SHA-256 bytes. After ordinary inventory synchronization, all 133 repaired
  assets remain approved and all 37 references remain active.
- Tsaeytte FRONT remains unlocked, with its existing archived image and inactive
  reference untouched, as Joe requested. Live relocking is reserved for Joe; it was
  verified only on disposable copies by this task.
- A pre-existing derived-index provider diagnostic (`list index out of range`)
  remains in health's cached reconciliation result. Direct inventory searches,
  detail reads and image serving work; no unrelated index repair was attempted.
- Runtime source backup and install receipt:
  `C:/Users/Joe/Projects/Zet_Runtime/state/hotfixes/locked-image-inventory-20261015T002551832410Z/`.
  Detailed repair/live-verification reports are in ignored `test-results` and were
  retained with that receipt. No live rendering or image generation was submitted.

## Final result
Local code/documentation and the approved running installation/catalog repair are
complete. `git diff --check` passes. Existing unrelated checkout changes remain
intact. Joe can now refresh the dashboard and test locking FRONT himself.

## Git publication — 2026-10-15

Joe authorized publishing the existing recovery hotfix separately so deployment can preserve it. The scoped release checkout passes S1–S3 (3 passed, 27.0s) and the disposable relocated-catalog recovery check. The fixture explicitly seeds archived states on its disposable copy because the live catalog has already been repaired and Joe has since changed lock state. Live source data remains unchanged. Runtime reconciliation will preserve the exact installed hotfix in Git before the normal deployment controller promotes merged main.
