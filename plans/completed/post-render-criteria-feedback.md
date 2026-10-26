# Post-render criteria and suggestion feedback
Status: complete
Related issue/specification: user-reported Costume Dressing post-render behavior

## Goal
Make costume/view criteria saves predictable, preserve them across page visits, and make every Suggest action show progress or a useful explanation. Keep existing routes and storage records; do not use production data or live inference for validation.

## Current behavior
`local_character_prompt_improvement.js` holds a criteria draft, posts the draft, and reports status in the page-wide message. The API stores criteria in the costume workspace through `CostumeAdjustmentCriteriaService`. Blank or invalid rows produce an unlocalized validation error. Suggest can be blocked by unsaved criteria with a message at the top of the page; analysis is asynchronous. A read-only production log showed rejected PUT requests while a later criteria record persisted; the exact submitted payload for the failed save is unavailable. The working tree was clean at inspection.

## Desired behavior
Save visible populated rows with stable IDs and the current revision. Make invalid rows and save progress/errors visible beside the criteria controls. Explain and focus the criteria controls when unsaved changes block Suggest. Show Suggest progress/results/failures beside its control, and prevent stale polling responses from replacing newer actions.

## Impact analysis
Frontend: `zet/web/static/local_character_prompt_improvement.js`, its HTML template and `zet/web/static/zet.css`. Backend validation: `zet/services/costume_adjustment_criteria_service.py`. Knowledge owners: Dashboard UI, Local Characters, Testing, Code Map. No API/storage migration.

## Invariants and constraints
Preserve costume/view isolation, stable criterion identities, optimistic revisions, accomplishment rules, and existing character workflows. No permanent tests, dependencies, production-library writes, live inference, or deployment. Disposable isolated checks are allowed.

## Implementation steps
### WP1 — Reliable criteria submission
- Dependencies: none.
- Files/interfaces: criteria editor JavaScript; `CostumeAdjustmentCriteriaService.save` validation messages.
- Work: build an immutable payload from visible rows, keep IDs and revision, omit empty new rows when populated rows exist, identify blank/invalid rows, disable editing during save, and retain drafts after failure.
- Acceptance: two criteria persist across reload/reopen; malformed rows retain their text and show a row-specific error.
- Validation: disposable isolated service and browser checks.
- Status: complete.

### WP2 — Visible save and suggestion states
- Dependencies: WP1.
- Files/interfaces: post-render page template and styles; criteria/suggestion controller.
- Work: add accessible inline status near each action, immediate saving/analyzing feedback, actionable dirty-criteria guidance and focus, duplicate-submit prevention, explicit empty/error results, and generation fencing for polling responses. Bump page asset versions.
- Acceptance: all save and Suggest outcomes are visible beside their controls; an older poll cannot overwrite a newer result.
- Validation: disposable browser checks with delayed responses and prepared AI outcomes.
- Status: complete.

### WP3 — Verification and documentation
- Dependencies: WP1–2.
- Files/interfaces: affected docs and this plan.
- Work: run requested isolated checks, approved E2E baseline, syntax checks and diff check; update workflow/validation docs with observed limits; archive this plan after completion.
- Acceptance: checks and final diff are recorded; no permanent test, live inference or production-library mutation.
- Validation: `npm.cmd run test:e2e`, changed JavaScript syntax checks, `git diff --check`.
- Status: complete.

## Validation
- `npm.cmd run test:e2e`: passed all four approved scenarios (38.2s).
- `node --check zet/web/static/local_character_prompt_improvement.js`, `python3 -m py_compile zet/services/costume_adjustment_criteria_service.py`, and `git diff --check`: passed.
- Disposable service check passed two-item persistence/reload, row-specific rejection, and failure atomicity.
- Prepared-response Chromium check passed blank-row omission, retained text and invalid marker after server rejection, dirty-criteria guidance, suggestion progress/empty/error feedback, and delayed-poll fencing after a newer save.
- No live inference, permanent tests, dependencies, or production-library writes.

## Risks and alternatives
The exact rejected payload is unavailable. Inspect actual submitted values in disposable checks and retain row-specific server validation to make future failures diagnosable.

## Progress and decisions
Plan was created before implementation. A browser check found and fixed an invalid-row marker being lost when redraw followed a rejected save. Server validation messages now include criterion positions. No storage/API changes were needed.

## Final results
Implemented in the criteria service, post-render page/controller and styles. Updated dashboard and testing documentation. All validations passed; final diff reviewed. No unresolved work.
