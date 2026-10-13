# GitHub task capture, local pickup and deployment

## Capture
Create task publishes a public issue in the configured repository (Joebok/Zet).
Start Codex work defaults on; uncheck it to Save for later. Original description,
expected/actual behavior, reproduction steps and success criteria are preserved.
Missing criteria remain explicitly unspecified. Explicit providers freeze page,
universe, selection IDs/labels/availability, timestamp, revision, viewport and
selected control. Preview the public text and selected screenshots. Prompts,
source documents, complete records, arbitrary browser state and private paths
are not automatically published. Return to Zet restores supported selections
through read requests without starting jobs or changing the global universe.

The browser keeps one draft per origin. Refresh context is explicit. First delivery
freezes report, repository and screenshot list. Upload/paste up to four valid
PNG/JPEG/WebP images, 5 MiB each. Storage failure warns that only the current tab
retains the draft. Failure never discards it. Convert Kanban draft preserves a
browser backup and allocates a new ID; previous Kanban delivery may already exist.
Old Kanban files are not read, edited, deleted or automatically republished.

## Services, publication and configuration
[TaskService](../zet/services/task_service.py) uses the authenticated server-side
[gh adapter](../zet/services/github_client.py); credentials stay out of browsers.
[TaskWorkflowRepository](../zet/repositories/task_workflow_repository.py) owns
task-workflow.sqlite3 outside Git/library. `[GitHub]` settings: Repository (owner/name
or empty), TimeoutSeconds (20), StatePath, UsageReservePercent (10), TrustedUsers
(Joebok). Empty repository disables delivery without blocking startup. Config
readiness does not imply authentication/reachability. GitHubByPlatform and
RuntimeByPlatform apply host-specific paths, like existing BaseFoldersByPlatform;
other hosts retain normal startup without a Windows runtime path.

- `GET /api/tasks/config`: local repository/issues URL/readiness/context version/revision.
- `POST /api/tasks/preview`: the issue formatter used for publication.
- `POST /api/tasks/attachments`: validated, content-addressed screenshot receipts;
  URLs pin commits on codex/issue-evidence, which is never merged/deployed/pruned automatically.
- `POST /api/tasks`: frozen report; returns repository, issue_number, issue_url, created.
  HTTP 201 is creation and 200 is replay. Readiness follows complete evidence/issue publication.
- `GET /api/tasks/status`: cached attention, worker freshness, usage and deployment.

Request IDs bind repository and canonical report hash. An uncertain receipt is
committed BEFORE GitHub creation. Retry reconciles the unique issue-body marker;
unresolved delivery never blindly creates again. Edited recovered issues require
inspection. Changed content/repository under the same ID is a conflict. Explicit
rejection can be retried after correcting host setup. Screenshot links preserve
original bytes and SHA-256; no silent resizing occurs.

## Pickup, limits and attention
[CODEX_WORKFLOW](../.github/CODEX_WORKFLOW.md) owns authorization, states, selection,
trusted resumption and delivery. [SCHEDULED_PICKUP](../.github/SCHEDULED_PICKUP.md)
is the saved prompt. A local project task polls every 30 minutes in isolated
worktrees; the PC/app must run. Polling itself consumes capacity. One helper claim
owns coding; interrupted ownership never auto-transfers. Explicit recovery requires
an operator to confirm the old worker stopped before inspecting/resuming retained work.

[CodexUsageService](../zet/services/codex_usage_service.py) reads account/rateLimits/read
over stdio without a model turn. Applicable returned Codex windows show remaining
percent/reset times. Unknown/stale quota pauses claims. The default reserve is 10%.
Retained usage-wait work resumes when fresh capacity permits. No automatic purchases
or earned-reset consumption occurs.

[TaskStatusService](../zet/services/task_status_service.py) polls GitHub every minute
and quota every five minutes. Tasks shows questions, ready PRs, failures, unavailable
worker, quota waits and merged updates. Questions/reviews link to GitHub; v1 has no
reply/merge UI. Worker freshness is stale after 70 minutes; a claim without heartbeat
for an hour needs inspection. Unchanged polls do not produce repeated notifications.

Worker mode rejects non-development configurations. Development library/queue paths
must be inside their fixture config directory; external candidate documents are
excluded. Additional writable roots contain coordination state, not production
releases, authored libraries, shared queues or machine indexes. Existing inspection
fixtures/prepared responses own browser checks; no live checks are authorized.

## Production runtime
[DeploymentService](../zet/services/deployment_service.py) stages merged origin/main
in Zet_Runtime/releases/<sha> with its own Python environment. Stable state lives in
Zet_Runtime/state. Creative library/queue paths stay unchanged. Release-local
config.runtime.toml preserves code/template-root assumptions; universe selection,
renderer presets and model caches have explicit persistent-state paths.

Restart offers Update and restart or Restart current version. Update stages and
runs the approved isolated baseline BEFORE stopping production. The controller is
copied outside releases; a check lock serializes worker/staging fixed-port tests.
`GET /api/deployment` reports status; `/stage` validates without promotion; `/update`
promotes after validation. Development fixtures cannot deploy.

Health includes revision, boot_id and role/config identity. Process matching uses
exact config identity; deployment rechecks Windows command lines before stopping
captured PIDs. Completion requires the expected revision and a new boot. Failed
startup restores the previous release/environment, or the original exact command
on first adoption. Creative data is not rolled back. Logs/records remain in state;
an interrupted operation is inspected rather than starting a duplicate update.

Config/Runtime_Contract.json declares deployment compatibility; it is NOT a library
schema version. Missing/changed contracts, manual-migration releases and tracked
production edits block updates. Incompatible authored-data changes must change this
declaration and provide an explicitly reviewed migration. Code rollback does not
establish data rollback safety. After promotion, run run_zet_runtime.bat independently
of the development branch. First promotion requires merged main to contain this workflow.

## Validation and rollout
The maintained three fast scenarios are unchanged. Disposable capture/browser,
coordination/quota and two-instance recovery checks cover added interfaces; no new
permanent suite or live rendering is implied. Enable scheduling after one real
small-issue pilot. Retire remaining Kanban execution only after three correct
issue-to-PR deliveries, preserving unfinished work for deliberate migration.
The active plan records observed results and outstanding rollout gates.
