# Re-run rejected character images
Status: complete
Related specification: user-approved plan in this chat

## Goal
Make Re-run failed replace human-rejected images as fresh renders and renderer failures as frozen retries across all five local character pipelines. Show blocked and partial requests in Activity.

## Current behavior
The shared view planner selects only `render_status == FAILED`; the browser enables the control on that condition, and Activity omits BLOCKED/PARTIAL. Two saved Head-Image Edit Final requests for Tsaeytte Youth BACK_LEFT_3_4 were blocked despite seven rejected images.

## Desired behavior
Target only failed or rejected slots in the requested mode and view. Recheck eligibility at commit. Preserve kept, selected, and locked images. Show actionable operation outcomes until dismissed.

## Impact analysis
Shared slot planning/preparation services, operation repository/list, shared browser controls and Activity. No serialized migration. Update Local Characters and Dashboard UI docs.

## Invariants and constraints
Maintain universe isolation, reservation identity and seeds, frozen render retries, current inputs for new renders, slot membership, and selected/locked protection. No new permanent tests or live renders.

## Implementation steps
### WP1 — Shared targets and commit guards
- Dependencies: none.
- Files/interfaces: `local_pipeline_slot_planning_service.py`, `local_pipeline_available_preparation_service.py`.
- Work: include rejects, distinguish retry from regeneration, recheck source eligibility at commit.
- Acceptance: mixed failed/rejected/kept view reserves only eligible slots; stale review blocks replacement.
- Validation: disposable Python fixture.
- Status: complete.

### WP2 — Browser and Activity
- Dependencies: WP1.
- Files/interfaces: `local_asset_pipeline.js`, `local_pipeline_operations.js`, operation repository/service.
- Work: recognize rejects; retain blocked/partial attention with dismissal and latest-first ordering.
- Acceptance: blocked request remains visible after settling and names action/view.
- Validation: disposable browser check.
- Status: complete.

### WP3 — Verification and knowledge
- Dependencies: WP1–WP2.
- Files/interfaces: `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, `Docs/COMPONENTS/DASHBOARD_UI.md`, plan record.
- Work: validate five pipelines and Draft/Final, run approved E2E and diff check, document result, archive plan.
- Acceptance: checks pass or limits recorded.
- Validation: `npm run test:e2e`; `git diff --check`.
- Status: complete.

## Progress and decisions
Existing unrelated dashboard startup edits are preserved.
The five pipelines use the same planner and preparation path. Failed renders retain
their frozen retry path; completed rejects use regeneration and current inputs.

## Final results
Shared planning and commit guards, Activity persistence/ordering, browser eligibility,
and cache versions were updated. Disposable planning checks passed for five pipelines
in both Draft and Final with mixed failed/rejected/kept images. Disposable checks
confirmed protected and kept slots are not targeted, and a Chromium check confirmed
blocked Activity entries show the rerun action, view, reason and Dismiss. Python
compilation and changed JavaScript syntax checks passed. The approved fast E2E suite
passed 4/4 (43.7s); `git diff --check` passed. The stale-review commit guard was
inspected in source but not exercised in a full transaction fixture. No live render
was started. Prior blocked requests remain records and need a fresh submission.
