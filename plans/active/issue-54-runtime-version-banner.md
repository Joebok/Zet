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
- Status: in progress.

## Validation
Planned: issue worker `validate` for the claimed revision (three approved E2E scenarios plus `git diff --check`), direct commit timestamp/hash inspection, and final diff review. No new tests or scenarios.

## Risks and alternatives
Runtime releases are Git checkouts, so release metadata is available without adding a build manifest. If metadata is unavailable in another runtime layout, the header remains empty rather than showing stale source metadata.

## Progress and decisions
- Claim selected new issue #54. Original issue has no trusted comments or screenshots.
- Verified `TaskService._revision` reads the runtime checkout's `HEAD`; deployment stages each release as a Git checkout at the requested revision.
- Added the matching committer timestamp and header presentation; validation and delivery remain pending.

## Final results
Pending.
