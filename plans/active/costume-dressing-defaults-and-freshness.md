# Costume Dressing defaults and freshness
Status: active
Related issue: Gia/Luna resume run 2026-11-13T19-32-25-242Z-287f661a

## Goal
Align unsaved Dressing quarter-view controls and requests, and make Earlier prompt reflect current master prompt text compiled with each candidate's captured render settings.

## Implementation packets
### WP1 - Align default settings
- Dependencies: none.
- Files: zet/web/static/character_asset_container.js.
- Work: Default unsaved quarter views to Doll-dressing (w/ Ref), FRONT reference. Distinguish defaults from saved settings in the status.
- Acceptance: Controls, Preview Prompt and Generate use the same settings.
- Validation: disposable UI/API check.
- Status: complete.

### WP2 - Recompute prompt freshness
- Dependencies: none.
- Files: zet/services/character_asset_container_service.py.
- Work: Compile current prompt using candidate request provenance settings, recalculate earlier_prompt for completed candidates, and retain previous marker only when compilation cannot establish freshness.
- Acceptance: Same governing prompt under captured mode clears stale marker. A real master prompt change sets it. Captured inputs and rankings remain unchanged.
- Validation: disposable service fixture.
- Status: complete.

### WP3 - Resume Costume Dressing
- Dependencies: WP1, WP2.
- Files: Zet Tester resume run, Local Characters and Testing documentation.
- Work: Preserve current candidates, add four FRONT LEFT guided candidates in empty slots, review and lock best eligible result, then complete FRONT RIGHT with corresponding Assembly source and dressed FRONT guide.
- Acceptance: Both quarter views have locked published candidates and recorded report evidence.
- Validation: approved S2, disposable checks, dashboard workflow and git diff --check.
- Status: blocked pending dashboard release.

## Constraints
No schema, dependency or permanent scenario changes. Keep prepared tests isolated. The test dashboard uses ZetTester. Verify selected FRONT and Assembly locks before starting each render.

## Results
The unsaved frontend default now matches the rendered controls and uses FRONT as the design reference. Freshness comparison uses captured Costume-Dressing settings and can clear stale markers after successful comparison. A disposable service fixture passed both unchanged and changed prompt cases. All four approved E2E scenarios passed in 41.8 seconds. Python syntax, JavaScript syntax and `git diff --check` passed.

The tester dashboard reported release `a836628bb5a0e0665e59449dd8ff8745526514de` before and after Restart current version. Its restart action does not activate the workspace source changes. Live FRONT LEFT/RIGHT follow-through remains pending a dashboard running this change. The four existing LEFT candidates remain untouched in slots 1–4; slots 5–8 remain empty.

