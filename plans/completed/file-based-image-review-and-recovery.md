# File-based local image review and live batch recovery
Status: complete
Authorization: Joe approved applying the fix to the running app, recovering Elder
and Youth Tsaeytte Head-Image batches, and removing checksum/path metadata failures
when their image files exist.

## Goal and scope
Local character image availability comes from the existing file. Missing/outdated
checksums, historical receipts and obsolete absolute roots must not prevent review
of an available image. Retain universe/candidate/attempt/cancellation/evaluation
ownership fences. Investigate other stale image references without replacing files
or matching arbitrary basenames. Published immutable locks and transport inventory
checks remain separate from evaluation availability.

## Current evidence and owners
`image_harvest_service.py` currently gates local ranking on receipt/hash evidence;
`LocalImagePipelineWorkflowService.reevaluate` repairs only receipt-proven missing
hashes. `LibraryReferenceService` decodes portable fields but leaves stale absolute
references unchanged. `PathService` owns shared path resolution. Production is
managed release `7ff178b`, while the preceding local fix is committed in `6a6681b`.
Production uses its existing LocalAppData state through config.runtime.toml;
preserve that config and avoid an unrelated storage migration.

## Work packets
### WP1 — File-based evaluation and path diagnosis
- Files: image_harvest_service.py, local_image_workflow_service.py; path_service.py
  and library_reference_service.py only if the audit establishes affected reads.
- Dependencies: read-only image-path audit.
- Work: replace checksum/receipt admission with file availability; refresh hashes
  as bookkeeping on explicit re-evaluation. Retain current owner/attempt fences.
  Resolve moved references only through an exact universe-relative suffix when
  an existing file establishes the destination; no filename search.
- Acceptance: reported batch copies rank with absent/stale metadata; replaced,
  cancelled and superseded candidates still cannot publish advice.
- Validation: disposable isolated checks, approved four-scenario E2E baseline,
  git diff --check.
- Status: complete.

### WP2 — Document, deploy and recover
- Files: affected component/invariant/data/decision docs; this plan.
- Dependencies: WP1 and passing isolated validation.
- Work: record the intentional evaluation-contract change; deploy through the
  managed release controller, retaining current runtime configuration. Invoke
  Re-evaluate for the two named FRONT batches and inspect resulting rankings.
- Acceptance: healthy new production revision/boot; both original batches ranked;
  original image bytes and human decisions/selections remain unchanged.
- Validation: managed staging suite, health/revision checks, batch/AI job status,
  source-image checksums recorded before/after for verification only.
- Status: complete.

## Documentation impact
LOCAL_CHARACTERS owns action semantics; AI_JOBS/INVARIANTS/DATA_MODEL describe
receipt/hash admission; CODE_MAP maps the shared owner; ADR 0017 needs a scoped
supersession note with the new decision. No schema versions or dependencies change.

## Constraints and risks
Do not disable worker-mode protections in repository code. Use the live HTTP
administration actions for deployment and recovery. Do not run the offline path
migration while production is active. Existing immutable-lock integrity is not
the same as permitting advisory ranking of a visible file. Path audit results
must distinguish stale metadata from files genuinely absent on disk.

## Progress and results
- No production writes performed yet in this turn.
- Read-only path audit running; production health and managed config confirmed.
- Read-only audit completed: 2,837 JSON records, 3,544 image references; 143 stale
  absolute references in 34 records map exactly to existing current-root files.
  These are pipeline records, including historical story and turnaround artifacts.
  Other missing-path observations include task-relative paths and genuinely absent
  historical files; no bulk migration or image replacement was performed.
- Disposable file-based recovery/path checks passed for copies of both batches,
  outdated hashes/absent asks, all 143 mappings, task-relative/foreign-universe/
  traversal behavior, and cancelled/replaced/missing-file rejection.
- `npm.cmd run test:e2e`: all four approved scenarios passed (34.9 seconds).
- Live pre-rollout snapshot: both named batches INTERRUPTED, eight existing images
  each; Elder ranking FAILED, Youth unranked. Original byte hashes/human decisions/
  selections recorded in ignored `test-results/live-head-recovery-before.json`.
- Implementation published as `f827c04a462dcb6f51cc736189072761c595126b` and
  deployed through `/api/deployment/update`, operation
  `a0e53395cef74826bb6acaf4f072d065`. Staged release's approved E2E command passed;
  controller reported succeeded and health confirmed revision f827c04 with new
  boot `48b3d8b249544e0d95e6de3306d8ca58`. Existing runtime config retained.
- Recovery is blocked before either Re-evaluate POST: the E: volume disappeared
  from Windows. `Get-Volume`, `Get-Disk` and `Get-Partition` show only C:/D: and
  their recovery/system partitions. D: is AI_DRIVE and has no Zet library/queue.
  Health reports recovery error `[WinError 3] ... E:\\`; explicit Moonsea requests
  return `Universe not found: Moonsea`. No path substitution, new library, queue
  migration or image changes were made. Joe was asked to reconnect E:\Zet.
- The disposable `test-results/recover_live_heads.py` stopped after the deployment
  succeeded and before submitting AI work. Once E: is back, rerun it: it checks
  the deployed revision/boot, submits the two re-evaluations, then verifies eight
  ranked images each and preservation of original bytes/human decisions/selections.
  Do not mark WP2/this plan complete until that live verification succeeds.
- Joe confirmed the drive was reconnected. After E: became readable, the existing
  `/api/processes/restart-zet` action restarted the deployed release so startup
  recovery could finish; health confirmed revision f827c04, boot
  `4515a182b3d44ee9983d37b7c5592613`, and recovery complete.
- Re-evaluate was submitted once per original batch through the live FRONT action.
  The first monitor incorrectly read Elder's prior FAILED ranking before the new
  asynchronous evaluation finished; monitoring was corrected to compare evaluation
  IDs, then resumed with `--monitor-only` without resubmitting work.
- Final live verification: Elder evaluation `420fbfa3cc384f42bb77ab753031d95b` and
  Youth evaluation `85a0ce60988c402fb22293b4bb14cfbc` both produced COMPLETE rankings
  of all eight original FRONT images. Both AI observation jobs are COMPLETE.
  Original image bytes, human decisions, front anchors and selected views match
  the pre-rollout snapshot. Full ignored result: `test-results/live-head-recovery-result.json`.

## Final result
The requested code is deployed and both reported batches are recovered. Local
review uses existing files instead of historical checksum/receipt admission;
all 143 audited stale absolute references resolve to exact existing current-root
files without a bulk library rewrite. Four approved E2E scenarios passed locally
and in managed staging; focused disposable recovery/path checks and final
`git diff --check` passed. No new permanent tests, dependencies, images or
published locks were introduced or replaced. The transient E: disconnect was
resolved by Joe reconnecting the volume; no filesystem remapping was performed.
