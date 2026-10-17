# Move machine storage and bound retention
Status: complete
Related issue/specification: none

## Goal
Route Zet's machine-local queues, indexes, workflow checkpoints and migration reports through configured `E:\\Zet\\AppData`, bound disposable index/history retention, and complete the approved offline cutover. Keep authored library and authoritative entity-catalog data unchanged. The shared transport queue and external archive remain outside cleanup.

## Current behavior
`LibraryIndexRepository` defaults to `%LOCALAPPDATA%/Zet/Indexes` and writes every complete generation and parsed-source revision. `queue_local_state_root` independently hashes the shared queue and uses `%LOCALAPPDATA%/Zet/AI_Queue`; task workflow and library-reference migration reporting use independent locations. The current SQLite index API owns limited compatibility history, while the dashboard's AI Queue uses local jobs and receipts directly.

Initial read-only inventory on 2026-10-16 found 104.48 GB in 1,900 indexes, including 62.57 GB and 31.26 GB for former library roots and a 9.36 GB index for current Moonsea. A fresh bounded cutover preview later measured the current legacy AppData tree at 99,819,740,792 bytes (49,568 files); `Indexes` is 99,750,010,880 bytes across 4,202 `.sqlite3` databases plus two sidecar files. Those databases contain 19,535 generation rows, 3,011 with multiple generations, only 21 free pages in total, and one 62,570,938,368-byte database. This confirms VACUUM alone cannot address the size. The exact operational copy manifest contains 45,364 checksummed files (69,729,912 bytes); no file changed during its scan. The shared queue is 412,270,022 bytes. Source queue retention classification found 25,125 eligible file actions, 29 jobs without receipts, and 289 unresolved/unknown receipts, which remain protected. The external archive scan reached its 20,000-file / 15-second limit at 3,404,944,730 bytes and remains incomplete/report-only.

## Desired behavior
`[Storage]` defines one root plus relative child folders for Indexes, QueueState, MigrationState and WorkflowState; Windows production points to `E:/Zet/AppData`. Other platforms and older configs retain their prior defaults. All local-state consumers use the shared resolver. Index replacement is atomic to readers and keeps one published generation; cached parses and compatibility history are bounded. A daily, idempotent maintenance pass preserves unresolved work and compact replay/image evidence. `manage_storage` reports by default; `--apply` enables narrowly validated cleanup. The approved offline cutover is complete; sources below the old C: AppData root were removed only after copy, index and live dashboard checks.

## Impact, documentation and constraints
Owners: `config_service.py`, a focused storage-path service, `ai_queue_paths.py`, workflow/queue consumers, `library_index_repository.py`, `library_index_service.py`, a focused maintenance/migration service and CLI. Update Data Model, Library, AI Jobs, Queues, Invariants, Code Map, Development and a short ADR. Preserve producer/universe ownership, immutable inputs, pending-answer recovery, duplicate/deletion fences, selected-image admission and lock inode behavior. Never delete by file mtime or rewrite arbitrary strings in historical records.

## Implementation steps
### WP1 — Configure and resolve storage
- Dependencies: none. Files: `config.toml`, `zet/services/config_service.py`, new `zet/services/storage_path_service.py`.
- Work: add the selected root/child/retention settings, platform overrides, legacy defaults, normalized containment validation and explicit missing-volume errors. Do not create paths while loading config.
- Acceptance: old/minimal fixture configs resolve as before; configured Windows paths and relative-root configs resolve deterministically; escaping children and overlap with the library/queue fail.
- Validation: disposable configs exercise Windows and host-platform overrides, relative/absolute paths, containment, and unavailable-volume behavior.
- Status: complete.

### WP2 — Route local-state consumers through configuration
- Dependencies: WP1. Files: queue path and lifecycle helpers, `FileProxyClient`, model catalog, manual publication, workflows, task state and migration report, call sites.
- Work: pass storage root explicitly; preserve hashed shared-queue/producer identities and queue-relative/library-relative references. Keep explicit task/runtime overrides. Update the E2E fixture to select its own isolated storage root rather than monkeypatching the index constructor.
- Acceptance: queue publication, cache lookup, receipt and manual publication paths derive from the configured root; fixtures never reach production AppData.
- Validation: disposable two-root service check plus the fast E2E suite.
- Status: complete.

### WP3 — Bound the derived library index
- Dependencies: WP1. Files: library index repository/service and rebuild CLI.
- Work: after snapshot commit, activate the new generation and delete obsolete generations/cache revisions/dependencies in one transaction. On failure keep the old active generation. Limit carried compatibility history to seven days using completion time; deduplicate one summary per job and avoid full archive import during normal reconcile.
- Acceptance: each successful publication keeps one complete generation; repeated reconciliation has bounded sources/cache; failed publication leaves the prior generation readable.
- Validation: disposable SQLite checks for generation switching, source revision pruning, stale-cursor behavior and `integrity_check`.
- Status: complete.

### WP4 — Retain only necessary completed operational data
- Dependencies: WP2. Files: lifecycle service, coordinator, job repository/query, workflow continuation service.
- Work: retention uses original completion timestamps and receipt/domain evidence. Remove only safely completed detail older than seven days; compact receipts without dropping replay fences or successful image-harvest proof. Preserve active, unresolved, ambiguous and selected-image work; skip lock files. Prevent archive import from renewing old details.
- Acceptance: legacy PUBLISHED records with matching old receipts are recognized as completed; missing receipts stay protected; duplicate answers cannot replay after compaction.
- Validation: disposable checks for imported timestamps, retry/interruption, image receipt admission and unknown ownership.
- Status: complete.

### WP5 — Add low-overhead maintenance and reporting
- Dependencies: WP3-WP4. Files: focused maintenance service/CLI and existing background lifecycle.
- Work: run safe index pruning after publication and a coordinated daily state sweep. Add `python3 -B -m zet.scripts.manage_storage --config config.toml`, read-only by default, with `--apply` and explicit offline rebuild/compact options. Report bytes, index generations/free pages, retention candidates/protected jobs, errors, shared queue and legacy archive. Keep one latest report; remove only verified completed Zet transport copies with no consumer.
- Acceptance: repeated passes are idempotent; offline compaction returns space; ambiguous archive/queue records appear in preview, not automatic deletion.
- Validation: temporary trees and SQLite files; no production data mutation.
- Status: complete.

### WP6 — Prepare offline cutover
- Dependencies: WP2-WP5. Files: migration/report service and operator instructions.
- Work: generate an exact manifest; then, only after Joe approves that manifest, stop verified processes, run `manage_storage --migrate-from <manifest> --confirm-offline` to copy/checksum operational state, rebuild disposable indexes for selected/all discovered universes, verify current workflows/images, and remove approved old data. The migration command rechecks file inventory/checksums, is retryable, and never removes its source. Retain source state until verification. Do not copy old index databases.
- Acceptance: destination opens for all configured universes; selected images and pending jobs remain valid; application creates no local state below the former AppData root. Report only until cleanup is approved.
- Validation: full inventory/checksum, SQLite integrity, app/task smoke checks; rollback instructions distinguish pre-write restore from post-write reconciliation.
- Status: complete. Joe approved the offline cutover after reviewing the manifest. Zet and the AI Proxy were stopped; a fresh complete preview was generated and checksum-verified during migration. 45,364 operational files (69,729,912 bytes) copied to E:, then verified. The disposable Moonsea index rebuilt at E: and passed SQLite integrity checks. The dashboard restarted against E:, discovered Moonsea, returned jobs/recent history, and served a selected approved image whose checksum matched the library record. The AI Proxy restarted with 0 queued and 0 running jobs. No active or unresolved operational state was deleted from the destination.

### WP7 — Document and finish
- Dependencies: all prior packets. Files: affected knowledge owners, ADR, this plan.
- Work: run the approved existing fast E2E suite and `git diff --check`; run disposable retention/migration checks; document measured outcomes and limitations. Do not add permanent coverage or dependencies. Archive this plan only after code/docs validation; leave cutover pending if its preview has not been approved.
- Acceptance: no unintended diff, configured paths/retention and operational boundaries documented, test outcomes recorded.
- Validation: `npm.cmd run test:e2e`, focused disposable checks, `git diff --check`.
- Status: complete. Cutover outcomes and the existing reconciliation warning are recorded in Development documentation.

## Risks and open constraints
The existing deployment can start both the dashboard and collectors; migration must fence every writer before copying/deleting state. Legacy history has mixed imports and timestamps. Queue state files contain image proof, attempt fences, lock files, and failed results with distinct retention rules. Archive scan must remain bounded and read-only until exact ownership/completion is known. New binaries must not silently fall back to C: if E: is unavailable.

## Progress and decisions
- 2026-10-16: selected `E:\\Zet\\AppData` and seven days of completed details. Central storage configuration, consumer routing, bounded index publication, conservative queue retention, reporting and checksum-verified migration are implemented. Joe approved cutover after reviewing the manifest. Zet/AI Proxy were quiesced, operational state was copied and verified, Moonsea was rebuilt at E:, and both services were restarted and checked. Retention removed 25,125 expired completed-detail files (46,752,461 bytes); 29 jobs without receipts and 289 unresolved/unknown receipts remained protected. The old C: AppData index/queue/migration state was removed after verification. A second read-only preview exposed two residual index databases under the same approved root after the first deletion; their current exact paths were checked and removed as stale derived indexes. No authoritative library/catalog data, shared queue data, or external archive files were removed.

## Final results
Implementation, documentation and cutover are complete. `npm.cmd run test:e2e` passed all four approved scenarios (32.1s); Python compilation and `git diff --check` passed. Disposable checks passed for storage-root resolution/containment, source-preserving idempotent checksum migration, generation pruning, failed-index-build preservation, SQLite integrity and compaction. The destination contains one healthy Moonsea index database (2,437,120 bytes after application reconciliation), with one active generation. Operational state copied successfully; the seven-day sweep completed 25,125 file actions with no failures and retained 29 receipt-less jobs and 289 unresolved/unknown receipts. Dashboard health, Moonsea discovery, job listing, recent harvests, and selected-image checksum were verified. AI Proxy status was 0 queued/0 running. No files remain under the old C: AppData Indexes root; the old local queue tree contains no files. The shared queue and incomplete external archive were left untouched. Existing provider reconciliation error `project/.indexed-dashboard/entity-library: list index out of range` remains and was already present in old index metadata. Cutover result artifacts are under ignored `test-results/`.
