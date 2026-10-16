# Remove character pipeline gates
Status: in progress
Related issue/specification: User-approved plan in task conversation.

## Goal
Remove defect gates and gate test infrastructure from the four active local character pipelines while retaining ranking, human review, automatic selection, and publication.

## Current behavior
Body-Reference, Head-Image, Character-Assembly, and Costume-Dressing submit defect-review jobs before ranking. Gate results persist in candidate state. Gate settings, test-case images, saved test runs, and API routes live under `PipelineCandidates/Gate-Test-Rig`. The dashboard exposes policy controls and Gate Test Rig/Data pages. Autogenerate currently requires a current, gate-approved FRONT ranking.

## Desired behavior
Rendered candidates proceed directly to ranking and human review. Autogenerate may select the original current Luna #1 FRONT candidate if its image and ranking are valid and Joe has not rejected it. No gate jobs, result data, settings, pages, or routes remain.

## Invariants and constraints
- Preserve candidate images, source snapshots, human decisions, selections, image locks, and universe ownership.
- Preserve shared queue ownership, attempt fencing, normal image review and prompt-improvement, and ranking validation.
- Do not remove unrelated schema validation, Minor Character behavior, image-recipe quality review, or historical completed plans/ADRs.
- Live library/queue cleanup requires an inventory, backup, quiescence, and explicit approval after the report.
- Use the existing four-scenario E2E baseline; no new maintained scenarios or dependencies.

## Implementation packets
### WP1 — Gate-free stored-state contract and migration
- Dependencies: none.
- Files/interfaces: `local_image_pipeline_policy.py`; new migration service and CLI.
- Work: add an idempotent dry-run/apply converter and backup manifest; strip gate-only fields from specs/state/legacy copies; convert gate-waiting/rejected candidates with valid images to human review; retain images, selections, decisions and locks; mark rankings from the retired review contract stale; advance review contract to v3.
- Acceptance: v1/v2 fixtures convert idempotently and preserve image hashes and publication bindings; malformed JSON is reported and blocks apply.
- Validation: isolated disposable migration fixture checks and CLI dry run.
- Status: implemented; disposable conversion/idempotence/checksum/backup/rig checks passed. No legacy review copies were present in the live inventory.

### WP2 — Retire gate queue jobs and late answers
- Dependencies: WP1.
- Files/interfaces: `ai_queue_lifecycle_service.py`, `ai_answer_harvester.py`, migration service/CLI.
- Work: find exact gate task types; back up and fence owned work; remove owned payload/history/evidence without changing unrelated producers; remove gate-specific stale-answer handling.
- Acceptance: late answers cannot mutate batches; unrelated queue work still collects.
- Validation: isolated queued/completed/late-answer checks.
- Status: implemented; disposable queue test passed for queued, running, late-answer, receipt, job-record and evidence cleanup, with unrelated work preserved.

### WP3 — Ranking-only evaluation service
- Dependencies: WP1–WP2 contract.
- Files/interfaces: `local_image_evaluation_service.py`, `local_image_pipeline_policy.py`, `candidate_review_contract.py`.
- Work: remove gate worker/callback/status contracts and verdict parser; retain ranking jobs, IDs, hashing, recovery, and supersession; finish evaluations from ranking outcomes.
- Acceptance: ranking and recovery proceed without gate state; superseded work cannot commit.
- Validation: disposable ranking success/failure/recovery checks.
- Status: implemented; end-to-end ranking path passed. Ranking terminal states now finish evaluation records.

### WP4 — Remove Body-Reference gates
- Dependencies: WP3.
- Files/interfaces: `local_body_reference_service.py`.
- Work: remove face and review gate prompts, dispatch/collection, eligibility and gate-only retries; retain analysis, ranking, selection, and human rejection rules.
- Acceptance: valid candidates can rank and select without gate jobs.
- Validation: prepared-response Body-Reference checks.
- Status: implemented; broader pipeline E2E passed, with no live ranking/render calls.

### WP5 — Remove Head-Image gates
- Dependencies: WP3.
- Files/interfaces: `local_head_image_service.py`.
- Work: remove gate prompts, dispatch/collection and eligibility; retain anchor requirements, ranking and image checks.
- Acceptance: candidates rank/review without gate jobs.
- Validation: prepared-response Head-Image checks.
- Status: implemented; broader pipeline E2E passed, with no live ranking/render calls.

### WP6 — Remove Assembly and Dressing gates
- Dependencies: WP3.
- Files/interfaces: `local_character_asset_pipeline_service.py`.
- Work: remove gate prompts, source-role bindings used only by gates, jobs/collectors and eligibility; retain rendering source dependencies, costume isolation, ranking and locks.
- Acceptance: existing Assembly-to-Dressing flow remains intact without gates.
- Validation: existing E2E scenario and prepared responses.
- Status: implemented; approved character-to-costume E2E scenario passed.

### WP7 — Remove gate dependencies from automation and slot work
- Dependencies: WP4–WP6.
- Files/interfaces: overview/run-all/slot services and relevant app lifecycle hooks.
- Work: remove gate checks from Autogenerate, run-all, recovery and slot completion; preserve Luna #1, current ranking/image, human rejection and lock checks.
- Acceptance: automation selects eligible #1 without gate results; human rejection still blocks.
- Validation: disposable automation, slot, and restart checks.
- Status: implemented; Autogenerate still requires current Luna #1, current ranking/image and no human rejection. Slot and restart behavior were not exercised against live work.

### WP8 — Remove dashboard gate controls
- Dependencies: WP7.
- Files/interfaces: local pipeline/dashboard JavaScript, `index.html`, `zet.css`.
- Work: remove gate settings, badges, rejection details, prompt dialogs, progress labels, events, requests and navigation; keep ranking/review/polling behavior.
- Acceptance: all four pages have no gate controls or requests and preserve unsaved review state.
- Validation: disposable browser checks at the existing E2E fixture.
- Status: implemented; the approved browser baseline passed. No permanent tests were added.

### WP9 — Remove rig, data-set APIs, and configuration
- Dependencies: WP2, WP4–WP8.
- Files/interfaces: gate services/templates, web routes, config/control/model-picker/task-report modules.
- Work: remove both test pages, their services and all rig/data/local-gate endpoints; remove image add/edit/upload, saved-run and report functionality; remove gate model setting and active docs. Extend migration cleanup to the rig directory and gate-only backup copies without deleting shared analysis data.
- Acceptance: removed routes return 404; configuration loads; live implementation has no gate references outside migration compatibility.
- Validation: source search, route check, configuration load.
- Status: implemented; obsolete pages, endpoints, services and settings are removed. App startup/configuration passed through E2E, and a fixture route-table check confirmed the retired paths are absent (404).

### WP10 — Documentation, verification, and live cutover
- Dependencies: WP1–WP9.
- Files/interfaces: architecture, local-character, data-model, invariants, queues, code map, testing docs, ADR, E2E helper.
- Work: update owned knowledge; repair prepared-answer helper; run approved `npm.cmd run test:e2e` and `git diff --check`; dry-run migration against isolated copies; create live data inventory and backup plan; after explicit approval quiesce work, back up, migrate and verify.
- Acceptance: four approved scenarios pass; isolated migration preserves images/locks; live cutover contains no gate state or feature data; plan records observed results and is archived.
- Validation: approved baseline, disposable migration/queue/browser checks, final search/diff review, then live verification after approval.
- Status: live data cutover and verification complete; restart is pending deployment of the updated application.

## Progress and decisions
- Confirmed by user: retain automatic FRONT selection of current Luna #1 while respecting manual rejection.
- Implementation removed gate workflows from the four pipelines, dashboard, app routes, configuration, queue reconciliation and task helpers; review records now use version 3. The retirement service and CLI keep stored-state conversion explicit, backed up and idempotent.
- `npm.cmd run test:e2e`: 4 passed. Disposable library conversion and queue fencing/ownership checks passed. `python3 -m compileall -q zet`, JavaScript syntax checks, and `git diff --check` passed.
- Read-only live inventory on 2026-10-16: 10 runs, 507 candidate records, 344 existing image files, 0 missing image paths; all 10 runs need conversion. No legacy review copies. One Gate-Test-Rig root contains 2 files totaling 650 bytes. No matching queue jobs, GateEvidence folders, malformed records, or blockers.
- Approved cutover applied at 2026-10-16 15:08 local. Backups and verification records are under `E:\Zet\Gate_Retirement_Backups`; all 10 runs converted, the rig was backed up and removed, and no queue items needed removal/fencing.
- Post-cutover checks confirmed 344 image files unchanged, zero missing images, unchanged selection/human-review values, unchanged Assets tree and catalog checksum, no gate fields in current run records, and no remaining rig/evidence/jobs. A second dry run reports zero changes and no malformed records.
- Zet runtime and its auto-harvester are stopped; AI_Proxy and unrelated queue work remain running. Disabling the `\Zet\Run Zet` logon task was denied by Windows, so it remains enabled. Keep the plan active until the task is disabled or updated and the new application release is deployed; do not restart the old release.

## Final results
Code implementation and live data conversion are complete. The plan remains active until the updated application can be safely deployed and restarted.
