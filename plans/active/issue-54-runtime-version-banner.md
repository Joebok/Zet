# Runtime version information in dashboard header
Status: active
Related issue/specification: [Issue #54](https://github.com/Joebok/Zet/issues/54)

## Goal
Show the running release's commit date/time and commit ID in the dashboard title bar, with low visual emphasis.

## Current behavior
`ZetApp` constructs `TaskService`, which resolves the checked-out revision from the runtime release's Git checkout. `/api/health` also exposes that revision. The dashboard header in `zet/web/templates/index.html` has a brand area but no release metadata. The issue has no comments or screenshots.

## Desired behavior
The header shows a concise local-time commit timestamp and abbreviated commit ID. Hover/title text exposes the full commit ID and exact timestamp. If Git metadata is unavailable, no misleading version is shown.

## Impact analysis
- `zet/services/task_service.py`: expose the current revision's committer timestamp alongside the existing revision.
- `zet/web/app.py` and `zet/web/templates/index.html`: render the metadata in the brand area.
- `zet/web/static/zet.css`: style the metadata subtly and responsively.
- `Docs/CODE_MAP.md`: identify runtime version display ownership.
- No stored data or external interface changes. Existing S1–S3 validation is the approved baseline; no permanent tests are added.

## Invariants and constraints
Use only the current release checkout's own Git metadata. Do not read production libraries/queues, run live models, add dependencies, or add permanent tests. Joe owns merge and deployment.

## Implementation steps
### WP1 — Provide and display running revision metadata
- Dependencies: none.
- Files/interfaces: `zet/services/task_service.py`, `zet/web/app.py`, `zet/web/templates/index.html`, `zet/web/static/zet.css`.
- Work: read committer timestamp for the same revision as `zet_revision`; render a compact local-time label and full details in the header; omit the label if metadata is missing.
- Acceptance: rendered dashboard header identifies the release by its commit time and abbreviated ID, with full commit ID available in the title; missing Git metadata does not fabricate a value.
- Validation: inspect the revision metadata against `git show`; run the helper's revision-bound approved E2E validation and `git diff --check`.
- Status: complete.

### WP2 — Synchronize knowledge and deliver
- Dependencies: WP1.
- Files/interfaces: `Docs/CODE_MAP.md`, this plan, issue branch.
- Work: document the header metadata owner; review the scoped diff; deliver through the issue helper, mark ready, and checkpoint `needs-review`.
- Acceptance: only scoped files are changed, helper validation passes for the delivered revision, and the ready PR is recorded.
- Validation: helper `deliver` and `ready`, final helper status, `git diff --check`.
- Status: in progress; recovery and initial helper validation passed, final presentation validation and PR delivery remain.

## Validation
Direct commit timestamp/hash inspection passed. Initial helper validation failed at `f1b4bbc`: S1 could not switch to Character Development; S2/S3 passed. Investigation proved the unclipped runtime timestamp intercepted the button click. Joe committed overflow clipping and dashboard readiness assertions at `704a959`; the approved baseline passed directly (26.8 seconds) and through the recovered helper (24.5 seconds) at that revision. A disposable browser check confirmed the final two-line label fits its bounds and leaves Character Development clickable at 1280, 850, and 390 pixels; screenshots were inspected. No new maintained tests/scenarios or live checks were added. The changed final presentation requires fresh helper validation after commit.

## Risks and alternatives
Runtime releases are Git checkouts, so release metadata is available without adding a build manifest. If metadata is unavailable in another runtime layout, the header remains empty rather than showing stale source metadata.

## Progress and decisions
- Claim selected new issue #54. Original issue has no trusted comments or screenshots.
- Verified `TaskService._revision` reads the runtime checkout's `HEAD`; deployment stages each release as a Git checkout at the requested revision.
- Added the matching committer timestamp and header presentation; validation and delivery remain pending.
- The original header label combined nowrap text with a narrow maximum width and no clipping, intercepting the workspace click. Joe's clipping fix and readiness waits are retained.
- Joe explicitly authorized recovery and continuation. Confirmed the old worker stopped, recovered through the helper, posted the authorized resume instruction, and reclaimed the same branch/worktree in resume mode.
- Clipping the original long timestamp also hid the short commit ID. The final label uses two compact lines (date, then local time and short hash), with full revision and offset-aware timestamp in the title.
- Existing code-map documentation already identifies the owning service, route, template, and stylesheet; no entry points moved.

## Final results
Implementation commits `f1b4bbc` and `704a959` provide the header metadata, overflow clipping, and repaired existing S1 waits. Helper validation now passes at `704a959`. Final compact-label validation and PR delivery are in progress; Joe retains merge and deployment authority.
