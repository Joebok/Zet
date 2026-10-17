# Streamlined image integrity
Status: complete
Specification: Joe's approved twelve-packet plan in this chat, 2026-10-17.

## Goal and contracts
An image at its recorded universe-owned path is usable. Historical hashes, receipts,
batch retention and optional provenance do not police files after admission.
Keep managed version/selection fences, ordered bindings, job ownership, atomic
publication and transfer verification. Confirm locked/referenced deletion and allow
it; resolve missing references only when needed. Maintain usages incrementally;
audits/rebuilds are explicit. Derived maintenance cannot fail a committed save.

## Impact and constraints
Owners: local assets/publication, shared AI jobs/queue, reconstruction/wizard,
entity catalog/usages, authoring mutations, index and browser controls.
Knowledge: architecture, data model, invariants, code map and library/local character/
Narrative/AI queue components; add a decision record. No dependencies, permanent
tests, live library/queue/model operations or external writes. Single implementer.
Storage recovery is now committed (working tree clean at implementation start);
reuse its local journal and storage guards. Do not undo its recovery fences.

## Packets
| Packet | Ownership / dependencies | Acceptance / validation | Status |
| --- | --- | --- | --- |
| WP1 | Plan and disposable baseline; none | Isolated counts/timings, no providers | complete |
| WP2 | LocalAssetStore/Source + summaries; WP1 | Permanent image survives missing history/manual edits; S2 | complete |
| WP3 | Entity library/publication; WP2 | Read-only inventory, no absence-driven archival; S1/S2 | complete |
| WP4 | FileProxyClient/AIJob/Lifecycle; WP1 | Cheap inspection, verified atomic transfer, retry; S4 | complete |
| WP5 | Image admission/local evaluation/wizard; WP2/4 | Available owned images admit review, stale attempts fenced; disposable/S2 | complete |
| WP6 | Reconstruction/prompt/publication/workspace; WP4/5 | External edits allowed, managed edits fenced; disposable | complete |
| WP7 | ImageUsageService/repository; WP1 | Consumer updates + durable replay; disposable | complete |
| WP8 | Narrative/template/costume/app writes; WP7 | No automatic global scans; S1/S3 | complete |
| WP9 | Usage audit routes/Inventory; WP7/8 | Read-only GET/check, explicit safe rebuild; disposable | complete |
| WP10 | Deletion services/routes/UI; WP3/8 | Confirm and allow, managed revision fencing; disposable/S3 | complete |
| WP11 | App/index callbacks/reconciler; WP3/8 | Async coalescing, last good index retained; S1-S4 | complete |
| WP12 | Measurements/docs/ADR/final review; all | Approved E2E, diff check, final results | complete |

## Validation
Use `npm.cmd run test:e2e` (S1-S4), `git diff --check` and disposable scripts under
ignored `test-results/`. No new maintained scenarios. Compare identical fixture
operations before/after: image bytes read, full usage scans, elapsed time. Include
manual replacement, missing history/file, mismatched transfer, restart/retry,
managed-version conflicts, confirmation cancellation and maintenance outages.

## Progress and decisions
- Verified `.venv/Scripts/python.exe` is Python 3; use it throughout.
- Planning is complete; implementation and measured results recorded below.

### Implementation findings
+- Publication metadata now belongs to write operations. Moved existing unreachable
+  character/phase classification into `register_locked_pipeline_image`, so removing
+  read-time discovery does not lose phase ownership. Explicit relock restores an
+  archived publication; ordinary discovery cannot do so.
+- Changed-consumer tracking is attached at NarrativeRepository's write boundary,
+  not only authoring facade calls, because generation writes frozen references too.
+  Unchanged reference sets skip secondary maintenance. Source/template/costume
+  writers journal their file or affected scope. File absence forces a storage
+  health probe before deleting old observations.
+- Character detail/overview/prompt-observation reads also rehashed candidate images;
+  replaced those reads with saved managed versions. Missing history does not revoke
+  locks; current candidate, attempt, cancellation, evaluation and path fences remain.
+- Transfer admission is stored only in local Inbox staging. Shared markers cannot
+  confer admission. Actual bytes are verified while copied; interrupted local
+  legacy copies verify once. Domain-owned advice needs current owned files.
+- Two intermediate full E2E runs exposed an S3 retry race (QUEUED timeout).
+  Captured isolated lifecycle traces showed the generic harvester finalizing a
+  `HARVESTED_FOR_EXTERNAL_CONSUMER` marker before Narrative applied its result.
+  Generic cleanup now leaves non-`zet` consumers to their registered domain handler.
+  A disposable deterministic check guards this completion boundary. Subsequent
+  full S1-S4 runs passed (39.8s and 41.1s); final verification recorded below.
+- Confirmation covers DELETE and alternate PATCH archive routes, phase/costume
+  deletion, and recorded usages. Tokens compare catalog metadata under the catalog
+  transaction, never image bytes. Direct usages survive deletion of a historical
+  key now pointing elsewhere. Existing Narrative direct bindings can still use
+  retained archived blobs; missing files/keys are reported without preventing edits.
+- No schema migration, new dependencies, permanent tests, live inference,
+  production-library changes, external publication or deployment.
+
+### Measured baseline and comparison
+Disposable `test-results/integrity/measure.py` loads pre-change implementations from
+Git HEAD for the before run, and current implementations for after. It uses the
+same temporary generated image and authored records, warms each operation once,
+then performs five iterations. Times are local samples, not performance guarantees.
+
+| Operation (5 warm iterations) | Before ms | After ms | Image bytes before -> after | Full usage scans before -> after |
+| --- | ---: | ---: | ---: | ---: |
+| Inventory | 20.617 | 3.575 | 13,318,215 -> 0 | 0 -> 0 |
+| Character sources | 18.672 | 3.989 | 13,318,215 -> 0 | 0 -> 0 |
+| Queue inspection | 27.086 | 8.710 | 13,318,215 -> 0 | 0 -> 0 |
+| Scene saves, tiny fixture | 27.800 | 55.515 | 0 -> 0 | 5 -> 0 |
+| Scene saves, 200 authored templates | 414.123 | 47.250 | 0 -> 0 | 5 -> 0 |
+
+Inventory synchronization calls also fall from five to zero. Recovery/transaction
+cost means the tiny fixture does not demonstrate faster saves; repeated global
+scanning no longer scales save cost with the rest of the library.
+
+### Additional validation
+- `.venv/Scripts/python.exe -B test-results/integrity/check.py`: 21 disposable
+  checks passed, including corrupted transfer retention, admission reuse, generic
+  harvester/domain ownership, metadata version fencing, usage replay after catalog
+  failure, direct/key integrity, unreadable audit retention, archive/relock,
+  asynchronous index coalescing/outage/recovery, phase deletion and editable
+  unresolved Narrative references.
+- `node test-results/integrity/browser.mjs`: recorded usage display, report-only
+  check, explicit rebuild, cancelled archive and confirmed referenced archive
+  passed without JavaScript errors. Screenshot inspected at desktop size.
+- `.venv/Scripts/python.exe -B -m compileall -q zet` and
+  `node --check zet/web/static/zet.js` passed.
+- Knowledge owners updated; ADR 0023 records the durable policy and superseded
+  recurring-verification assumptions. Existing schemas and API receipt fields stay
+  readable. New confirmation bodies and explicit audit routes are documented.
+
+## Final results
+All twelve packets are complete. Final `npm.cmd run test:e2e`: **4 passed in
39.0s**, after the earlier successful post-race runs (39.8s and 41.1s). The final
transfer-error classification was then checked with the disposable suite: **21
passed**, including automatic bounded collection retry for transfer mismatch.
Python compilation, JavaScript syntax and `git diff --check` pass. Final diff
review removed unintended whitespace-only changes and confirmed no maintained
tests/dependencies/configuration or unrelated recovery work were changed.

Changed domains: available local publications; image analysis/reconstruction and
wizard sources; queue inspection/admission/cleanup; incremental usage tracking and
reference audits; confirmed deletion; asynchronous index refresh and image
metadata dependencies; owning knowledge and ADR 0023. The completed plan is the
primary record of observed validation and measured limits. No blockers remain.
Live inference and production-library performance were intentionally untested.
