# Repair GitHub pickup
Status: complete
Related: [GitHub workflow](../../.github/CODEX_WORKFLOW.md)

## Goal and current behavior
Scheduled runs inspect retained #42/PR #43 instead of claiming the current queue,
then disappear into archived chats. PR #43 is merged but local state still says
needs-review; #42 remains ready because its pilot PR targeted a feature branch.
The bridge is available and quota exceeds the reserve. Preserve all retained work,
singleton fencing, quota guards and the approved three-scenario baseline.

## Impact and documentation
Worker service/CLI own merge reconciliation; no schema change or bridge permission
expansion. Workflow and saved prompt own queue polling and run history. Update
Docs/GitHub_Task_Workflow.md; code map, architecture and invariants keep their owners.
No production restart, merge, dependencies, permanent tests or unrelated issue work.

## Luna sized packets
### WP1 — Reconcile merged deliveries
- Dependencies: none.
- Files: zet/services/issue_worker_service.py, zet/scripts/issue_worker.py.
- Work: reconcile validated merged PRs to completed local records before selection;
  skip completed issues and reject attempts to revive their tokens.
- Acceptance: merged #42 cannot be reclaimed; waiting reviews do not block #44;
  active ownership and quota failures remain fenced.
- Validation: disposable fake-GitHub/store checks; existing npm run test:e2e.
- Status: complete.

### WP2 — Correct scheduled polling and history
- Dependencies: WP1.
- Files: .github/SCHEDULED_PICKUP.md, .github/CODEX_WORKFLOW.md,
  Docs/GitHub_Task_Workflow.md; saved automation prompt/memory.
- Work: always reconcile and call claim in an isolated worktree; select retained
  coding worktree only after helper selection; keep run history and record decisions.
- Acceptance: no early exit based on cached review state; Luna/High, cadence,
  bridge-only credentials and notification intent preserved.
- Validation: inspect saved automation fields and prompt; git diff --check.
- Status: complete.

### WP3 — Repair current retained state
- Dependencies: WP1-2.
- Work: verify PR #43 delivery is included in main, close completed #42 and reconcile
  its local record. Verify #44 eligibility with disposable selection, without taking
  a real claim away from the next scheduled worker.
- Acceptance: #42 completed locally and closed on GitHub; #44 remains ready for pickup.
- Validation: read-only GitHub, helper/status and isolated selection checks.
- Status: complete.

## Validation and final results
New worker contracts use disposable checks; S1–S3 do not cover GitHub selection.
No live checks or additional maintained scenarios.

- Disposable test-results/check-pickup-repair.py passed: real #44 eligibility with
  fake writes, merged #42 skipping/idempotence, completed-token rejection,
  independent pickup while review waits, busy ownership, quota pause and rollback
  for a merged revision mismatch. No real claim was taken by the checks.
- npm.cmd run test:e2e with ZET_WORKER_MODE=1 and verified project Python passed
  all three approved scenarios in 23.3s. git diff --check passed; final diff reviewed.
- Real bridge-backed reconcile recorded #42 completed at its validated revision.
  Verified PR #43 merge 71cb0a0 is an ancestor of origin/main before removing
  codex-ready and closing the leftover issue. Worktree/evidence retained.
- Saved automation is ACTIVE with Luna/High, unchanged 30-minute cadence and
  reserve. Every poll calls claim; coordinator uses current development code and
  an explicit isolated target. Chats stay visible; latest archived run restored.
- Corrected automation memory supersedes stale review-wait assumptions. The next
  live scheduled #44 implementation/delivery has not yet been observed; no claim,
  merge, deployment or normal-library/queue changes were made by this repair.
