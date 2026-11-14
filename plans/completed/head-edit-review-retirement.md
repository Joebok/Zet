# Head Image Edit review and Construct retirement cleanup
Status: active
Related issue/specification: ADR 0054 and Zet_Tester Luna case

## Goal
Repair Luna's rejected text review, keep Character Wizard authoring scoped to Head Image Edit, and remove live references to retired Head Image Construct.

## Current behavior
Codex reviews use exact excerpts, which failed against noncontiguous saved bullets. The wizard can resume old saved schemas. Batch status imports a removed Construct key, while campaign and operation lists still admit it. Queue history links to its retired page. Zet_Tester asks operators to set a removed Assembly head-family control.

## Desired behavior
Template review addresses exact source occurrences by stable line ID. Stale Construct authoring cannot resume or publish. Active pipeline coordinators use the pipeline registry, and saved Construct work cannot dispatch. Current UI and tester instructions use Edit sources.

## Impact analysis
Services: `character_container_template_service.py`, Character Wizard services, pipeline policy/status/campaign/operation services, and `ai_queue_query_service.py`. Presentation: finding labels and screenshot defaults. External test workflow: Zet_Tester runner and cases. Documentation: Local Characters, Prompts, Code Map, Testing.

## Invariants and constraints
Preserve frozen proposal sources, selected correction semantics, view conditioning, current-master acceptance checks, accepted history, published assets, queue history, and saved case parsing. No permanent scenarios or dependencies.

## Implementation steps
### WP1 — Occurrence-based Head Edit findings
- Dependencies: none.
- Files/interfaces: `character_container_template_service.py`, `character_asset_container.js`.
- Work: Assign stable line IDs to Head Edit bullets, resolve exact ranges, support multiple Codex edits, and present section names.
- Acceptance: Repeated identical text can be edited independently and each preview is compiled from the exact frozen source.
- Validation: Disposable saved-response replay and range/preview checks.
- Status: complete.

### WP2 — Fence stale Construct wizard sessions
- Dependencies: none.
- Files/interfaces: `character_wizard_service.py`, `character_wizard_sections.py`.
- Work: Detect retired authoring IDs in saved schemas/baselines before dispatch and before create publication. Preserve legacy history reads.
- Acceptance: Current Edit-only sessions create/edit successfully. Stale Construct sessions require a new interview and cannot publish.
- Validation: Disposable fixture checks.
- Status: complete.

### WP3 — Remove active Construct coordinator references
- Dependencies: none.
- Files/interfaces: local batch status, run-all, pipeline operations, queue query service.
- Work: Derive active pipelines from the policy registry, skip retired campaign entries, reject retired operation admission, and omit dead queue links.
- Acceptance: Imports succeed, old campaigns continue active entries, and Construct work cannot dispatch.
- Validation: Import, campaign and operation boundary checks.
- Status: complete.

### WP4 — Update operator/tester references and knowledge
- Dependencies: WP1-WP3.
- Files/interfaces: UI capture script, Zet_Tester run instructions/cases, affected component docs and code map.
- Work: Capture Head Image Edit, remove Assembly family selection instruction while retaining legacy case parsing, document wizard and review behavior.
- Acceptance: Tester workflow relies on published Edit and Body locks and documentation describes active ownership.
- Validation: Targeted search, approved E2E baseline, `git diff --check`.
- Status: complete.

## Validation
Observed checks: frozen Luna source/response replay and line-offset mapping, current wizard source check, active pipeline registry/import checks, `npm run test:e2e` (4/4), Python compilation, JavaScript syntax, and `git diff --check`.

## Risks and alternatives
Old campaign state is user data. Retired entries will be marked skipped in the current campaign record rather than deleted.

## Progress and decisions
Investigation reproduced both zero-match findings. The Codex review path now uses section-labelled source line IDs and multiple edits. Ollama's version 1 unique-line mapping remains supported. Construct sections are fenced from unfinished wizard sessions. Pipeline coordinators use the active registry and saved campaigns skip retired entries. AI Queue history retains records without linking to the retired page. The tester instructions use Head Image Edit locks for Assembly.

## Final results
Implemented the four packets. The four approved E2E scenarios passed. The saved Luna review was replayed only through source/validator mapping. Fresh Codex repeatability, compiled preview acceptance, selected master promotion, and a live master revision conflict were not exercised. Luna's failed proposal, source master, board, and existing locks remain untouched, so a fresh review can be started from the retained board after updating the test release.
