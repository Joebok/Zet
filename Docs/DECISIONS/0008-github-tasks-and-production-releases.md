# 0008 — GitHub tasks and isolated production releases
Status: accepted
Date: 2026-10-13

## Context
Joe approved replacing Kanban capture/execution with GitHub issues and scheduled
Codex pickup, retaining original intent and usable screenshots. Development must
not change running production code or use its creative data for tests.

## Decision
GitHub owns task states; machine-local SQLite owns receipts and fenced checkpoints.
Existing capture providers remain. Screenshot URLs pin commits on a separate branch
because installed gh lacks attachment upload. Native scheduled Codex performs coding;
a deterministic helper owns claims, quota checks and revision-bound local validation.
Joe owns review, merge and deployment. Production uses versioned releases/environments
and stable state. An external controller stages before promotion and checks health
by revision/boot. Authored-data compatibility is an explicit migration gate.

## Alternatives and tradeoffs
Kanban's execution engine retains the manual operations Joe wants to remove. Cloud
pickup needs separately packaged local context and a cloud environment. Public
evidence is Joe's selected default and grows Git history; no automatic deletion is
implied. Native polling consumes capacity and requires the PC/app. Evidence upload
and issue creation have no shared transaction, so uncertain delivery is reconciled
conservatively. Code rollback cannot roll back authored data safely.

## Consequences and verification
Original reports and actual screenshots remain acceptance inputs at every stage.
Unknown quota/ownership stop new work. Runtime state differs from entity catalogs
and machine indexes. S1–S3 remain the only permanent fast scenarios. Disposable
checks and the real pilot establish observed behavior; rollout gates stay in the plan.

## Related sources
- [Workflow](../GitHub_Task_Workflow.md), [Codex authority](../../.github/CODEX_WORKFLOW.md)
- [Active plan](../../plans/active/github-issue-workflow.md)
- [TaskService](../../zet/services/task_service.py), [worker](../../zet/services/issue_worker_service.py), [deployment](../../zet/services/deployment_service.py)
