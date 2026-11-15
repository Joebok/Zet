# Template Improvement status and proposal quality
Status: complete
Related issue/specification: User report and approved implementation plan from 2026-11-14

## Goal
Make template review state truthful across navigation, polling, and recovery; expose durable AI submission progress; improve directed local model edits while preserving safe review, preview, and acceptance.

## Current behavior
`CharacterContainerTemplateService` persists a proposal and submits `_review_job` through `AIWorkflowService`. Directed Ollama Head reviews use line IDs, but include all eight compiled prompts and return up to twelve edits. Other directed Ollama reviews use exact-text findings. The dashboard sets a separate analyzing status after the POST and does not clear it on scope changes or review completion. Review polling stops on a transient fetch error.

## Desired behavior
Scope changes clear transient UI status. Persisted proposal/workflow/request state drives analysis display through storage recovery. Directed Ollama reviews work from bounded source sections, preserve independently valid edits, and label prompt versus criteria effects. Human preview and explicit master acceptance remain required.

## Impact analysis
- `zet/web/static/character_asset_container.js` and its template asset version.
- `zet/services/character_container_template_service.py`, existing proposal endpoints, and durable AI workflow/request records.
- `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, `Docs/COMPONENTS/AI_JOBS.md`, `Docs/CODE_MAP.md`, and this plan.
- No new dependency or public endpoint. Existing proposal records resume by their saved format version.

## Invariants and constraints
Preserve universe/container ownership, frozen review inputs, unique anchors, source section ownership, source structure and view tags, compiler checks, master revision fencing, and explicit acceptance. Do not add maintained scenarios. Use disposable isolated fixtures for new contracts. Historical Gemma Body candidate evidence may be unavailable after deletion and must be reported as unverified when replay cannot reproduce it.

## Implementation steps
### WP1 — Dashboard status lifecycle
- Dependencies: none.
- Files/interfaces: `zet/web/static/character_asset_container.js`, `zet/web/templates/index.html`.
- Work: clear stale status on scope changes; bind polling and late responses to the active proposal/container; serialize polls; retry temporary request errors; clear old validation feedback after successful preview/acceptance.
- Acceptance: opening another pipeline displays no stale analysis; a pending review survives a temporary poll failure and settles visibly.
- Validation: disposable browser check and JavaScript syntax.
- Status: complete.

### WP2 — Durable review progress
- Dependencies: WP1.
- Files/interfaces: `zet/services/character_container_template_service.py`, existing AI job/workflow services as needed, proposal API projection, controller.
- Work: project workflow state and matching structured AI request identity/status without exposing prompt contents; distinguish preparation, queued/running, storage pause, and terminal proposal state. Repair orphaned acknowledged work only after storage is healthy and prove no active job exists.
- Acceptance: proposal and ask IDs correlate across restart/recovery; polling reflects actual continuation and request state; no duplicate AI asks.
- Validation: isolated prepared transport plus forced temporary storage failure/reconnect.
- Status: implemented. Workflow records retain structured AI request IDs across pending yields, and proposal detail projects continuation/request status. A completed or missing continuation without a saved result is an actionable failure when storage is healthy; an outage is shown as paused. Disposable checks covered request identity reuse after interrupted collection and missing-continuation projection under healthy and unavailable storage. The production filesystem queue was not taken offline for an integration test.

### WP3 — Bounded section requests
- Dependencies: WP2.
- Files/interfaces: `zet/services/character_container_template_service.py` and existing source/compiler interfaces.
- Work: version new directed Ollama text review records. Submit separate compact requests for applicable render-facing sections and overrides. Preserve other review paths. Reconstruct source edits and derive affected views from all eight local previews.
- Acceptance: Head description/preservation/overrides and Body facts/overrides can change render prompts; saved reviews resume their original request version.
- Validation: prepared response replay, repeated anchor and all-view compiler checks.
- Status: implemented for directed Ollama text reviews on Body Reference and Head Image Edit. Each populated render-facing section gets its own compact request with frozen line IDs. Eight prompts are recompiled locally to derive view impact. Historical saved reviews retain their original format and behavior.

### WP4 — Partial findings and effect classification
- Dependencies: WP3.
- Files/interfaces: template review service and dashboard proposal renderer.
- Work: independently validate each section response; merge identical edits, expose alternatives for conflicting edits, and keep valid findings when a sibling fails. Classify render-prompt and criteria-only effects. Show a recoverable empty-result reason and source editor path while rejecting malformed or unsafe text.
- Acceptance: valid edits remain selectable beside rejected edits; criteria-only changes are explicit; source and compiler guards remain authoritative.
- Validation: isolated malformed, partial, repeated, conflicting, overlapping, no-op, and valid response checks.
- Status: implemented for line-based directed Body/Head reviews. Malformed/unsafe line edits are rejected individually, valid sibling edits remain available, section failures are retained, conflicting replacements are labeled as alternatives, and selecting multiple alternatives is rejected. Exact-text review retains its existing per-finding validation. The UI labels prompt versus review-criteria effects.

### WP5 — Body accepted-text lineage investigation
- Dependencies: WP3 and WP4.
- Files/interfaces: source promotion, prompt compilation, frozen render request, candidate display; local characters documentation.
- Work: replay the Gemma waist correction through each boundary using isolated data. Fix the first reproducible divergence. If historical bytes are unavailable and replay passes, record the historical case as unverified.
- Acceptance: a newly staged candidate carries the accepted wording; baseline prompts and frozen retries retain their captured wording.
- Validation: disposable service/browser check, approved E2E baseline, syntax checks, and diff review.
- Status: historical divergence unverified. The test-library deleted Gemma phase retains 581 files, but candidate `591c63f7a9a7492f9e8db0fbe4450515` and its proposal are not present in the archived data. Disposable source replay verified that edited Body/Head lines compile through the eight-view preview and derive affected views from prompt changes. No saved historical render request was available to verify the original candidate staging/display boundary, and no production fix was reproduced.

## Validation
Run `npm.cmd run test:e2e`, `node --check zet/web/static/character_asset_container.js`, and `git diff --check`. Disposable checks cover browser navigation, submission, storage status projection, request identity reuse, malformed and mixed findings, prompt compilation, and alternative selection. Live model comparison is excluded unless separately authorized.

## Progress and decisions
- Repository instructions and current component/code-map ownership inspected. User supplied implementation scope authorizes local code and documentation changes.
- The controller now clears the stale inline analyzing message whenever a new container is activated. Proposal polling allows only one request at a time, ignores a response after the active container/proposal changes, and retries after temporary HTTP errors while displaying the error next to the pending proposal.
- Proposal polling now stops when the durable continuation reaches terminal failure and keeps the reload/new-analysis instruction visible.
- WP1 and WP2-WP4 changes pass syntax and approved fast-suite checks. Disposable prepared replay against the test Character.md verified Body/Head source-section anchors, structure guards, eight-view preview impact plumbing, alternative grouping/selection rejection, and keeping a valid edit when a sibling edit has an unknown line ID. A second disposable check verified an orphaned proposal fails actionably when storage is healthy and pauses when unavailable. Workflow/AIJobService checks verified structured ask ID retention and reuse across pending collection. These checks do not exercise the real filesystem queue during an outage. The archived Gemma deletion copy has 581 files but no occurrences of the recorded proposal or candidate IDs. No live model or renderer was used.

## Final results
WP1-WP4 are implemented. Proposal progress follows saved workflow/request records, transient polling errors retry inline, and missing continuation records produce a recovery-aware outcome. Directed local Body/Head text reviews use bounded section requests with independent validation and selectable alternatives. Disposable checks verified request ID retention/reuse after pending collection, healthy/outage orphan projection, editable anchors, source/compiler guards, eight-view impact, alternatives, and preservation of a valid finding beside a malformed sibling. `node --check zet/web/static/character_asset_container.js`, Python AST parsing, and `git diff --check` passed. The latest `npm.cmd run test:e2e` passed all four approved scenarios (47.3 seconds). No production AI queue or storage root was interrupted. The historical Gemma Body candidate lineage remains unavailable; an isolated source replay compiled the correction, but its original frozen render request and candidate display cannot be verified. No live model or renderer was used.
