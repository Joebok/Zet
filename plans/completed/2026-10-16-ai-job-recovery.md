# AI job collection, recovery, and follow-up ordering

Approved and implemented 2026-10-16. Companion: [AI_Proxy plan](../../../AI_Proxy/plans/completed/2026-10-16-ai-job-recovery.md).

## Outcome and contracts

Concurrent producer workflows remain supported: one non-preemptive local slot and two independent Codex slots. Only a successful durable image harvest permits image-based continuation. Preserve protocol/request v1, universe/producer ownership, attempt fences, immutable requests, locked assets and receipts. No live deployment, queue repair, new dependency or permanent test is authorized by this implementation.

## Ordered Luna-sized packets

| Packet | Owned responsibility | Depends on | Acceptance / validation | Status |
|---|---|---|---|---|
| 1 | AIJobService, repository, readiness: read-only inspection, dual outcome validation, staged diagnostics | — | Failed collection remains visible, retained payload and identity unchanged; disposable prepared checks | Complete |
| 2 | Image generation, image handler: disk discovery, shared request locking, atomic saves and completion | 1 | Two hosts see new jobs and apply once; disposable checks | Complete |
| 3 | Coordinator, harvest entry point, Body collector: failure isolation and universe ownership | 1 | Missing run does not block other consumers/universes; existing S4 | Complete |
| 4 | Reconstruction preparation and continuations: deterministic resume and frozen-input verification | 2,3 | Resume uses one reconstruction/request; disposable checks | Complete |
| 5 | Minor review, local gates/ranking: durable image barrier, fenced deterministic continuation, initialize gate record | 1–4 | No premature/duplicate analysis; existing S2 and disposable checks | Complete |
| 6 | Render/gate/structured waits: queue time is not execution failure | 1,5 | Long pending work is retained without new attempt; disposable checks | Complete |
| 7 | AI_Proxy native provider worker | — | Companion plan; six existing isolated scenarios | Complete |
| 8 | Queue UI/query and focused recovery service: RECOVERY_REQUIRED, diagnostic actions, dry-run inventory | 1–7 | Accurate shared statuses; report matches authoritative owners, no live mutations | Complete |

## Knowledge and validation

Affected owners: Docs/COMPONENTS/{AI_JOBS,QUEUES,LOCAL_CHARACTERS}.md, Docs/{INVARIANTS,DATA_MODEL,CODE_MAP,Testing}.md; proxy provider/scheduling docs. Update only changed contracts. Run npm.cmd run test:e2e, proxy's six isolated tests, and git diff --check. Extra Zet checks are disposable and isolated; no permanent coverage expansion. Finish with a concrete recovery report and deployment prerequisites; production apply requires separate approval.

## Progress / evidence

- Investigation baseline: Zet 4 fast scenarios passed; proxy 6 scenarios passed. Ten retained harvest failures have successful worker/transport outcomes and valid images. Live state remains untouched.

## Implementation evidence and deviations

- All eight packets are implemented. New filesystem failures schedule collection-only retries with bounded delay. Historical failures without retry metadata remain unchanged.
- Added the focused image admission helper, recovery inventory service/CLI and ADR 0017. Existing wire/catalog formats and scheduler capacities are unchanged.
- Corrected the existing S4 helper's invalid proxy outcome `SUCCESS` to `SUCCEEDED`; its scenario purpose is unchanged.
- Disposable checks passed: an existing collector discovers a disk request; two OS processes collect one image; interrupted image/receipt commit recovers; retained-image retry does not rerun execution; failed transport rejects worker success; image/cancellation barriers reject premature advice; deterministic gate identity survives lost gate state; reconstruction reuses frozen preparation; long queue wait remains collectable; mixed Image Generation/Assembly/Minor work dispatches once; new I/O collection retry succeeds; a failing legacy collector does not block another handler.
- Final observed validation: `npm.cmd run test:e2e` **4 passed in 33.4 s**; proxy `.venv/Scripts/python.exe -m pytest tests/test_e2e.py -q` **6 passed in 8.80 s**. Changed Python AST parsing, `node --check zet/web/static/ai_queue.js`, and both `git diff --check` passed. No permanent scenario/dependency added. No live model check performed. Narrative polling also uses the common dual-outcome check and retains collection failures separately from execution failures; the focused existing Narrative scenario passed after this change.

## Deployment and historical-job report

- User clarified that robust new jobs take priority and historical repair is unnecessary. No live job, route or library repair was performed.
- Read-only command: `python3 -B -m zet.scripts.inspect_ai_recovery --queue-root E:/Zet/AI_Queue --library-root E:/Zet/Zet_Library_v5/Moonsea --universe Moonsea`. Captured JSON is in ignored `test-results/ai-recovery-report.json`; no runtime app was constructed. Of ten investigated harvest failures, five current Image Generation answers are eligible for collection retry, one Minor answer is obsolete, and four old answers lack inventoried auxiliary files as well as routes. A valid PNG alone does not authorize application.
- Zet's running release was `ea44249b`; it was not promoted or restarted. Production promotion remains separately approved through the documented release workflow. Dashboard and standalone collector must use the same new release.
- AI_Proxy's native registry starts worker subprocesses from its project checkout. Subsequent worker launches can load the modified module without a runtime restart. No backend ownership or scheduler configuration changed. Use the normal managed UI for a deliberate consistent-runtime restart, waiting for active workers instead of killing them.
- Rollout needs no schema migration, historical cleanup, new dependency or automatic execution retry. Observe new queued/render/harvest/review transitions after approved rollout; a live model check and permanent coverage expansion remain separately gated.
