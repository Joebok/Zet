# File-based local image review and live batch recovery
Status: active
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
- Status: in progress.

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
