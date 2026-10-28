# JavaScript Console Error Survey
Status: active

## Goal
Survey the deployed dashboard and an isolated fixture for recurring browser errors, identify shared causes, and produce a prioritized remediation plan. This plan does not authorize application fixes, deployment, production writes, live Narrative checks, or permanent test expansion.

## Current behavior
`Scripts/capture-dashboard-ui.mjs` captures 26 destinations at five viewport sizes but records activation failures and overflow, not console/network failures. It omits the active `local-overview` and `local-head-image-edit` destinations by default. `zet.js` refreshes production-work summary on a 45-second timer; `/api/production-work-summary` and `/api/assets` convert backend exceptions to HTTP 400. Most startup paths load `/api/assets`, with a special case for Minor Characters. A prior disposable Minor Characters check passed with storage denied, but did not attribute the reported storage errors.

## Desired result
A redacted, reproducible evidence set covering active destinations, safe read-only production browsing, and the approved isolated E2E scenarios. Findings are grouped by signature/source/endpoint with frequency, impact, confidence, reproduction evidence, and an ordered remediation plan. Unavailable normal-browser evidence or fixture destinations remain explicit gaps.

## Constraints
Use existing Playwright, one agent, one machine. Never send writes to the deployed site. Exclude actions that autosave, collect results, enqueue work, or change configuration. Disposable checks use existing fixture roots and prepared responses. No live AI calls, production content changes, deployment, permanent tests, or blanket error suppression.

## Implementation packets
### WP1 — Inventory and boundaries
- Dependencies: none.
- Files: this plan; `test-results/console-survey/manifest.json`.
- Work: derive destinations from shell navigation and canonical page routing; include Overview and Head-Image Edit; record prerequisites, safe actions, direct entry routes and known polling. Identify retired routes and excluded mutating actions. Record local and served revisions separately.
- Acceptance: every reachable active destination is inspected, blocked, excluded with reason, or covered by an equivalent route.
- Validation: compare manifest with shell buttons, canonical page mapping and standalone routes.
- Status: complete; inventory generated during survey setup.

### WP2 — Disposable evidence collector
- Dependencies: WP1.
- Files: `test-results/console-survey/survey.mjs` and per-run output.
- Work: collect console warning/error, page exceptions, rejected promises surfaced as page errors, failed requests and HTTP 400+; retain source/frame, stack, URL, method, status, destination/context-at-request, timestamp and bounded error details. Preserve raw events while correlating. Exclude credentials/cookies and unrelated response content. Track coverage and runner health. Verify collector with a local synthetic page, never the deployed service.
- Acceptance: injected console/exception/HTTP failures are separately recorded and correlation does not discard originals.
- Validation: `node --check test-results/console-survey/survey.mjs`; run synthetic fixture check.
- Status: in progress.

### WP3 — Deployed and isolated survey
- Dependencies: WP2.
- Files: disposable run artifacts.
- Work: direct entry/reload and in-app navigation over active destinations at desktop; safe read-only selectors, lists, previews and dialogs. Repeat Costume Dressing, Narrative, Overview and AI Queue; observe at least two minutes including context/navigation, visibility and bounded two-tab comparison. Repeat priority journeys compact. Run the existing fast scenarios against isolated data. Add a focused denied-storage disposable check. Compare a clean Chromium profile with normal-browser evidence only if available; do not infer extension cause from `content.js` alone.
- Acceptance: coverage status and reason for every destination; no production mutation or live AI request.
- Validation: audit recorder health and coverage after each pass; maintain logs/screenshots for reproduced groups.
- Status: pending.

### WP4 — Root-cause groups
- Dependencies: WP3.
- Files: this plan and evidence.
- Work: group by signature/source/endpoint/response; count occurrences/destinations and reproduction passes. Classify frontend, backend surfaced in browser, extension/browser, expected handled failure, or unresolved. Inspect server evidence where available. Trace SQLite index reader/writer overlap and `/api/assets` selection/startup context; distinguish rebuildable index from authoritative catalog. Keep storage failures separate absent causal evidence.
- Acceptance: each group has user impact, reproduction, evidence, confidence and cause or a bounded next investigation.
- Validation: reproduce twice when practical; mark intermittent/unreproduced findings.
- Status: pending.

### WP5 — Prioritized repair plan and archive
- Dependencies: WP4.
- Files: `plans/active/console-error-remediation.md`; this plan moves to `plans/completed/` only after results are complete.
- Work: rank by impact/frequency/breadth; write Luna-sized repair packets with owner, dependencies, acceptance and focused validation. Name affected documentation and any proposed permanent test requiring separate approval. Link evidence and remediation plan.
- Acceptance: reviewable findings and an ordered repair plan, with uncertainty stated.
- Validation: `git diff --check`, final artifact/diff review.
- Status: pending.

## Evidence and defaults
The deployed URL is `https://zet.schonbok.net`. Its interactions are read-only, limited to page navigation, reads and previews. Before browser execution, inspect route startup behavior and skip any read that triggers collection or other writes. The disposable harness uses existing project dependencies. The current approved baseline is four fast E2E scenarios (`npm.cmd run test:e2e`); it must remain isolated. Do not run the separately invoked live Narrative check.

## Progress and decisions
- Repository inspection confirms a 45-second production summary timer and broad exception-to-400 handling for both example API paths. These are investigation leads, not established root causes.
- UI capture inventory has 26 defaults; active navigation includes `local-overview` and `local-head-image-edit` beyond that default.
- Local browser storage failure was not reproduced in the referenced previous disposable Minor Characters check; its reported cause remains unresolved.

## Results
Pending survey execution.
## Survey results (2026-10-28)

The disposable Playwright collector was syntax-checked and the survey run completed against `https://zet.schonbok.net` in headless Chromium. It visited 26 destinations and recorded 63 raw events: 11 console errors, four HTTP errors (three 400 and one 404), eight failed requests, and seven non-GET requests deliberately blocked by the read-only guard. The blocked preview/workspace-import requests produced expected `ERR_BLOCKED_BY_CLIENT` console entries; exclude these from application findings. Raw events, per-destination coverage, user-agent/revision context, and a screenshot are under ignored `test-results/console-survey/deployed/`.

Observed server errors: `/api/assets` 400 for missing `Moonsea/Characters/Tsaeytte/Adult/Assets.json`; `/api/phase-comparison` 400 from comparing two `None` values; `/api/pipeline-controls` 400 because the selected phase lacks `Pipelines.json`; Narrative called `/api/narrative/legacy-location` with an empty scene slug and received a 404 because no migration mapping exists. See the prioritized [remediation plan](console-error-remediation.md).

Coverage limits: 19 requested destinations reached their active page. Five local pipeline routes redirected into existing batch-context routes, and Image Generation/Pipeline Controls did not activate. The run exercised route startup/read paths rather than direct/reload plus normal navigation for every route; compact priority journeys and the normal browser profile were not inspected. Narrative remained foregrounded for two minutes; the production-summary lock did not reproduce. Storage-denial errors were absent in this clean browser, which does not establish whether the normal browser extension or profile caused the original report. The deployed sweep blocked non-GET requests; it did not test their user-facing workflows. The four approved isolated E2E scenarios passed (42.3 seconds); this does not verify deployed data behavior.

`node --check test-results/console-survey/survey.mjs` and `git diff --check` passed. No product code, permanent tests, production content, or deployment changed. Survey artifacts are ignored under `test-results/`.
