# Console Error Remediation Plan
Status: active
Related survey: [console-error-survey](console-error-survey.md)

## Goal
Address reproducible production browser errors found during the 2026-10-28 survey. Implementation authorized on 2026-10-28; WP1–WP4 implemented and validated locally. Plan remains active only for WP5's unresolved original browser/storage evidence.

## Evidence and priority
The disposable Chromium run visited 26 destinations, but only 19 reached the requested active page. Five local pipeline routes redirected to existing batch-context routes; Image Generation and Pipeline Controls failed activation. The isolated four-scenario E2E baseline passed. The deployed read-only pass captured 11 console errors and four HTTP errors plus seven blocked non-GET requests; blocked requests are survey interference and must not be treated as app defects.

**P1 — Missing legacy Assets.json creates a startup 400.** `/api/assets?character=Tsaeytte&phase=Adult` returned 400 because `Moonsea/Characters/Tsaeytte/Adult/Assets.json` is absent. The shared shell issues this read on startup even for unrelated destinations. Impact is a recurring console error on page loads in this library state. Confidence: high for cause, medium for whether to skip the request or repair the data contract. Fix ownership: `zet.js` startup routing and `/api/assets` compatibility handling in `zet/web/app.py`; check the asset repository before changing behavior. Acceptance should show normal pages load without irrelevant asset errors and true asset-read failures remain visible.

**P1 — Phase Comparison ordering crashes on missing values.** `/api/phase-comparison` returned 400 with `'<‘ not supported between instances of 'NoneType' and 'NoneType'`. Reproduced once while navigating the deployed page. Confidence: high for the failing comparison operation, medium for exact source rows. Inspect the phase comparison service/repository ordering and source records before choosing a null ordering rule.

**P2 — Pipeline Controls requires absent Pipelines.json.** `/api/pipeline-controls` returned 400 for missing `Tsaeytte/Adult/Pipelines.json`; that destination therefore did not activate in the deployed library. Confidence: high. Determine whether the file is required for this active route or if the UI should explain unavailable configuration without a browser error.

**P2 — Narrative legacy-location lookup returns 404 on empty scene.** A Narrative startup request with a valid story and empty `scene_slug` returned 404, “This legacy story or scene has not been migrated.” Confidence: high for observed request/response, unresolved whether this is expected optional lookup or a stale caller. Inspect call guards and route contract before altering status handling.

**Unconfirmed reports — storage errors and SQLite index lock.** This clean headless Chromium run produced no storage-denial exception or production-summary lock error during the two-minute Narrative observation. The user’s normal browser/profile was unavailable, so extension attribution is unresolved. The lock report was not reproduced; retain it as an intermittent follow-up. Do not adjust SQLite locking/retry behavior without server-side evidence.

## Luna sized work packets

### WP1 — Startup asset request contract
- Status: complete.
- Dependencies: none; can be implemented independently after code/source audit.
- Files/interfaces: `zet/web/static/zet.js`, `zet/web/app.py`, owning asset repository/service and relevant component docs.
- Work: trace startup callers and distinguish destinations requiring the legacy asset list. Define a compatible response/error behavior for absent optional `Assets.json`, preserving diagnostics for malformed or inaccessible data.
- Acceptance: direct-load representative non-asset pages against a fixture without `Assets.json` produces no irrelevant 400; asset-dependent views still report actionable failures.
- Validation: disposable browser reproduction and existing appropriate isolated E2E assertions. Request Joe’s approval before adding permanent coverage.

### WP2 — Phase Comparison null-safe ordering
- Status: complete.
- Dependencies: none.
- Files/interfaces: phase comparison service/repository and current serializer/router.
- Work: inspect the failing source rows and sort keys; define deterministic placement for missing values consistent with current domain ordering.
- Acceptance: the reproduced data returns a stable comparison response; existing fully populated comparisons retain order.
- Validation: focused disposable service/route check and existing fast E2E baseline. Seek explicit approval before permanent test additions.

### WP3 — Pipeline Controls missing configuration state
- Status: complete.
- Dependencies: none; coordinate with WP1 only if startup changes touch shared errors.
- Files/interfaces: `zet/web/app.py`, pipeline-controls service/config reader, `zet.js` presentation.
- Work: determine supported behavior when `Pipelines.json` is absent; return a structured unavailable state or actionable page message if absence is valid, otherwise identify the required library repair.
- Acceptance: active route clearly reports the missing prerequisite without an unhandled browser error; configured control behavior remains intact.
- Validation: disposable checks with and without the file; no writes to the deployed library.

### WP4 — Narrative legacy-location empty-context lookup
- Status: complete.
- Dependencies: none.
- Files/interfaces: Narrative browser controller and legacy-location route/service.
- Work: trace why startup submits an empty scene slug and whether no legacy mapping is a normal empty result. Align request guard or route response with the intended optional lookup semantics.
- Acceptance: Narrative opens without a console 404 when no legacy mapping exists; real migration failures remain distinguishable.
- Validation: isolated Narrative startup/reload check and approved S1/S3 workflow coverage; request approval for any new maintained case.

### WP5 — Recheck storage and index-lock reports
- Status: unresolved; the available production log contains no `database is locked` or `sqlite3.OperationalError` entry. Original profile evidence and a timed lock reproduction are still unavailable.
- Dependencies: browser/profile access and server logs for the original index-lock window.
- Files/interfaces: none until the cause is established; likely storage-access callers, index repository and reconciliation owner.
- Work: compare normal browser with clean Chromium and inspect source stacks/extension IDs; correlate the index path and time with index reads, reconciliation, and logs. Keep lock contention separate from storage denial absent evidence.
- Acceptance: attribute storage errors or retain them as unresolved, and reproduce or bound the index-lock cause before selecting a code change.
- Validation: read-only normal-browser capture and isolated concurrent-read diagnostic; do not add production telemetry or change SQLite settings as part of diagnosis.

## Risks and validation
The deployed catalog may intentionally omit legacy files; making those errors silent globally could hide genuine damage. Null ordering must reflect domain semantics. Current fixture E2E results validate existing scenarios only and do not cover these deployed library errors. The survey blocked POSTs on purpose; preview, workspace import, and other blocked operations were not exercised and their associated browser errors are excluded from product findings.

## Status
WP1–WP4 implemented locally. WP5 remains unresolved: no original browser/profile capture or matching server lock log was supplied. No SQLite or storage changes are justified yet.

## Implementation findings and impact
- WP1: onboarding already reports `assets_exists` separately from readiness. `zet.js:loadAssets` skips known-absent legacy storage, clears stale selection and explains the local workflow alternative. `/api/assets` remains strict for actual callers; malformed/unreadable files still fail visibly.
- WP2: local comparison rows deliberately have `asset_id=None`; `_assets_by_slot` sorted those IDs. `PhaseComparisonService` now preserves numeric legacy ordering and uses stable local source keys for missing IDs, including slot-order tie breaks.
- WP3: `PipelineRepository` distinguishes missing configuration from invalid configuration. `PipelineControlService.snapshot` returns global settings plus an unavailable message and empty legacy rows only for the missing-file case. Router serialization and browser status expose this state.
- WP4: `ZetApp.list_stories` projects native Narrative IDs as `slug`; shared shell routes therefore passed native IDs to the migration lookup. The caller now recognizes known native IDs and translates them directly. Actual legacy probes use explicit optional lookup; unmatched probes return null with a visible migration notice. Required lookups retain 404 behavior, and repository failures are not swallowed.
- Affected knowledge owners: Dashboard UI and Narrative components. Architecture, data persistence, universe/queue/locked-image invariants and code-map responsibilities do not change; no schema or durable design decision requires an ADR.
- Validation: approved S1–S4 baseline plus disposable missing-file, malformed-file, null-ID ordering and Narrative route/browser checks. No maintained scenarios added. No production library writes or live AI calls.

## Observed results (2026-10-28)
- `npm.cmd run test:e2e`: four approved scenarios passed (41.6s). Initial run passed three and timed out in S1's second template upload: successful context refresh now reaches the existing post-upload navigation that the missing-assets exception previously prevented. Repaired S1 to reopen setup before restoring the fixture; no scenario or coverage expansion.
- `python3 -B test-results/console-remediation/check.py`: focused checks passed legacy numeric ordering, stable source-key selection for null IDs, a real fixture comparison, configured/malformed/missing Pipelines.json, and strict/optional migration lookups before starting its isolated browser server. Initial disposable harness assumed the seed had legacy files; corrected it to create its own configured case.
- `node test-results/console-remediation/browser.mjs`: four direct loads (Overview, Pipeline Controls, native Narrative story and unmigrated legacy story) passed with no page errors or HTTP errors and no irrelevant asset-list request. Required lookup remained 404, optional absence returned 200/null, and explicit malformed asset/pipeline reads remained 400.
- Python AST checks and `node --check zet/web/static/zet.js` passed. Disposable scripts/fixtures remain ignored under `test-results/console-remediation/`.
- Updated Dashboard UI and Narrative component knowledge. Existing responsibilities remain in place, so no code-map change or ADR was needed.
- No deployment performed. WP5 remains unverified; no SQLite retry/settings or browser storage changes were made. Final diff/whitespace review recorded after documentation completion.
