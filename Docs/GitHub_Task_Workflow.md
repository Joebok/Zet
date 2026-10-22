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
worktrees; the PC/app and local Zet server must run. A private loopback bridge
keeps GitHub/usage credentials on the host when the nested sandbox cannot access
its credential store. Its bearer is only in machine-local state, never the browser.
It permits issue reads, claimed-issue labels/comments, pinned evidence and scoped
draft/ready delivery; merge/deployment and other repositories are excluded.
Git bundles are imported/pushed from a protected bare transfer directory; host git
is never executed in an agent-controlled worktree (hooks/config could escape its
sandbox). Helper context/evidence/deliver/ready use this bridge. Polling itself consumes capacity. One helper claim
owns coding; interrupted ownership never auto-transfers. Explicit recovery requires
an operator to confirm the old worker stopped before inspecting/resuming retained work.

The worker must diagnose validation failures and attempt a scoped repair before
escalating, unless a demonstrated constraint prevents the attempt. The required
repair loop, checkpoint selection, and blocker report are owned by
[Validation failures and escalation](../.github/CODEX_WORKFLOW.md#validation-failures-and-escalation)
and applied by the saved pickup prompt. These are worker instructions; the helper
does not mechanically verify diagnosis or repair attempts.

The coordinator runs from the development checkout with an explicit isolated
`claim --worktree` target; coding/tests use the returned worktree. `reconcile`
reads retained ready PRs and records validated merged deliveries as completed
without changing GitHub or deleting work. Claim also performs reconciliation and
skips completed issues even if their GitHub label is still ready. Waiting reviews
do not block independent ready work. Scheduled runs must actually call claim
rather than infer queue state from an old checkpoint. Memory records each helper
result. Runs with no eligible work can be archived after recording their result;
busy, quota-limited, active, and attention-needed runs stay visible. Unchanged
results do not produce attention notifications.

[CodexUsageService](../zet/services/codex_usage_service.py) reads account/rateLimits/read
over stdio without a model turn. Applicable returned Codex windows show remaining
percent/reset times. Unknown/stale quota pauses claims. The default reserve is 10%.
Fresh host readings expire after five minutes. A nested Codex sandbox may lack
account access; native tasks can import the app usage-limits tool reading rather
than bypass quota. Retained usage-wait work resumes when fresh capacity permits. No automatic purchases
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
promotes after validation. The root `config.toml` used by the active checkout may
have local edits: deployment carries that exact file into the next release's
runtime config. Other tracked edits remain blocked unless governing template edits
were published and merged. Development fixtures cannot deploy.

Health includes revision, boot_id and role/config identity. Process matching uses
exact config identity; deployment rechecks Windows command lines before stopping
captured PIDs. Completion requires the expected revision and a new boot. Failed
startup restores the previous release/environment, or the original exact command
on first adoption. Creative data is not rolled back. Logs/records remain in state;
an interrupted operation is inspected rather than starting a duplicate update.

Config/Runtime_Contract.json declares deployment compatibility; it is NOT a library
schema version. Missing/changed contracts, manual-migration releases and tracked
unreconciled production edits block updates. Incompatible authored-data changes must change this
declaration and provide an explicitly reviewed migration. Code rollback does not
establish data rollback safety. After promotion, run run_zet_runtime.bat independently
of the development branch. First promotion requires merged main to contain this workflow.

### Accepted template edits and update recovery

Restart previews local tracked edits and offers **Create template PR** for global
sections and the four active character governing templates. Review the diffs and
select files. Other code/config edits remain blockers; character/costume library
sources are excluded. Promotion itself does not publish anything.

[TemplatePublicationService](../zet/services/template_publication_service.py)
captures exact bytes/baselines outside Git, applies their patch three ways onto
fetched main in a private checkout, runs the approved isolated baseline, then pushes
`codex/template-edits-<id>` and creates a PR using existing host credentials. Live
HEAD, index, templates and creative records stay unchanged. Reopen Restart to see
progress; after a server interruption use **Retry if interrupted**. Uncertain
delivery reconciles the same branch/PR. Failed attempts/snapshots are retained.

Publication checkouts and new staged releases enable Git `core.longpaths` locally
before checkout, because their nested runtime directories can exceed Windows'
default Git path limit even when the source checkout succeeds. This does not
change user/global Git configuration. A publication failure before its commit
checkpoint can use **Retry if interrupted** after the running publisher has the
fix; the retry retains the captured template bytes and uses a fresh checkout.

Use **Open PR**, merge on GitHub, then **Check merge status** and **Update and
restart**. Neither merge nor update is automatic. Update refreshes GitHub proof:
the PR must have merged into this repository's main with the published head, the
target must contain that merge and the exact published template blobs, and local
raw bytes must still match the capture. Git contents normalize CRLF/LF. Newer local
or target edits and unrelated tracked changes remain blockers. The final check
shares a cross-process fence with master promotion; the old release retains its
edits for rollback. Receipts belonging to earlier releases do not affect new ones.

Promotion merges profiles shipped in the release into runtime
`Local_Render_Presets.json`. Existing mutable-state definitions win same-name
conflicts, production-only custom profiles are retained, and missing release
profiles are added.

Three-way conflicts require reconciliation of retained work; no resolution is
invented. Selected edits already matching main produce no PR diff and stop with a
retained snapshot and explicit reconciliation message. Closed/unmerged PRs remain
blocked. Failed/conflicted/closed attempts permit a fresh reviewed snapshot.

`GET /api/deployment` adds compact `local_edits` blockers/publication status.
`GET /api/deployment/templates` supplies diffs/snapshot identity; POST accepts
selected paths and expected identity. POST `/api/deployment/templates/{id}/refresh`
checks merge status; `/retry` resumes publication. Development instances cannot
publish/deploy. Existing dashboard access boundaries apply; credentials are never
sent to the browser.

### First installation of template recovery

The old updater cannot consume new receipts. With separate deployment
authorization, an operator/agent first backs up exact dirty template bytes and
baseline outside the release, publishes only those edits, and merges the PR.
Verify fetched main preserves them and the live file still matches the backup.
Only then reconcile that named file for the old guard and invoke the existing
managed update. Preserve the backup/old release; never broadly reset/stash or drop
other edits. Arrange a quiescent handoff before restoring an earlier template.
Implementation/isolated validation does not perform this production action.
Subsequent recoveries retain live bytes and require no routine filesystem cleanup.

## Validation and rollout
The maintained three fast scenarios are unchanged. Disposable capture/browser,
coordination/quota and two-instance recovery checks cover added interfaces; no new
permanent suite or live rendering is implied. Enable scheduling after one real
small-issue pilot. Retire remaining Kanban execution only after three correct
issue-to-PR deliveries, preserving unfinished work for deliberate migration.
The active plan records observed results and outstanding rollout gates.

Existing-PR delivery refreshes its title and description as well as its branch, so
validation and original-problem acceptance remain current after a retained retry.
To resume a question with an existing PR, answer on the issue while it has
`needs-input`; changing it to `codex-ready` alone does not supersede that PR.
